"""A card route asks its warnings of the card the author WROTE.

`character_card_warnings` asks its semantic questions (a drive, goals,
capacity) of the card's normalization and its structural ones -- a station
with no name, more stations than are built, clothing at a region nothing
declares -- of the card as written, because normalization is exactly what
repairs those away (story_scene_schema F12a, audit 2026-11-01; the function
half is the story lane's, `tests/test_card_warnings_read_a_card_as_it_was_
written.py`). A route that hands it the normalized card can never show the
author those three: the four routes here hold the author's own input in the
request body, and now hand it over.
"""
from __future__ import annotations

import json
import time


def _written(name="Kit"):
    from story.character_schema import default_character_data
    sheet = default_character_data(name)
    sheet["embodiment"]["interior"] = [{"name": "the throat"},
                                       {"description": "a room nobody named"}]
    return sheet


def _named_nothing(out):
    return any("no name" in w for w in out["warnings"])


def test_creating_a_card(temp_db):
    from web import app
    assert _named_nothing(app.char_create({"sheet": _written()}))


def test_editing_a_card(temp_db):
    from web import app
    cid = app.char_create({"name": "Kit"})["id"]
    assert _named_nothing(app.char_edit(cid, {"sheet": _written()}))


def test_editing_a_storys_card(temp_db):
    from web import app
    ch = app.char_create({"name": "Kit"})["id"]
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Story", "", time.time()))
    temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
               (cid, ch, "active", "{}"))
    stored = json.loads(temp_db.q("SELECT sheet FROM characters WHERE id=?", (ch,),
                                  one=True)["sheet"])
    written = _written()
    written["identity"]["uid"] = stored["identity"]["uid"]
    assert _named_nothing(app.chat_char_card_put(cid, ch, {"sheet": written}))


def test_confirming_a_promotion(temp_db):
    from web import app
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Story", "", time.time()))
    assert _named_nothing(app.confirm_promotion(cid, {"name": "Kit", "sheet": _written()}))
