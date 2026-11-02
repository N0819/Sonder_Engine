"""A presence is never promoted under a co-player's name.

Names are identity here: `scene.positions`, the cast, addressing and every
psychology write are keyed on them. `_refuse_name_collision` refused the
primary persona's name and every attached character's, and not the
co-players, who live in `chat_personas` -- so a presence tracked before a
co-player named "Bo" joined could be promoted to a second "Bo" sharing that
player's `positions` key, the cross-mind failure its own docstring names
(review 2026-11-01, persist_background_memory F21).
"""

from __future__ import annotations

import json
import time

import pytest

from persist.commit import _refuse_name_collision
from story.character_schema import default_persona_data


def _story(temp_db, status="active"):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Test", "", time.time()))
    pid = temp_db.qi("INSERT INTO personas(name,sheet) VALUES(?,?)",
                     ("Bo", json.dumps(default_persona_data("Bo"))))
    temp_db.qi("INSERT INTO chat_personas(chat_id,persona_id,status) "
               "VALUES(?,?,?)", (cid, pid, status))
    return cid


def test_a_co_players_name_is_taken(temp_db):
    cid = _story(temp_db)
    with pytest.raises(ValueError, match="Bo"):
        _refuse_name_collision(cid, "Bo")
    with pytest.raises(ValueError):
        _refuse_name_collision(cid, "bo")


def test_another_name_is_free(temp_db):
    cid = _story(temp_db)
    _refuse_name_collision(cid, "Mara")
