"""A story card's save keeps the identity key the character is played under.

`normalize_character_data` mints a fresh `char_<hex>` for a card with no
uid, on every call -- so the story-card editor, fed a normalized sheet by
`GET /api/chats/{cid}`, sends a minted uid back on every save. The route only
checked a uid the stored card had authored, so for a uid-less card the minted
one was WRITTEN, and from then on `authored_uid` found it: `cast_entity_id`
flipped from `character:<row id>` to `char_<hex>` and `identity_key` from the
casefolded name to the uid -- orphaning every circle membership earned in
play (audit 2026-11-01, story_scene_schema F2; 6 of 183 attachments on the
owner's database read a uid-less effective card).

A minted uid is not authored. Whatever the card authored -- in its identity
block or at its top level -- is immutable; a card that authored none keeps
none.
"""
from __future__ import annotations

import json
import time

import pytest
from fastapi import HTTPException


def _attached(db, raw_sheet):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Story", "", time.time()))
    ch = db.qi("INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
               ("Mara Quill", json.dumps(raw_sheet), "{}", time.time()))
    db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
          (cid, ch, "active", "{}"))
    return cid, ch


def _stored(db, cid, ch):
    return json.loads(db.q("SELECT sheet FROM chat_chars WHERE chat_id=? AND char_id=?",
                           (cid, ch), one=True)["sheet"])


def _uidless():
    from story.character_schema import default_character_data
    sheet = default_character_data("Mara Quill")
    sheet["identity"].pop("uid", None)
    return sheet


def test_the_editors_minted_uid_is_not_written(temp_db):
    from mind.knowledge_circles import identity_key
    from story.character_schema import cast_entity_id, normalize_character_data
    from web import app

    cid, ch = _attached(temp_db, _uidless())
    # What the editor holds: the chat payload's normalized card, uid minted.
    edited = normalize_character_data(_uidless())
    assert edited["identity"]["uid"]
    edited["psychology"]["drive"]["essence"] = "to be believed"

    app.chat_char_card_put(cid, ch, {"sheet": edited})

    stored = _stored(temp_db, cid, ch)
    assert not stored["identity"].get("uid") and not stored.get("uid")
    assert stored["psychology"]["drive"]["essence"] == "to be believed"
    assert cast_entity_id(stored, ch) == f"character:{ch}"
    assert identity_key(stored) == "mara quill"


def test_a_second_save_still_mints_nothing(temp_db):
    """The editor reopens on the story's own card now, normalized -- so the
    second save carries a NEW minted uid. It is not authored either."""
    from story.character_schema import cast_entity_id, normalize_character_data
    from web import app

    cid, ch = _attached(temp_db, _uidless())
    app.chat_char_card_put(cid, ch, {"sheet": normalize_character_data(_uidless())})
    reopened = normalize_character_data(_stored(temp_db, cid, ch))
    assert reopened["identity"]["uid"]
    app.chat_char_card_put(cid, ch, {"sheet": reopened})
    assert cast_entity_id(_stored(temp_db, cid, ch), ch) == f"character:{ch}"


def test_an_authored_uid_stays_and_cannot_be_changed(temp_db):
    from story.character_schema import default_character_data, normalize_character_data
    from web import app

    sheet = default_character_data("Mara Quill")
    sheet["identity"]["uid"] = "char_authored"
    cid, ch = _attached(temp_db, sheet)

    other = normalize_character_data(sheet)
    other["identity"]["uid"] = "char_someone_else"
    with pytest.raises(HTTPException) as refused:
        app.chat_char_card_put(cid, ch, {"sheet": other})
    assert refused.value.status_code == 400

    app.chat_char_card_put(cid, ch, {"sheet": normalize_character_data(sheet)})
    assert _stored(temp_db, cid, ch)["identity"]["uid"] == "char_authored"


def test_a_uid_authored_at_the_top_level_is_just_as_immutable(temp_db):
    """`authored_uid` reads the top-level spelling a flattened card uses, and
    so does the guard: the identity block alone missed it, and a different
    uid in the body was written over it."""
    from story.character_schema import normalize_character_data
    from web import app

    flat = _uidless()
    flat["uid"] = "char_flat"
    cid, ch = _attached(temp_db, flat)

    other = normalize_character_data(flat)
    assert other["identity"]["uid"] == "char_flat"
    other["identity"]["uid"] = "char_someone_else"
    with pytest.raises(HTTPException) as refused:
        app.chat_char_card_put(cid, ch, {"sheet": other})
    assert refused.value.status_code == 400
