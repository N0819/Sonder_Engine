"""A LINE THAT NAMES NOBODY IS NOT A LINE TO SOMEBODY ELSE (2026-10-20).

Wave A's din and wave B2's turned head take words from a BYSTANDER -- a
listener in front of whom a line was spoken to somebody else -- and from
nobody else: noise and a turned head never stop people talking to each
other. The flag that says which is three-valued
(`spatial_senses.spoken_to`): True, the line names this listener; False, it
names somebody else; None, it names nobody, which caps nothing.

Every reader produced only the first two. The addressee field is on nearly
every recorded line and EMPTY on 3,678 of the owner's 11,841 (31%), and an
empty field read as "names somebody else" -- so a third of all talk made
each of its listeners a bystander. Measured on the harbour story's quay
(turns 1-3): seven lines between two people fourteen metres apart, naming
nobody, fell to pieces on the speaker's end-of-beat facing. Wave A's own
test held a line with NO addressee field, which no recorded line is.
"""

from __future__ import annotations

from agents import composer
from world.spatial import sound_field, spatial_rel_between, spoken_to

EMPTY_FIELDS = ({"intended_target": None}, {"intended_target": ""},
                {"targets": []}, {"intended_target": None, "targets": None})


def _tavern():
    """A taproom ten paces by eight with a few dozen people talking in it:
    A speaks, B stands beside A, C sits at the far table nine paces off."""
    cells = {"A": (1, 1), "B": (2, 1), "C": (8, 6)}
    room = {"name": "the taproom", "exposure": "enclosed",
            "extent": {"w": 10, "d": 8}, "anchors": {}, "adjacent": []}
    return {"rooms": {"tap": room},
            "positions": {k: "tap" for k in cells},
            "stations": {k: {"cell": list(v)} for k, v in cells.items()},
            "entities": {}, "poses": {}, "orientation": {}, "contained": {}}


CROWD = [{"uid": "drinkers", "room_uid": "tap", "band": "a few dozen"}]


def _quay():
    """An open quay ninety-six paces long: A speaks from the west end with
    her back to B, who stands forty paces east of her."""
    return {"rooms": {"quay": {"name": "the quay", "exposure": "open",
                               "extent": {"w": 96, "d": 6}, "anchors": {},
                               "adjacent": []}},
            "positions": {"A": "quay", "B": "quay"},
            "stations": {"A": {"cell": [1, 3]}, "B": {"cell": [41, 3]}},
            "entities": {}, "poses": {}, "orientation": {"A": {"facing": "w"}},
            "contained": {}}


def _rel(sc, listener, speaker="A", crowds=()):
    field = sound_field(sc, listener, crowds=list(crowds))
    return spatial_rel_between(sc, listener, speaker, sound=field)


def _line(**fields):
    return dict({"speaker": "A", "exact_quote": "The tide turns at dusk.",
                 "volume": "normal"}, **fields)


def test_the_three_answers():
    assert spoken_to(True, True) is True
    assert spoken_to(False, True) is False
    assert spoken_to(False, False) is None


def test_an_empty_addressee_field_names_nobody():
    """Absent or empty, the field names nobody: unknown, never "somebody
    else" -- and still not this listener, so every yes/no reader is
    unchanged."""
    from agents.perception import _line_is_to

    class _Ctx:
        cast = ()

    sc = _tavern()
    for fields in EMPTY_FIELDS:
        line = _line(**fields)
        assert composer.line_addressed(line, "B") is None, fields
        assert _line_is_to(_Ctx(), sc, "B", line) is None, fields
        assert not _line_is_to(_Ctx(), sc, "B", line)
    named = _line(intended_target="B")
    assert composer.line_addressed(named, "B") is True
    assert composer.line_addressed(named, "C") is False
    assert _line_is_to(_Ctx(), sc, "C", named) is False


def test_a_din_takes_no_word_of_a_line_naming_nobody():
    """Nine paces off in a few dozen people's talk, a line spoken to B is
    caught in pieces at the far table -- and a line that names nobody is
    followed whole, as wave A's rule says of a line it cannot place."""
    far = _rel(_tavern(), "C", crowds=CROWD)
    assert far.get("din_db") is not None
    assert composer.line_hear_level(_line(intended_target="B"), far, "C") \
        == "fragment"
    for fields in EMPTY_FIELDS:
        assert composer.line_hear_level(_line(**fields), far, "C") == "full", \
            fields
        p = composer.speech_percept(_line(**fields), far, "C",
                                    display="the speaker", can_see=False)
        assert p is not None and p.fidelity == "full", (fields, p)
        assert p.data.get("body") == "The tide turns at dusk."


def test_a_turned_head_takes_no_word_of_a_line_naming_nobody():
    """Forty paces of open quay, the speaker's back to the listener: a line
    spoken to somebody else reaches the listener in pieces, and one naming
    nobody -- two people trading lines -- reaches them whole."""
    rel = _rel(_quay(), "B")
    assert rel.get("speaker_turned_away") is True
    assert composer.line_hear_level(_line(intended_target="C"), rel, "B") \
        == "fragment"
    for fields in EMPTY_FIELDS:
        assert composer.line_hear_level(_line(**fields), rel, "B") == "full", \
            fields


def test_a_breath_into_an_ear_naming_nobody_still_reaches_nobody():
    """Unknown is not a licence for the ear rung: a line breathed into an
    ear that names no ear reaches nobody, the body beside the speaker
    included (`EAR_VOLUME` fails toward no)."""
    beside = _rel(_tavern(), "B")
    for fields in EMPTY_FIELDS:
        assert composer.line_hear_level(_line(volume="ear", **fields),
                                        beside, "B") == "none", fields
    assert composer.line_hear_level(
        _line(volume="ear", intended_target="B"), beside, "B") != "none"
