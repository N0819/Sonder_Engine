"""A destination written the way a person says it is the room whose words it
carries.

The whole-spelling fold (`room_spellings`) is exact: "Cope's yard" is neither
the id `copes_boatyard` nor the folded name `cope_s_boatyard`, so on scratch
chat 5 turn 27 (2026-09-14) the compiler filed a planning need for a room the
scene held, the Director refused the walk, commit minted an empty "Copes Yard"
beside the real yard, and the page had the player walk into the inn. The
words decide when the spelling does not: every word of the destination is a
word of the room's name or the tail of one, possessives joined, and exactly one
room answers. Two rooms answering is the same refusal the fold makes.
"""

from __future__ import annotations

import time

from core.pipeline_context import ChatData, PipelineContext, TurnData
from persist.commit import prepare_scene_commit
from world.spatial import room_name_words, scene_room_id
from world.structure import planned_context, plant_structure


SCENE = {"rooms": {
    "copes_boatyard": {"name": "Cope's Boatyard"},
    "boat_inn_taproom": {"name": "The Boat Inn Taproom"},
    "inn_cellar": {"name": "Inn Cellar & Pantry"},
    "village_wharf": {"name": "Village Wharf"},
}}


def test_a_possessive_folds_to_one_word_however_it_was_spelled():
    assert room_name_words("Cope's Boatyard") == ("copes", "boatyard")
    assert room_name_words("cope_s_boatyard") == ("copes", "boatyard")
    assert room_name_words("copes_boatyard") == ("copes", "boatyard")
    assert room_name_words("The Boat Inn") == ("boat", "inn")


def test_the_yard_the_director_spelled_its_own_way_is_the_scenes_yard():
    assert scene_room_id(SCENE, "copes_yard") == "copes_boatyard"
    assert scene_room_id(SCENE, "Cope's yard") == "copes_boatyard"
    assert scene_room_id(SCENE, "the boat inn") == "boat_inn_taproom"


def test_a_word_two_rooms_answer_to_names_neither():
    assert scene_room_id(SCENE, "the inn") == ""


def test_the_exact_fold_still_wins_over_the_words():
    scene = {"rooms": {"yard": {"name": "The Yard"},
                       "copes_boatyard": {"name": "Cope's Boatyard"}}}
    assert scene_room_id(scene, "the yard") == "yard"


def test_the_plan_answers_to_its_rooms_words_too(temp_db):
    cid = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Words", "", time.time()))
    plant_structure(cid, {"key": "blackwater", "max_planned": 8, "grammar": []}, {
        "copes_boatyard": {"name": "Cope's Boatyard", "purpose": "boats",
                           "access": "public", "adjacent": [], "frontier": []},
        "village_wharf": {"name": "Village Wharf", "purpose": "trade",
                          "access": "public", "adjacent": [], "frontier": []},
    })
    hit = planned_context(cid, "copes_yard")
    assert hit and hit["room_uid"] == "copes_boatyard"
    assert planned_context(cid, "nowhere in particular") is None


def _ctx(temp_db, to_room, refused):
    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Refused", "", time.time()))
    temp_db.wset(chat_id, "scene", {
        "rooms": {"boat_inn": {"name": "The Boat Inn", "adjacent": []}},
        "positions": {"Nan": "boat_inn"},
    })
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Refused", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=1, chat_id=chat_id, idx=4, player_input="go",
                      created=time.time()),
        cast=[], input="go")
    ctx.director_interpret = {"movement": {"to_room": to_room, "mover": "Nan",
                                           "arrives": True}}
    sd = {}
    if refused:
        sd["movement_refused"] = [{"subject": "Nan", "to_room": to_room}]
    ctx.director_resolve = {"state_diff": sd}
    return ctx


def test_a_refused_walk_mints_no_room(temp_db):
    sc = (prepare_scene_commit(_ctx(temp_db, "nowhere_lane", True)) or {}).get("scene") or {}
    assert set(sc.get("rooms", {})) == {"boat_inn"}


def test_a_walk_the_director_let_happen_still_lands_somewhere(temp_db):
    sc = (prepare_scene_commit(_ctx(temp_db, "nowhere_lane", False)) or {}).get("scene") or {}
    assert "nowhere_lane" in sc.get("rooms", {})
