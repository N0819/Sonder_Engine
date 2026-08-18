"""The chat's PRIMARY persona must never be treated as an extra (co-)player.

chat_personas is for ADDITIONAL players; the primary lives in chats.persona_id
and is rendered by the main narrator / perceived as "player". But an import or a
hand-built chat can wrongly list the primary in chat_personas too, and it was
then double-rendered -- a spurious `extra:<pid>` perceiver identical to the
player's own view, and a wasted narrator_extra call every beat (observed live in
the impostor-crucible run). Both extra-player queries now exclude the primary.
"""

from __future__ import annotations

import json
import time

from agents.runtime import _load_extra_players, _chat_has_extra_players


def _persona(temp_db, name):
    from story.character_schema import default_persona_data
    return temp_db.qi("INSERT INTO personas(name,sheet,resource_uid) VALUES(?,?,?)",
                      (name, json.dumps(default_persona_data(name)), name))


def _chat(temp_db, primary_pid):
    return temp_db.qi(
        "INSERT INTO chats(name,persona_id,scenario,created) VALUES(?,?,?,?)",
        ("t", primary_pid, "", time.time()))


def test_primary_persona_in_chat_personas_is_not_an_extra(temp_db):
    pid = _persona(temp_db, "Vane")
    cid = _chat(temp_db, pid)
    # The scaffold/import mistake: primary also listed as an active co-player.
    temp_db.qi("INSERT INTO chat_personas(chat_id,persona_id,status,frame_id) "
               "VALUES(?,?,'active',NULL)", (cid, pid))

    assert _load_extra_players(cid, 0) == []
    assert _chat_has_extra_players(cid) is False


def test_a_genuine_extra_player_is_still_returned(temp_db):
    primary = _persona(temp_db, "Vane")
    coplayer = _persona(temp_db, "Marsh")
    cid = _chat(temp_db, primary)
    temp_db.qi("INSERT INTO chat_personas(chat_id,persona_id,status,frame_id) "
               "VALUES(?,?,'active',NULL)", (cid, primary))   # wrongly listed
    temp_db.qi("INSERT INTO chat_personas(chat_id,persona_id,status,frame_id) "
               "VALUES(?,?,'active',NULL)", (cid, coplayer))  # genuine extra

    extras = _load_extra_players(cid, 0)
    assert [e["persona_id"] for e in extras] == [coplayer]
    assert _chat_has_extra_players(cid) is True
