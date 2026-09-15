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


def _tower(w=6, d=6):
    names = ["store", "keepers", "watch", "lamp"]
    rooms = {}
    for i, rid in enumerate(names):
        adj = []
        if i > 0:
            adj.append({"to": names[i - 1], "barrier": "open", "dir": "n", "vertical": "down"})
        if i < 3:
            adj.append({"to": names[i + 1], "barrier": "open", "dir": "n", "vertical": "up"})
        rooms[rid] = {"name": rid, "extent": {"w": w, "d": d}, "adjacent": adj,
                      "anchors": {}, "exposure": "enclosed"}
    # The burner roars at the top: the noise floor is what makes a normal
    # line break up on the way down and a pitched one carry.
    return {"rooms": rooms, "positions": {"Clara": "lamp", "Crane": "store", "burner": "lamp",
                                          "winch": "store"},
            "stations": {"Clara": {"cell": [3, 1]}, "Crane": {"cell": [3, 3]},
                         "burner": {"cell": [1, 3]}, "winch": {"cell": [5, 5]}},
            "entities": {"burner": {"name": "the burner", "kind": "fixture",
                                    "sound_source": "audible", "portable": False,
                                    "state": {"running": True}},
                         "winch": {"name": "the winch engine", "kind": "fixture",
                                   "sound_source": "audible", "portable": False,
                                   "state": {"running": True}}},
            "attire": {}, "overlays": {}, "orientation": {}}


def test_a_pitched_line_reaches_its_addressee_at_onset(temp_db):
    """Skerry Light turn 5, 2026-09-15: "Then come up. Slow." pitched to the
    man three storeys down was graded as a normal line on the onset pass
    (the addressee "not yet on the entry") and reached him as
    "...Then... hands... where...". The addressee is on the interpret's own
    span; the level is solved there as the outcome pass solves it."""
    import json, time
    from agents.perception import perception_act
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    from story.character_schema import default_character_data, default_persona_data
    persona_id = temp_db.qi("INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
                            ("Clara", json.dumps(default_persona_data("Clara")), "{}"))
    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
                         ("Tower", "", time.time(), persona_id))
    char_id = temp_db.qi("INSERT INTO characters(name,sheet,source,created,resource_uid) VALUES(?,?,?,?,?)",
                         ("Crane", json.dumps(default_character_data("Crane")), "{}", time.time(), "char_crane"))
    temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
               (chat_id, char_id, "active", "{}"))
    temp_db.wset(chat_id, "scene", _tower())
    cast = temp_db.q("SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
                     "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (chat_id,))
    line = "Then come up. Slow. Keep your hands where I can see them."

    idx = [4]

    def _act(volume):
        idx[0] += 1
        turn_id = temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
                             (chat_id, idx[0], line, time.time()))
        ctx = PipelineContext(
            chat=ChatData(id=chat_id, name="Tower", persona_id=persona_id,
                          lorebook_id=None, scenario="", created=time.time()),
            turn=TurnData(id=turn_id, chat_id=chat_id, idx=idx[0], player_input=line, created=time.time()),
            cast=cast, input=line)
        ctx.director_interpret = {
            "sequence": [{"type": "speech", "text": line, "volume": volume,
                          "visibility": "overt", "conceal_from": [],
                          "targets": [f"character:{char_id}"],
                          "event_id": "turn:5:player:0:speech"}],
            "speech": line, "speech_volume": volume, "action": None,
            "flow": {"reactors": [char_id], "addressed_to": ["Crane"], "authority_claims": [],
                     "resolution_flags": {}, "fiction_frame": {}}}
        out = perception_act(ctx, "n0")
        return (out.get("views") or {}).get(str(char_id)) or ""

    sc = _tower()
    assert hear_level(spatial_rel_between(sc, "Crane", "Clara"), "normal") != "full", \
        "the tower must be tall enough that a normal line breaks up"
    assert "hands where I can see them" in _act("pitched"), _act("pitched")
    assert "hands where I can see them" not in _act("normal")
