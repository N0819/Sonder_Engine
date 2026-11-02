"""A name said in a line aimed at somebody else is a subject, not an address
-- at commit as at the gate -- and a name said where its holder cannot hear
it addresses nobody.

`addressed_turns` is the counter that earns a passer-by a character sheet
(`PLANNED_PROMOTION_ADDRESSED_THRESHOLD` is 2), and the commit accrued it on
the loose significant-word match alone. The demand gate drops that match
when the beat has a precise addressee ("A NAME IN A LINE AIMED AT SOMEONE
ELSE IS A SUBJECT", measured Harrowmere turn 4) and when the words did not
arrive (`address_reaches`); the writer applied neither. So "Has Nookfeller
been in today?", asked of the clerk, counted as turning toward Nookfeller at
the mill across town, and two such beats proposed him for promotion as
"turned to on 2 beats" (review 2026-11-01, persist_background_memory F7).
"""

from __future__ import annotations

import time

from core.pipeline_context import ChatData, PipelineContext, TurnData
from persist.commit import presence_display_name, track_background_presences


def _ctx(temp_db, words, refs=()):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()))
    temp_db.wset(chat_id, "scene", {
        "location": "town",
        "rooms": {"counting_house": {"name": "Counting House"},
                  "mill": {"name": "Mill"}},
        "positions": {"The Stranger": "counting_house",
                      "Clerk Pim": "counting_house",
                      "Reeve Nookfeller": "mill"},
        "entities": {}, "attire": {}})
    temp_db.wset(chat_id, "background_presences", {
        "Clerk Pim": {"first_turn": 1, "last_turn": 4},
        "Reeve Nookfeller": {"first_turn": 1, "last_turn": 4}})
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 7, words, time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=7, player_input=words,
                      created=time.time()),
        cast=[], input=words,
        director_resolve={"resolved_event": "Ink and ledgers.",
                          "dialogue_log": []})
    if refs:
        ctx["director_interpret"] = {"flow": {"addressed_to_refs": list(refs)}}
    ctx["background_react"] = {"selected": [], "reactions": []}
    return ctx


def _addressed(temp_db, ctx):
    track_background_presences(ctx, nonce=0)
    ledger = temp_db.wget(ctx.chat.id, "background_presences", {})
    return {presence_display_name(k, r): 7 in (r.get("addressed_turns") or [])
            for k, r in ledger.items() if isinstance(r, dict)}


def test_a_name_in_a_line_aimed_at_somebody_else_is_a_subject(temp_db):
    ctx = _ctx(temp_db, "Clerk, has Nookfeller been in today?",
               refs=["Clerk Pim"])
    seen = _addressed(temp_db, ctx)
    assert seen["Clerk Pim"] is True
    assert seen["Reeve Nookfeller"] is False, \
        "the subject of the question was counted as turned toward"


def test_a_name_said_out_of_its_holders_hearing_addresses_nobody(temp_db):
    ctx = _ctx(temp_db, "Nookfeller? Anyone seen Nookfeller?")
    assert _addressed(temp_db, ctx)["Reeve Nookfeller"] is False


def test_a_name_said_to_its_holder_still_counts(temp_db):
    """The loose match is kept for what it was for: a first name carrying
    an address to the one person in the room who holds it."""
    ctx = _ctx(temp_db, "Pim -- a word?")
    assert _addressed(temp_db, ctx)["Clerk Pim"] is True
