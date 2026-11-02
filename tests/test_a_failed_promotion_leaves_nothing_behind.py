"""A promotion lands whole or not at all.

`promote_background_character` INSERTed the `characters` row, the
`chat_chars` row (status 'active'), the relationship graph, the scene
position, mutual recognition and the seed memories one statement at a time
-- each auto-committed, because neither caller (the confirm route, the commit
tail's landing) holds a transaction -- and only then raised "Charter
promotion binding could not be saved" when the charter body was gone from the
registry by binding time. The story kept an active character with a
position, recognition edges and memories, the presence record of the same
name stayed tracked, and the charter kept simulating the now-unbound body:
one person, two simulations. With auto-promote on, every later beat
re-drafted the record (two `utility` calls, ~27 s each) and the landing was
refused by the name collision the half-made character created (review
2026-11-01, persist_background_memory F5).
"""

from __future__ import annotations

import time

import pytest

import world.charter_runtime as charter_runtime
from persist.commit import _mint_presence_uid, promote_background_character
from story.character_schema import default_character_data

BUNDLE = {"charter": "millers", "body": "b17", "place": "mill",
          "handoff": {}, "social_names": {}}
#: The key a charter-bound record is filed under (the ledger folds any other
#: spelling onto it on load).
MARA = _mint_presence_uid("charter:millers:b17")


def _story(temp_db):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Test", "", time.time()))
    temp_db.wset(cid, "scene", {"rooms": {"mill": {"name": "Mill"}},
                                "positions": {}, "entities": {},
                                "attire": {}})
    temp_db.wset(cid, "background_presences", {MARA: {
        "uid": MARA, "name": "Mara", "first_turn": 1, "last_turn": 9,
        "dialogue_turns": [3, 5, 9],
        "charter_refs": [{"charter": "millers", "body": "b17"}]}})
    return cid


def test_a_binding_that_cannot_be_saved_writes_nothing(temp_db, monkeypatch):
    cid = _story(temp_db)
    monkeypatch.setattr(charter_runtime, "promotion_bundle",
                        lambda *a, **k: dict(BUNDLE))
    monkeypatch.setattr(charter_runtime, "bind_promoted_character",
                        lambda *a, **k: False)
    with pytest.raises(RuntimeError, match="binding could not be saved"):
        promote_background_character(
            cid, MARA, sheet=default_character_data("Mara"),
            memory_seeds=["I kept the mill wheel turning."], promoted_turn=9)
    assert temp_db.q("SELECT id FROM characters") == []
    assert temp_db.q("SELECT char_id FROM chat_chars WHERE chat_id=?",
                     (cid,)) == []
    assert temp_db.q("SELECT id FROM memories WHERE chat_id=?", (cid,)) == []
    assert "Mara" not in (temp_db.wget(cid, "scene", {}).get("positions")
                          or {})
    assert MARA in temp_db.wget(cid, "background_presences", {})


def test_a_promotion_that_binds_lands_every_write(temp_db, monkeypatch):
    cid = _story(temp_db)
    monkeypatch.setattr(charter_runtime, "promotion_bundle",
                        lambda *a, **k: dict(BUNDLE))
    monkeypatch.setattr(charter_runtime, "bind_promoted_character",
                        lambda *a, **k: True)
    char_id = promote_background_character(
        cid, MARA, sheet=default_character_data("Mara"),
        memory_seeds=["I kept the mill wheel turning."], promoted_turn=9)
    assert temp_db.q("SELECT status FROM chat_chars WHERE chat_id=? AND "
                     "char_id=?", (cid, char_id), one=True)["status"] == \
        "active"
    seeds = temp_db.q("SELECT content, event_key, char_id FROM memories "
                      "WHERE chat_id=?", (cid,))
    assert [r["content"] for r in seeds] == ["I kept the mill wheel turning."]
    assert seeds[0]["char_id"] == char_id
    assert seeds[0]["event_key"] == "promotion:%s:%s:0" % (cid, char_id)
    assert temp_db.wget(cid, "scene", {})["positions"]["Mara"] == "mill"
    assert MARA not in temp_db.wget(cid, "background_presences", {})
