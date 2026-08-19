"""One bad co-player sheet must cost that co-player, not the chat.

`_load_extra_players` runs inside the `PipelineContext` construction -- before
`ensure_checkpoint` means anything and before any step runs -- so an exception
there is not a failed stage that can be resumed or rerolled. It is every turn
in the chat, at setup, for everyone.
"""

from __future__ import annotations

import json
import time

from agents.runtime import _load_extra_players
from story.character_schema import default_persona_data


def _persona(db, name, sheet=None):
    data = sheet if sheet is not None else json.dumps(
        default_persona_data(name))
    return db.qi(
        "INSERT INTO personas(name,sheet) VALUES(?,?)", (name, data))


def _chat_with_extras(db, extras):
    primary = _persona(db, "Primary")
    chat_id = db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) "
        "VALUES(?,?,?,?)", ("Co-op", "", time.time(), primary))
    for pid in extras:
        db.qi(
            "INSERT INTO chat_personas(chat_id,persona_id,status,frame_id) "
            "VALUES(?,?,?,?)", (chat_id, pid, "active", None))
    return chat_id


def test_a_readable_co_player_survives_an_unreadable_one(temp_db):
    broken = _persona(temp_db, "Broken", sheet="{not json at all")
    good = _persona(temp_db, "Good")
    chat_id = _chat_with_extras(temp_db, [broken, good])

    extras = _load_extra_players(chat_id, 1, None)

    assert [e["persona_id"] for e in extras] == [good]


def test_every_co_player_unreadable_is_still_a_running_turn(temp_db):
    broken = _persona(temp_db, "Broken", sheet="")
    chat_id = _chat_with_extras(temp_db, [broken])
    assert _load_extra_players(chat_id, 1, None) == []
