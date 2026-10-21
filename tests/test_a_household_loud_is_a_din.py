"""A HOUSEHOLD `loud` IS A DIN, NEVER A ROOM DROWNED (the owner,
2026-10-20: "Ordinary household objects should probably be scaled back").

The emission ladder read `loud` as 80 dB(A) at a pace -- "an engine at idle,
a mill, a busy workshop" -- while a model writes it for the loudest thing a
home, a shop or a street holds. Chat 176's opening wrote the kettle on the
range `loud`, which put 83 dB at the range: "Where you are, the noise drowns
everything" for a body standing at it, and a kettle heard rooms away through
the far field. Since 2026-10-20 the hearing rule takes nothing from a line
below `deafening`, so what `loud` still decides is DESCRIPTION and REACH,
and those are what these pin:

  1. `loud` sits in the household band (a vacuum cleaner or a television
     turned up, 65-75 dB(A) at a metre) and `deafening` keeps the class that
     stops conversation;
  2. the noise words read a household `loud` as a `din` at most, at every
     cell of its room, its own included -- and with a second such thing
     beside it;
  3. a household `loud` is a near-field thing: heard in its own room and the
     next, never entering the far field; a `deafening` one still does;
  4. no spoken line moves (the re-grade of every recorded line says the same
     for the corpus: `DESIGN_SOUND_FIELD.md` § 11.8).

The kitchen is chat 176's, as its checkpoint holds it.
"""

from __future__ import annotations

import copy

import pytest

from world.spatial import (NOISE_WORDS, SOUND_ONE_PACE_DB, far_field_sources,
                           hear_level, hearing_reason, noise_word,
                           room_noise_word, sound_field, sound_shape,
                           spatial_rel_between)

_ORDER = {word: n for n, word in enumerate(NOISE_WORDS)}   # quiet < din < drowned


def _kitchen(*, kettle="loud", second=None, cook=(3, 0)):
    """Chat 176's kitchen at turn 2: five paces square, furnished, a kettle
    on the range the opening wrote `loud`. The cook stands AT the range --
    on its cell, which is where a body stationed at a fixture is placed --
    and the parlour lies beyond an open door, the hall beyond that."""
    kitchen = {
        "name": "The Kitchen", "exposure": "enclosed", "surface": "furnished",
        "extent": {"w": 5, "d": 5}, "light": "lit",
        "anchors": {
            "kitchen_range": {"desc": "the range", "dir": "n",
                              "height": "waist", "footprint": "small",
                              "cell": [3, 0]}},
        "adjacent": [{"to": "parlour", "barrier": "open_door", "dir": "s",
                      "offset": 0.5}],
    }
    parlour = {"name": "The Parlour", "exposure": "enclosed",
               "extent": {"w": 5, "d": 5},
               "adjacent": [{"to": "kitchen", "barrier": "open_door",
                             "dir": "n", "offset": 0.5},
                            {"to": "hall", "barrier": "open_door",
                             "dir": "s", "offset": 0.5}]}
    hall = {"name": "The Hall", "exposure": "enclosed",
            "extent": {"w": 5, "d": 5},
            "adjacent": [{"to": "parlour", "barrier": "open_door",
                          "dir": "n", "offset": 0.5}]}
    entities = {"the kettle": {
        "name": "the kettle", "kind": "object", "portable": True,
        "description": "A squat tin kettle with steam jetting from its spout.",
        "state": {"whistling": True}, "sound_source": kettle}}
    stations = {"the kettle": {"at": "kitchen_range"},
                "Mellisande": {"at": None, "near": [], "cell": list(cook)},
                "Hinami": {"at": None, "near": [], "cell": [2, 4]},
                "Ada": {"at": None, "near": [], "cell": [2, 2]}}
    positions = {"the kettle": "kitchen", "Mellisande": "kitchen",
                 "Hinami": "kitchen", "Ada": "hall"}
    if second:
        entities["the radio"] = {
            "name": "the radio", "kind": "object", "portable": True,
            "description": "A wireless on the shelf by the range.",
            "state": {}, "sound_source": second}
        stations["the radio"] = {"at": "kitchen_range"}
        positions["the radio"] = "kitchen"
    return {"rooms": {"kitchen": kitchen, "parlour": parlour, "hall": hall},
            "positions": positions, "stations": stations,
            "entities": entities, "poses": {}, "orientation": {},
            "contained": {}}


def _words(sc, room="kitchen", size=(5, 5)):
    """The noise word a body standing at each cell of `room` is in: a probe
    stood on every cell in turn, the kettle's own included, and the noise
    at its ear named (`noise_at`, which is the standing sources and the
    room's floor where no one-beat sound is made)."""
    words = {}
    for x in range(size[0]):
        for y in range(size[1]):
            probe = copy.deepcopy(sc)
            probe["positions"]["Probe"] = room
            probe["stations"]["Probe"] = {"at": None, "near": [],
                                          "cell": [x, y]}
            field = sound_field(probe, "Probe", room=room)
            words[(x, y)] = noise_word(field.noise_at("Probe", room=room))
    return words


def test_loud_is_a_household_level_and_deafening_stops_conversation():
    """A vacuum cleaner or a television turned up is 65-75 dB(A) at a
    metre: the loudest an ordinary household thing gets. A klaxon, a siren
    and machinery a voice cannot be raised over stay `deafening` (95-110)."""
    assert 65.0 <= SOUND_ONE_PACE_DB["loud"] <= 75.0
    assert SOUND_ONE_PACE_DB["deafening"] == 100.0
    ladder = [SOUND_ONE_PACE_DB[w] for w in
              ("faint", "audible", "loud", "deafening", "thunderous",
               "catastrophic")]
    assert ladder == sorted(ladder), "the ladder must stay monotone"


def test_a_household_loud_reads_a_din_at_most_at_every_cell_its_own_included():
    """Chat 176 turn 2: a body at the range read "the noise drowns
    everything" beside a whistling kettle. It is a din there -- a voice is
    raised over it -- and nowhere in the room is it more."""
    words = _words(_kitchen())
    assert words, "the kitchen must carry a field"
    assert max(_ORDER[w] for w in words.values()) <= _ORDER["din"], words
    assert "din" in words.values(), "a loud thing is still a din near it"
    # The body standing at the range is told so in its own shape.
    shape = sound_shape(_kitchen(), "Mellisande")
    assert shape is None or shape["self"] in (None, "quiet", "din"), shape


def test_two_household_things_side_by_side_are_still_a_din():
    """A radio turned up on the shelf beside the whistling kettle: 71 dB at
    their spot, still under the 72 a room is `drowned` at."""
    words = _words(_kitchen(second="loud"))
    assert max(_ORDER[w] for w in words.values()) <= _ORDER["din"], words


def test_deafening_still_drowns_the_room_it_runs_in():
    """The complement, unchanged: a thing that stops conversation drowns the
    room it runs in -- everywhere, not only beside it."""
    words = _words(_kitchen(kettle="deafening"))
    assert set(words.values()) == {"drowned"}
    assert room_noise_word(_kitchen(kettle="deafening"), "kitchen") == "drowned"


def test_a_household_loud_is_heard_next_door_and_never_rooms_away():
    """The far field carries what is loud enough to cross a building (70 dB
    at the source's cell). A household thing is met in its own room and the
    next; until 2026-10-20 the kettle entered at 83 and was heard rooms
    away. A deafening one still enters."""
    assert far_field_sources(_kitchen()) == []
    entered = far_field_sources(_kitchen(kettle="deafening"))
    assert [s["id"] for s in entered] == ["the kettle"]
    # Next door, on the parlour's own field, it is still heard.
    field = sound_field(_kitchen(), "Ada", room="parlour")
    assert field is not None
    assert field.level_of("Ada", "the kettle", room="parlour") != "none"


def test_no_spoken_line_moves_with_the_household_level():
    """`loud` MASKS no line: below `deafening` nothing masks speech
    (`masking_db` is never stamped), so every volume between the two in the
    kitchen grades the same with the kettle loud, audible or gone -- for
    everyone within conversational reach, and for the one standing clear of
    the thing. The one exception is the round-2 class (2026-10-20, lane B):
    the cook standing AT the whistling kettle, on its own cell, is in its
    din (some 64 dB(A) at her ear), and a normal voice spoken TO her from
    four paces off comes in pieces, a raised one whole -- the din at the
    listener's ear decides beyond conversational reach, whoever the line
    was for (`tests/test_a_din_reaches_an_addressee_beyond_reach.py`). The
    kettle at `audible` is no din anywhere."""
    volumes = ("ear", "whisper", "mutter", "normal", "loud", "shout")

    def graded(sc, pairs=(("Mellisande", "Hinami"), ("Hinami", "Mellisande"))):
        out = {}
        for listener, speaker in pairs:
            rel = spatial_rel_between(sc, listener, speaker)
            assert "masking_db" not in rel
            out[(listener, speaker)] = {
                v: hear_level(rel, v, addressed=True) for v in volumes}
        return out

    base = graded(_kitchen())
    # Hinami, four paces from the range, hears the cook as she would in a
    # quiet kitchen; the cook at the kettle has Hinami's ordinary voice in
    # pieces and her raised voice whole.
    assert base[("Hinami", "Mellisande")] == graded(
        _kitchen(kettle="audible"))[("Hinami", "Mellisande")]
    at_the_kettle = base[("Mellisande", "Hinami")]
    assert at_the_kettle["normal"] == "fragment"
    assert at_the_kettle["loud"] == at_the_kettle["shout"] == "full"
    rel = spatial_rel_between(_kitchen(), "Mellisande", "Hinami")
    assert rel.get("din_db") is not None and float(rel["paces"]) > 2.0
    assert hearing_reason(rel, "normal", addressed=True) == "din_beyond_reach"
    # Two paces from the kettle (within reach of the speaker beside her)
    # the din takes nothing; and with the kettle audible or gone nothing
    # anywhere moves.
    assert graded(_kitchen(cook=(2, 3)))[("Mellisande", "Hinami")] == \
        graded(_kitchen(kettle="audible", cook=(2, 3)))[("Mellisande", "Hinami")]
    quieter = graded(_kitchen(kettle="audible"))
    quiet = _kitchen()
    quiet = copy.deepcopy(quiet)
    del quiet["entities"]["the kettle"]["sound_source"]
    assert graded(quiet) == quieter
    assert quieter[("Mellisande", "Hinami")] == {
        v: at_the_kettle[v] for v in volumes if v != "normal"} | {"normal": "full"}


_CLASS = {"en": "stops conversation outright", "ja": "会話をまるごと止める"}


@pytest.mark.parametrize("language", ["en", "ja"])
def test_the_class_is_stated_wherever_a_level_is_chosen(language):
    """One clause, stated by what a sound does to talk beside it: ordinary
    life's noise is `loud` at most, and only what stops conversation is
    `deafening`. Where the encoder writes a thing's `sound_source`, where it
    writes a place's `sound`, and in the opening (which carries the room
    vocabulary) -- in both packs."""
    from llm.prompts import get_prompt, unified_specialist_prompt
    marker = _CLASS[language]
    assert marker in unified_specialist_prompt(
        ("entities",), language, parts=("entities__emits",))
    assert marker in unified_specialist_prompt(("rooms",), language, parts=())
    assert marker in get_prompt("director_establish", language=language)
