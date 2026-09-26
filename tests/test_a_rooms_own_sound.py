"""A room's own sound is how the PLACE sounds to someone in it.

`rooms[rid]["sound"]` is written as heard in that room, echo and all, so
the engine must not lay the room's ring on top of the word a second time;
and it is what the place makes by itself -- not what someone there is doing,
and not the weather, which the engine hears from the sky. Both were measured
on the mood test stories (2026-09-26), where the owner found the gating
"entirely overzealous": a `faint` drip in a hushed 4x3 stone infirmary stood
at 58 dB wherever anyone stood, and a soprano's evening performance and the
night's rain were written into the opera house's rooms as standing noise
that never stopped."""
from __future__ import annotations

from world.spatial import db_of_power, sound_field


def _cell(surface=None, *, room_sound=True, thing=False):
    room = {"name": "infirmary", "extent": {"w": 4, "d": 3}, "anchors": {},
            "adjacent": [], "exposure": "enclosed"}
    if surface:
        room["surface"] = surface
    if room_sound:
        room["sound"] = {"level": "faint", "detail": "water dripping into a tin"}
    sc = {"rooms": {"infirmary": room}, "positions": {"A": "infirmary"},
          "stations": {"A": {"cell": [0, 0]}}, "entities": {}}
    if thing:
        sc["entities"] = {"tap": {"name": "a dripping tap", "sound_source": "faint"}}
        sc["positions"]["tap"] = "infirmary"
        sc["stations"]["tap"] = {"cell": [3, 2]}
    return sc


def _noise_db(sc):
    return db_of_power(sound_field(sc, "A").noise_at("A"))


def test_a_rooms_own_sound_already_carries_its_echo():
    from world.spatial import EVENT_DB, spreading_loss_db

    # The word names the sound one pace off. Where a ring holds the room the
    # level no longer falls with distance -- it stands at the ring -- and
    # that standing level is the word, not the word plus the ring: before
    # 2026-09-26 this corner read 52.9 dB, a faint drip at the loudness of
    # a conversation.
    word_db = EVENT_DB["faint"] - spreading_loss_db(1.0)
    bare = _noise_db(_cell("bare"))
    assert bare <= word_db + 1.0, (bare, word_db)
    # An ordinary room is unchanged: no ring, and the level falls away.
    assert _noise_db(_cell()) < word_db


def test_a_things_noise_still_rings_in_the_room_it_is_in():
    bare = _noise_db(_cell("bare", room_sound=False, thing=True))
    plain = _noise_db(_cell(room_sound=False, thing=True))
    assert bare > plain + 6.0, (bare, plain)


def test_the_planner_is_told_a_rooms_sound_is_the_places_own():
    from story.plot_packages import OPERATION_FIELDS

    text = OPERATION_FIELDS["plan_rooms"]["rooms"]
    assert "with nobody in it, whatever the weather" in text
    assert "the weather's, which the engine hears for itself" in text
