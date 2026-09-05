"""A fact the diff supplies is a record, not a need.

**PS18** (Salt Terraces, 2026-09-05). Turn 0 wrote three `world_facts` ("Lake
Sarrat dried up a generation ago...", and two more). `wget(cid,
"world_facts")` was **null** at the end of the run, and the same commit warned
*"3 planning need(s) recorded: the beat reached for setting fact '...'"* --
the needs still `status: "open"` twenty turns later, one of them naming the
player herself. The Director had just written those facts; nothing stored
them anywhere.
"""

from __future__ import annotations

import time

from core.db import wget
from persist.commit import commit_world_facts, WORLD_FACTS_CAP
from core.pipeline_context import ChatData, PipelineContext, TurnData


def _ctx(temp_db, facts, *, idx=0, opening=True):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Terraces", "", time.time()))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, idx, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Terraces", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=idx, player_input="",
                      created=time.time()),
        cast=[], input="")
    result = {"state_diff": {"world_facts": facts}}
    if opening:
        ctx.director_establish = result
    else:
        ctx.director_resolve = result
    return ctx


_FACTS = [
    "Lake Sarrat dried up a generation ago and the terraces were abandoned.",
    {"fact": "Salt is cut from the pans by licence of the Ourmel works.",
     "source": {"kind": "director"}},
]


def test_the_opening_records_what_it_established(temp_db):
    ctx = _ctx(temp_db, _FACTS)
    out = commit_world_facts(ctx, nonce=0)

    assert out["recorded"] == 2
    ledger = wget(ctx.chat.id, "world_facts", [])
    assert [entry["fact"] for entry in ledger] == [
        _FACTS[0], _FACTS[1]["fact"]]
    assert ledger[1]["source"] == "director"
    assert all(entry["turn_idx"] == 0 for entry in ledger)


def test_a_fact_restated_is_not_a_second_fact(temp_db):
    ctx = _ctx(temp_db, _FACTS)
    commit_world_facts(ctx, nonce=0)
    again = _ctx(temp_db, ["   Lake Sarrat dried up a generation ago and the "
                           "terraces were abandoned.  "], idx=4, opening=False)
    again.chat = ctx.chat
    again.turn = TurnData(id=ctx.turn.id, chat_id=ctx.chat.id, idx=4,
                          player_input="", created=time.time())
    out = commit_world_facts(again, nonce=0)

    assert out["recorded"] == 0
    assert len(wget(ctx.chat.id, "world_facts", [])) == 2


def test_the_ledger_is_capped_and_says_what_it_dropped(temp_db):
    ctx = _ctx(temp_db, ["fact number %d about this world" % n
                         for n in range(WORLD_FACTS_CAP + 3)])
    out = commit_world_facts(ctx, nonce=0)

    assert out["held"] == WORLD_FACTS_CAP
    ledger = wget(ctx.chat.id, "world_facts", [])
    assert ledger[0]["fact"] == "fact number 3 about this world"
