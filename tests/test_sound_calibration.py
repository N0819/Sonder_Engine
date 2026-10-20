"""The sound field's power tables, calibrated from real decibels (2026-09-14).

The three scenes here are the ones the 2026-09-14 play produced (two fresh
stories, 22 turns; the session's `play/REPORT_PLAY.md`), each pinned as the
verdict a reader would accept and the compressed ladder refused:

  a. a drawing room with a hearth fire: a line spoken AT the hearth reached
     nobody five paces off ("she offered no reply", four beats running),
     because `audible` held a normal voice's own power;
  b. a launch deck with its engine running: a raised line one pace off was
     `none` from every cell, because `loud` held a loud voice's own power
     and the fragment margin sat a decibel under the noise;
  c. a still room: the quiet volumes, which the old ladder put within two
     decibels of each other.

Every level is `SPEECH_ONE_PACE_DB` / `SOUND_ONE_PACE_DB`, a sound pressure
level at one pace a reader can check against any decibel chart; the numbers
in the docstrings are what the field measured on these scenes.

RESTATED 2026-10-20 by the owner's ruling (the hearing rule,
`spatial_senses.hear_level`): noise never masks speech but for what the
story makes deafening, so a voice in one room is heard whole by every
listener in it and the quiet volumes are private beyond reach. What these
scenes still pin is the description -- the noise words a room carries -- and
the verdicts the rule gives them.
"""

from __future__ import annotations

from tests.test_field_sentences import room, scene
from world.spatial import (body_cell, hear_level, noise_word, sound_field,
                           spatial_rel_between, SPEECH_VOLUMES)


def _levels(sc, speaker, listener):
    rel = spatial_rel_between(sc, listener, speaker)
    assert rel.get("air"), "the field must place the pair"
    return {v: hear_level(rel, v) for v in SPEECH_VOLUMES}


def _noise_word_at(sc, who):
    return noise_word(sound_field(sc, who).noise_at(who))


# ---------------------------------------------------------------------------
# a. A hearth fire does not mask the people sitting at it
# ---------------------------------------------------------------------------

def drawing_room():
    """A medium 8x7 room, an `audible` fire at the south wall's hearth. A
    stands at the hearth, B five paces north of it, C at the door on the
    north wall."""
    r = room("the Drawing Room", light="lit", anchors={
        "hearth": {"desc": "the hearth", "dir": "s", "cell": [4, 6]},
        "settee": {"desc": "the settee", "cell": [4, 1]},
        "door": {"desc": "the door", "dir": "n"}})
    r["extent"] = {"w": 8, "d": 7}
    return scene({"r": r}, {"A": "r", "B": "r", "C": "r", "fire": "r"},
                 entities={"fire": {"name": "the fire",
                                    "sound_source": "audible"}},
                 stations={"fire": {"at": "hearth"}, "A": {"at": "hearth"},
                           "B": {"at": "settee"}, "C": {"at": "door"}})


def test_a_line_from_the_hearth_reaches_five_paces_in_full():
    """A hearth fire is 50 dB(A) at a pace, 53 at its cell; five paces off
    it is 39 and the room is `quiet`. A normal line from the hearth (63 at
    the cell) arrives at 48.9 -- ten decibels over the floor, `full`.
    On the compressed ladder the fire and the voice shared a rung and the
    same line was `none` (signal 0.08 against noise 1.83)."""
    sc = drawing_room()
    assert _levels(sc, "A", "B")["normal"] == "full"
    assert _levels(sc, "A", "C")["normal"] == "full"
    assert _noise_word_at(sc, "B") == "quiet"


def test_the_fire_is_quiet_even_at_the_hearth():
    """Standing AT the fire the floor is the fire itself, 53 dB, and a
    normal voice one pace off is still ten over it: the hearth is `quiet`,
    not the `din` the play rendered ("The fire's din was loud here")."""
    sc = drawing_room()
    assert _noise_word_at(sc, "A") == "quiet"
    # The line back TO the hearth from five paces is graded against the
    # fire at the listener's ear: 48.9 against 53 is four under, in pieces.
    assert _levels(sc, "B", "A")["normal"] in ("full", "fragment")
    assert _levels(sc, "B", "A")["loud"] == "full"


# ---------------------------------------------------------------------------
# b. A launch engine is a din a voice is raised over, and masks none of it
# ---------------------------------------------------------------------------

def deck(engine_cell=(3, 0), a_cell=(0, 2), b_cell=(0, 1), length=4):
    """A 4x3 open deck (`length` paces long) with a `loud` engine (80 dB(A)
    at a pace, 83 at its cell) at `engine_cell`; A and B at the two named
    cells; W in the bow beside the engine."""
    r = room("the Deck", light="lit", anchors={
        "engine": {"desc": "the engine", "dir": "n", "cell": list(engine_cell)},
        "stern_bench": {"desc": "the stern bench", "cell": list(a_cell)},
        "stern_rail": {"desc": "the stern rail", "cell": list(b_cell)},
        "bow": {"desc": "the bow", "cell": [max(0, engine_cell[0] - 1),
                                            engine_cell[1]]}})
    r["extent"] = {"w": length, "d": 3}
    r["exposure"] = "open"
    return scene({"d": r}, {"A": "d", "B": "d", "W": "d", "eng": "d"},
                 entities={"eng": {"name": "the engine", "kind": "machine",
                                   "sound_source": "loud"}},
                 stations={"eng": {"at": "engine"}, "A": {"at": "stern_bench"},
                           "B": {"at": "stern_rail"}, "W": {"at": "bow"}})


def test_a_raised_line_one_pace_off_survives_the_engine_in_pieces():
    """Across the deck from the engine (a path of 3.8) the floor is 74.7
    dB; a loud line (73 at the cell) one pace off arrives at 70, five
    under the floor and well inside the fragment margin (-12). Nearer the
    machine the margin narrows and the verdict holds: from every cell of
    the deck a loud line one pace off is at least a fragment."""
    for engine, a, b in (((3, 0), (0, 2), (0, 1)),      # corner to corner
                         ((2, 0), (0, 2), (1, 2)),      # wall centre, far corner
                         ((2, 0), (2, 2), (3, 2))):     # two paces from it
        sc = deck(engine, a, b)
        assert _levels(sc, "A", "B")["loud"] in ("fragment", "full"), engine
        assert _levels(sc, "A", "B")["shout"] in ("fragment", "full"), engine


def test_a_conversation_at_arms_reach_carries_over_the_deck():
    """Sharing a cell (arm's reach), three paces from the engine and two:
    a normal line is heard whole at both.

    RECALIBRATED 2026-09-23 for the Lombard effect, and OVERTURNED
    2026-10-20 by the owner's ruling for what it still kept: two paces from
    the machine a normal and a raised line at arm's length were pinned in
    pieces. A `loud` engine is an everyday thing on the class ladder -- the
    same word is a whistling kettle -- and nothing short of deafening takes
    a voice away: people on a launch talk over its engine, raising their
    voices (the owner, of arm's-reach replies arriving in pieces in a
    working room, 2026-09-23: "doesn't make particular sense")."""
    far = deck((3, 0), (0, 2), (0, 2))
    assert _levels(far, "A", "B")["normal"] == "full"
    near = deck((2, 0), (2, 2), (2, 2))
    assert _levels(near, "A", "B")["normal"] == "full"
    assert _levels(near, "A", "B")["loud"] == "full"
    assert _levels(near, "A", "B")["whisper"] == "full"


def test_a_whisper_across_the_deck_is_gone():
    """A whisper from the stern to the bow is gone from every layout -- a
    whisper is speech for a listener at touching distance, and the bow is
    not that. The deck is `drowned` everywhere, which is DESCRIPTION: what
    a voice has to rise over (`noise_word`).

    RESTATED 2026-10-20: the whisper is lost to the distance between the two
    bodies (the hearing rule's privacy beyond reach), not to the engine, so
    the deck is a launch's twelve paces: on the original 4x3 the stern bench
    and the bow stand a diagonal pace apart, which is arm's reach. Between
    the two at the stern, a pace apart at the bench and the rail, it is
    whole."""
    for engine, a, b in (((11, 0), (0, 2), (0, 1)), ((10, 0), (0, 2), (1, 2))):
        sc = deck(engine, a, b, length=12)
        assert _levels(sc, "A", "W")["whisper"] == "none", engine
    stern = deck((11, 0), (0, 2), (0, 1), length=12)
    assert _levels(stern, "A", "B")["whisper"] == "full"
    for engine, a, b in (((3, 0), (0, 2), (0, 1)), ((2, 0), (0, 2), (1, 2))):
        assert _noise_word_at(deck(engine, a, b), "A") == "drowned", engine


# ---------------------------------------------------------------------------
# c. A still room and the quiet volumes
# ---------------------------------------------------------------------------

def still_hall():
    """A large 12x10 enclosed room with nothing running in it: the 27.0 dB
    floor an ordinary quiet room carries. A at (2,1), beside the lectern;
    B one pace east, beside the first bench; F in the far corner, a path of
    11.4. A and B are pinned: until 2026-10-13 a body at the lectern was
    stood in the bench beside it, which is what put the two one pace apart,
    and a cell code chooses now keeps out of every fixture the body is not
    on (`spatial_fov._stand_cell`)."""
    r = room("the Hall", light="lit", anchors={
        "a": {"desc": "the lectern", "cell": [1, 1]},
        "b": {"desc": "the first bench", "cell": [2, 2]},
        "far": {"desc": "the far corner", "cell": [10, 8]}})
    r["extent"] = {"w": 12, "d": 10}
    return scene({"r": r}, {"A": "r", "B": "r", "F": "r"},
                 stations={"A": {"at": "a", "cell": [2, 1]},
                           "B": {"at": "b", "cell": [3, 1]},
                           "F": {"at": "far"}})


def test_a_whisper_at_one_pace_is_whole_and_across_a_hall_is_gone():
    """A whisper is 35 dB(A) at a pace: eight over the floor beside you,
    `full`; across the hall (38 at the cell, 21.2 of path) it is 16.8,
    ten under the floor, `none`. A mutter (38) beside you is `full` and
    across the hall is gone as well; a normal voice carries the hall."""
    sc = still_hall()
    beside = _levels(sc, "A", "B")
    across = _levels(sc, "A", "F")
    assert beside["whisper"] == "full"
    assert beside["mutter"] == "full"
    assert across["whisper"] == "none"
    assert across["mutter"] == "none"
    assert across["normal"] == "full"
    assert _noise_word_at(sc, "A") == "quiet"


def test_the_quiet_volumes_fall_off_by_the_pace():
    """The reach of each quiet volume in a still room, pace by pace.

    RESTATED 2026-10-20 by the owner's ruling: breath-level speech is
    private beyond reach. Measured in paces of the field's own path, the
    distances this still hall gave them before stand as the privacy they
    were -- a whisper whole to two paces, a mutter to three and in pieces
    at four -- with the one change the owner made: a whisper beyond its
    reach is lost, never caught in pieces (it was a fragment at three).
    And no noise moves them any more (`spatial_senses.WHISPER_REACH_PACES`)."""
    sc = still_hall()
    ax, ay = body_cell(sc, "A")
    words = {}
    for paces in (1, 2, 3, 4, 5, 6):
        # A station's `cell` is a grid cell; an anchor's is the room's own
        # coordinate, one band in. Placing B off A's measured cell keeps the
        # pace count honest whichever convention the anchor used.
        sc["stations"]["B"] = {"cell": [ax + paces, ay]}
        assert body_cell(sc, "B") == (ax + paces, ay)
        rel = spatial_rel_between(sc, "B", "A")
        words[paces] = (hear_level(rel, "whisper"), hear_level(rel, "mutter"))
    assert words[1] == ("full", "full")
    assert words[2] == ("full", "full")
    assert words[3] == ("none", "full")
    assert words[4] == ("none", "fragment")
    assert words[5] == ("none", "none")
