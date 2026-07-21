"""Regression tests for the interaction-loop micro-perception concealed-speech
leak (AUDIT_FINDINGS #2 / CRITICAL).

agents/loops.py's deterministic_micro_perception speech branch used to check
ONLY hear_level -- unlike the action branch right below it, which skips
visibility=='concealed'. A concealed NPC line was therefore delivered verbatim
to every in-earshot observer, including any observer named in the line's
conceal_from, then flowed into that observer's next character step, outcome
view, and durable "heard" memory.

Fix: the speech branch now skips delivery to any observer resolved (by id,
name, or uid) in the line's conceal_from, while still routing it to legitimate
recipients -- mirroring the action branch and the norm_sequence backstop.
"""

from __future__ import annotations

import json
import time

from character_schema import default_character_data
from pipeline_context import ChatData, PipelineContext, TurnData

from agents.loops import deterministic_micro_perception


def _setup(temp_db, names, room="room1"):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("T", "", time.time()),
    )
    ids = {}
    for n in names:
        cid = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) VALUES(?,?,?,?,?)",
            (n, json.dumps(default_character_data(n)), "{}", time.time(), f"char_{n}"),
        )
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
            (chat_id, cid, "active", "{}"),
        )
        ids[n] = cid
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,),
    )
    scene = {
        "location": "x", "time": "day",
        "rooms": {room: {"name": "Room 1", "adjacent": []}},
        "positions": {n: room for n in names},
        "entities": {}, "attire": {}, "overlays": {},
    }
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="T", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=1, chat_id=chat_id, idx=1, player_input="", created=time.time()),
        cast=cast, input="",
    )
    return ctx, ids, scene


def _delivered(views, ids, name):
    return " ".join(views.get(ids[name], []))


def test_concealed_speech_skips_conceal_from_observer_by_id(temp_db):
    ctx, ids, scene = _setup(temp_db, ["Reya", "Kael", "Mara"])
    result = {"sequence": [{
        "type": "speech", "text": "The gate opens at dawn.",
        "volume": "normal", "visibility": "concealed",
        "conceal_from": [ids["Kael"]],
    }]}

    views, perceived_by = deterministic_micro_perception(ctx, ids["Reya"], result, scene)

    # Concealed-from observer (Kael) must not receive the line at all.
    assert "dawn" not in _delivered(views, ids, "Kael")
    assert ids["Kael"] not in perceived_by
    # A legitimate co-present recipient (Mara) still hears it.
    assert "dawn" in _delivered(views, ids, "Mara")
    assert ids["Mara"] in perceived_by


def test_concealed_speech_skips_conceal_from_observer_by_name(temp_db):
    ctx, ids, scene = _setup(temp_db, ["Reya", "Kael", "Mara"])
    result = {"sequence": [{
        "type": "speech", "text": "The gate opens at dawn.",
        "volume": "normal", "visibility": "concealed",
        "conceal_from": ["Kael"],
    }]}

    views, _ = deterministic_micro_perception(ctx, ids["Reya"], result, scene)

    assert "dawn" not in _delivered(views, ids, "Kael")
    assert "dawn" in _delivered(views, ids, "Mara")


def test_overt_speech_still_reaches_everyone(temp_db):
    # Guard against over-blocking: an ordinary overt line must still be
    # delivered to all co-present observers.
    ctx, ids, scene = _setup(temp_db, ["Reya", "Kael", "Mara"])
    result = {"sequence": [{
        "type": "speech", "text": "The gate opens at dawn.",
        "volume": "normal", "visibility": "overt", "conceal_from": [],
    }]}

    views, _ = deterministic_micro_perception(ctx, ids["Reya"], result, scene)

    assert "dawn" in _delivered(views, ids, "Kael")
    assert "dawn" in _delivered(views, ids, "Mara")
