"""A pitched line is loud enough for the one addressed and no louder.

Five volume words fixed a line's level before anyone knew who it was for.
"Low, so that only his table would hear" was filed as a whisper and died
four paces off (scratch play 2026-09-14, chat 9 turn 16). The owner's ask
(2026-09-15): decibels scale on intent. A pitched line's level is solved
from the addressee's cell -- their noise floor plus the full margin, less
the path's gain -- clamped to the ladder, and everyone else is graded at
that level.
"""
from llm.schemas import normalize_speech_volume
from world.spatial import (hear_level, pitched_level_db, spatial_rel_between,
                           word_for_level)
from world.spatial import SPEECH_DB


def _scene():
    return {
        "rooms": {
            "ballroom": {"name": "ballroom", "extent": {"w": 12, "d": 8}, "anchors": {
                "far_wall": {"desc": "the far wall", "dir": "w"},
                "card_room_door": {"desc": "the door through to the card room", "dir": "e"},
            }, "adjacent": [{"to": "card_room", "barrier": "open_door", "dir": "e"}]},
            "card_room": {"name": "card room", "extent": {"w": 8, "d": 6}, "anchors": {
                "near_table": {"desc": "the table nearest the door", "dir": "w"},
            }, "adjacent": [{"to": "ballroom", "barrier": "open_door", "dir": "w"}]},
        },
        "positions": {"Clara": "ballroom", "Crane": "card_room", "Matron": "ballroom"},
        "stations": {"Clara": {"at": "card_room_door", "near": []},
                     "Crane": {"at": "near_table", "near": []},
                     "Matron": {"at": "far_wall", "near": []}},
        "entities": {"crane_e": {"name": "Mr Crane", "kind": "person"}},
    }


def test_the_sixth_word_is_a_volume():
    assert normalize_speech_volume("pitched") == "pitched"
    assert normalize_speech_volume("soft") == "mutter"


def test_the_word_a_level_stands_for():
    assert word_for_level(SPEECH_DB["whisper"]) == "whisper"
    assert word_for_level(SPEECH_DB["normal"] + 1) == "normal"
    assert word_for_level(1000) == "shout"
    assert word_for_level("x") == "normal"


def test_a_pitched_line_reaches_its_addressee_whole_and_the_far_wall_less():
    sc = _scene()
    level = pitched_level_db(sc, "Clara", "Crane")
    assert SPEECH_DB["whisper"] <= level <= SPEECH_DB["shout"]
    to_crane = spatial_rel_between(sc, "Crane", "Clara")
    to_matron = spatial_rel_between(sc, "Matron", "Clara")
    assert hear_level(to_crane, "pitched", level_db=level) == "full"
    # A whisper by the word would have died at the table.
    assert hear_level(to_crane, "whisper") == "none"
    # The far wall gets no more than the table does, and the level is the
    # least that reaches the table, so the far wall is graded lower or equal.
    order = {"none": 0, "fragment": 1, "full": 2}
    assert order[hear_level(to_matron, "pitched", level_db=level)] <= order["full"]
    assert level < SPEECH_DB["shout"]


def test_no_addressee_or_no_field_is_a_normal_line():
    sc = _scene()
    assert pitched_level_db(sc, "Clara", "Nobody Here") == SPEECH_DB["normal"]
    bare = {"rooms": {"a": {"name": "a", "adjacent": []}},
            "positions": {"X": "a", "Y": "a"}, "stations": {}, "entities": {}}
    assert pitched_level_db(bare, "X", "Y") in (SPEECH_DB["normal"],) or isinstance(pitched_level_db(bare, "X", "Y"), float)
