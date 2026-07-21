"""Regression test for the _asks_player trailing-"?" heuristic ending
NPC<->NPC exchanges (AUDIT_FINDINGS #18 / MEDIUM).

Any speech ending in "?" used to return True from _asks_player, stopping the
interaction loop as "awaiting player response" -- even when the question was
explicitly addressed to another NPC. That stranded NPC-to-NPC dialogue as if
the player had been spoken to.

Fix: the trailing-"?" fallback applies only when interaction.addresses is empty
or names a player alias; never when it names a registered cast member.
"""

from __future__ import annotations

import json
import time

from character_schema import default_character_data
from pipeline_context import ChatData

from agents.common import _asks_player


def _cast(temp_db, names):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("T", "", time.time()),
    )
    for n in names:
        cid = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) VALUES(?,?,?,?,?)",
            (n, json.dumps(default_character_data(n)), "{}", time.time(), f"char_{n}"),
        )
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
            (chat_id, cid, "active", "{}"),
        )
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,),
    )
    chat = ChatData(id=chat_id, name="T", persona_id=None, lorebook_id=None,
                    scenario="", created=time.time())
    return chat, cast


def _question_to(target):
    return {
        "interaction": {"addresses": [target] if target else []},
        "sequence": [{"type": "speech", "text": "Are you sure about this?"}],
    }


def test_question_to_another_npc_does_not_await_player(temp_db):
    chat, cast = _cast(temp_db, ["Reya", "Kael"])
    # Reya asks Kael a question -- the loop must not stop as "awaiting player".
    assert _asks_player(_question_to("Kael"), chat, cast) is False


def test_question_with_no_address_still_awaits_player(temp_db):
    chat, cast = _cast(temp_db, ["Reya", "Kael"])
    assert _asks_player(_question_to(None), chat, cast) is True


def test_question_addressed_to_player_alias_awaits_player(temp_db):
    chat, cast = _cast(temp_db, ["Reya", "Kael"])
    assert _asks_player(_question_to("you"), chat, cast) is True


def test_statement_to_npc_never_awaits_player(temp_db):
    chat, cast = _cast(temp_db, ["Reya", "Kael"])
    result = {
        "interaction": {"addresses": ["Kael"]},
        "sequence": [{"type": "speech", "text": "Stand down."}],
    }
    assert _asks_player(result, chat, cast) is False
