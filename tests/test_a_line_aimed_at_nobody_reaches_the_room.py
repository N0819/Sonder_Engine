"""A line nobody was named for is addressed to the room it was spoken in.

`addressed_rooms` fed the gate's place-addressed trigger from the PLAYER's
lines only (`is_player_speaker`, twice) and deliberately excluded the room the
speaker stands in. Between them, a line spoken aloud to no one in particular
reached nobody at all -- for a character always, and for the player whenever
they did not name someone.

Measured (Aldermill, fourth run, 2026-09-19, turn idx 15): Sal Weatherby --
"know how a place really works; asks the people nobody asks" -- leaned off a
bench in the Wheel and Bushel, raised two fingers at the floor staff and said

    "Small ale, when you've a moment."

`intended_target` came back null. Five presences resolve into that taproom --
Host Pennytonwood (innkeeper), Robanot Appleytonwood (tapster), a cook, an
ostler, one more -- and `background_react` stayed `fired: false`. It was the
first thing either character had asked of anybody in 220 beats across four
runs, and an inn with a tapster in it did not answer an order for a drink.

THE CLASS: you say "small ale" into a room and whoever is working there deals
with it. Who is speaking does not change that -- the firewall does not care
whether a voice belongs to a player, and the room's occupants hear it either
way -- so the player-only filter goes and the speaker's own room counts.

WEIGHT, NOT FORCE. `place_addressed` ranks below a precise address and never
forces the slot: the cap still stands and a room is answered by one person.
"""

import types

import persist.commit as commit


#: Sal is a REGISTERED character, which is what makes her line an authored
#: mind's. A background presence's unaimed line must not mark a room -- one
#: presence answering another is padding, and `test_tavern_six_turn_story`
#: holds that line -- so the roster membership is load-bearing here.
CAST = [{"id": 1, "sheet": '{"identity": {"name": "Sal Weatherby"}}'}]


def _ctx(chat_id=1):
    chat = {"id": chat_id, "persona_id": 1}
    return types.SimpleNamespace(
        chat=chat, turn=types.SimpleNamespace(idx=15, frame_id=2),
        cast=CAST, extra_players=[], get=lambda k, d=None: d)


SCENE = {
    "rooms": {"taproom": {"name": "Wheel and Bushel Taproom"},
              "kitchen": {"name": "Inn Kitchen"}},
    "positions": {"Sal Weatherby": "taproom"},
}


def _rooms(dialogue, speaker_room="taproom"):
    return commit.addressed_rooms(
        _ctx(), {"dialogue_log": dialogue}, SCENE, speaker_room)


def test_a_characters_unaimed_line_addresses_her_own_room():
    rooms = _rooms([{"speaker": "Sal Weatherby",
                     "exact_quote": "\"Small ale, when you've a moment.\"",
                     "intended_target": None, "visibility": "overt"}])
    assert "taproom" in rooms, (
        "an order called into a room with a tapster in it must reach him")


def test_a_named_target_still_wins_and_the_room_is_not_flooded():
    """A line that DOES name somebody is a precise address and needs no help
    from the room; adding the room as well would make every aimed line a
    general summons."""
    rooms = _rooms([{"speaker": "Sal Weatherby", "exact_quote": "\"You.\"",
                     "intended_target": "Robanot Appleytonwood",
                     "visibility": "overt"}])
    assert "taproom" not in rooms


def test_a_characters_aimed_line_does_not_mark_another_room():
    """CALLING THROUGH A DOOR AT A ROOM BY NAME STAYS THE PLAYER'S
    AFFORDANCE, and this test asserted the opposite until the suite said so
    (`test_the_players_own_room_and_other_speakers_are_never_aimed`).

    The reason holds: a character aiming at a named BODY is already covered
    by the gate's precise-address trigger, so letting any speaker's aimed
    line mark a whole room would turn every cross-room exchange into a
    general summons. Only the UNAIMED case generalises -- a line nobody was
    named for, which no other trigger can reach."""
    rooms = _rooms([{"speaker": "Sal Weatherby", "exact_quote": "\"Hoy.\"",
                     "intended_target": "kitchen", "visibility": "overt"}])
    assert rooms == set()


def test_silence_addresses_nothing():
    assert _rooms([]) == set()


def test_a_background_presence_talking_to_itself_summons_nobody():
    """One presence answering another is padding. The tavern's Mira says
    "The lamb stew, if you're wise" to nobody in particular and must not
    conjure a second voice to take it up."""
    rooms = commit.addressed_rooms(
        _ctx(), {"dialogue_log": [{"speaker": "Mira",
                                   "exact_quote": "\"The lamb stew.\"",
                                   "intended_target": None,
                                   "visibility": "overt"}]},
        dict(SCENE, positions=dict(SCENE["positions"], Mira="taproom")),
        "taproom")
    assert rooms == set()
