"""A body picked to answer must be told what it is answering.

`_character_address_of` triggers only on a PRECISE `intended_target`. A line
aimed at nobody in particular matches nothing, so a presence the gate picked
on the place-addressed trigger arrived at `_react_one` with
`addressed_by: null` and no quote -- and the one fallback that repairs that,
`_filtered_player_declaration`, is gated on `player_addressed` and reads the
player's own declaration. For a CHARACTER's line there was no fallback at all.

Measured (Aldermill, fourth run, 2026-09-19, idx 15). Sal Weatherby said
"Small ale, when you've a moment." With the place-addressed routing repaired
the gate correctly picked a body -- `selected: ["Watisett Appleytonwater"]`,
`why: ["place_addressed:wheel_bushel_taproom", "channel:hearing"]` -- and
`_react_one` returned None. It was right to: it had been handed an
unremarkable woman standing in the room and no words. Silence is the correct
answer to that payload.

The comment at the player fallback records this exact bug being fixed once
already, for the player: "a presence the PLAYER addressed was handed
`addressed_by: null` ... the cord-seller, gripped by the sleeve and asked
twice, declined". This is the same repair for the other kind of speaker.

CHANNEL RULES ARE COPIED, NOT RELAXED: same roster test, same fail-closed
concealment, same full-hearing requirement. The only thing dropped is the
demand that the line NAME the listener -- which is the whole point, because
"small ale" names nobody.
"""

from persist.commit import _room_address_of


ROSTER = {"sal weatherby"}
SCENE = {
    "rooms": {"taproom": {"name": "Taproom"}, "yard": {"name": "Yard"}},
    "positions": {"Sal Weatherby": "taproom"},
}
ORDER = {"speaker": "Sal Weatherby", "intended_target": None,
         "exact_quote": "\"Small ale, when you've a moment.\"",
         "volume": "pitched", "visibility": "overt", "conceal_from": []}


def test_an_unaimed_line_in_the_room_is_what_the_body_answers():
    found = _room_address_of({"dialogue_log": [ORDER]}, "Watisett",
                             ROSTER, SCENE, "taproom")
    assert found and found["exact_quote"] == ORDER["exact_quote"]
    assert found["speaker"] == "Sal Weatherby"


def test_a_concealed_line_never_reaches_it():
    hidden = dict(ORDER, visibility="concealed")
    assert _room_address_of({"dialogue_log": [hidden]}, "Watisett",
                            ROSTER, SCENE, "taproom") is None


def test_a_line_concealed_from_this_body_never_reaches_it():
    hidden = dict(ORDER, conceal_from=["Watisett"])
    assert _room_address_of({"dialogue_log": [hidden]}, "Watisett",
                            ROSTER, SCENE, "taproom") is None


def test_a_line_from_another_room_it_cannot_hear_does_not_reach_it():
    assert _room_address_of({"dialogue_log": [ORDER]}, "Watisett",
                            ROSTER, SCENE, "yard") is None


def test_a_speaker_outside_the_roster_is_not_an_authored_mind():
    """The same membership test `_character_address_of` makes: an unregistered
    voice is not somebody whose line demands an answer."""
    assert _room_address_of({"dialogue_log": [ORDER]}, "Watisett",
                            set(), SCENE, "taproom") is None


def test_the_body_does_not_answer_itself():
    own = dict(ORDER, speaker="Watisett")
    assert _room_address_of({"dialogue_log": [own]}, "Watisett",
                            {"watisett"}, SCENE, "taproom") is None


def test_the_last_hearable_line_wins():
    first = dict(ORDER, exact_quote="\"Anyone about?\"")
    found = _room_address_of({"dialogue_log": [first, ORDER]}, "Watisett",
                             ROSTER, SCENE, "taproom")
    assert found["exact_quote"] == ORDER["exact_quote"]
