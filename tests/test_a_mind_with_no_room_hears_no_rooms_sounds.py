"""A sound scoped to a room reaches only a mind in that room -- and a mind
with no room is in none of them.

`composer.ambient_percepts` admitted a room-scoped event when `room and
observer_room and room != observer_room` was false, so an observer with NO
room failed the guard open and was handed every room's sounds: a cast member
attached but not placed (`character_room` -> None; perception still builds
its perceiver with `"room": None`) heard the hiss behind the vault door
(audit agents_composer F3, 2026-11-01), while `environment_percept(None, ...)`
already returns None ("A mind in unloaded space perceives NOTHING"). The
guard cannot judge that input, so it refuses it. A roomless event is scene
ambience and stays admitted to everyone, roomed or not.
"""

from agents.composer import ambient_percepts

VAULT = {"room": "vault", "detail": "a slow hiss behind the vault door"}


def test_a_mind_with_no_room_is_given_no_rooms_sound():
    assert ambient_percepts([VAULT], None) == []
    assert ambient_percepts([VAULT], "") == []
    assert ambient_percepts([dict(VAULT, room=None, room_id="vault")],
                            None) == []
    assert ambient_percepts([{"source_room": "vault", "detail": "a hiss"}],
                            None, order_key=500_000) == []


def test_the_room_the_sound_is_in_still_hears_it():
    [percept] = ambient_percepts([VAULT], "vault")
    assert "hiss" in percept.data["desc"]


def test_a_roomless_sound_is_ambience_for_every_mind():
    event = {"detail": "the whole ship hums"}
    assert ambient_percepts([event], None)
    assert ambient_percepts([event], "vault")
