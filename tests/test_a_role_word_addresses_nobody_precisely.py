"""A line aimed at "the trader" in a market of traders is not a precise
address to every trader.

`_presence_addressed_match` accepts the title-stripped ref inside the name
("Tate" names Trader Tate). `intended_target` reaches it uncanonicalised --
the containment arm's own docstring says it is safe only after
`_flow_addressed_refs` has bound the ref -- so a ref that strips to the word
every holder of a post shares matched each of them. Each was then an
addressee the gate forced past `max_reactors`, and at commit each one within
reach graded a WHISPER "to its addressee" in full and stored the breathed
words as the reply it owes (review 2026-11-01, persist_background_memory F2,
reproduced: Trader Bob, Trader Ann and Trader Tate all matched; the Cook did
not). The comment at the matcher records the same class once before: one
sleeve-grab became a 44-strong forced chorus (chat 95 turn 3043).

A word this story's tracked names hold in common is the post's name
(`_shared_name_words`), so it singles nobody out; a ref made only of such
words is not a precise address. The full name, and a part only one name
holds, still are.
"""

from __future__ import annotations

import json
import time

from core.pipeline_context import ChatData, PipelineContext, TurnData
from persist.commit import (_character_address_of, _presence_addressed_match,
                            _shared_name_words, pick_voice_demand,
                            presence_display_name, track_background_presences)
from story.character_schema import default_character_data

ROOM = "market_square"
TRADERS = ("Trader Bob", "Trader Ann", "Trader Tate")
SHARED = _shared_name_words(TRADERS)


def test_a_shared_head_word_names_none_of_its_holders():
    assert "trader" in SHARED
    for name in TRADERS:
        assert not _presence_addressed_match(name, "the trader",
                                             shared=SHARED), name


def test_the_full_name_and_a_unique_part_still_name_their_body():
    assert _presence_addressed_match("Trader Tate", "Trader Tate",
                                     shared=SHARED)
    assert _presence_addressed_match("Trader Tate", "Tate", shared=SHARED)
    assert not _presence_addressed_match("Trader Bob", "Tate", shared=SHARED)


def test_a_lone_holder_of_a_word_is_still_named_by_it():
    assert _presence_addressed_match(
        "Trader Bob", "the trader",
        shared=_shared_name_words(["Trader Bob", "Cook Ama"]))


def _ctx(temp_db, line):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()))
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Sal Weatherby", json.dumps(default_character_data("Sal Weatherby")),
         "{}", time.time(), "char_sal"))
    temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
               "VALUES(?,?,?,?)", (chat_id, char_id, "active", "{}"))
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    positions = {name: ROOM for name in TRADERS}
    positions["Sal Weatherby"] = ROOM
    temp_db.wset(chat_id, "scene", {
        "location": "town", "rooms": {ROOM: {"name": "Market Square"}},
        "positions": positions, "entities": {}, "attire": {}})
    temp_db.wset(chat_id, "background_presences", {
        name: {"first_turn": 1, "last_turn": 4} for name in TRADERS})
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 7, "", time.time()))
    return PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=7, player_input="",
                      created=time.time()),
        cast=cast, input="",
        director_resolve={"resolved_event": "The square hums.",
                          "dialogue_log": [line]})


WHISPER = {"speaker": "Sal Weatherby", "intended_target": "the trader",
           "exact_quote": "The ledger is forged. Tell no one.",
           "volume": "whisper", "tone": "low"}


def test_a_whisper_to_the_trader_leaves_no_trader_owing_its_words(temp_db):
    ctx = _ctx(temp_db, WHISPER)
    roster = {"sal weatherby"}
    for name in TRADERS:
        assert _character_address_of(ctx.director_resolve, name, roster,
                                     shared=SHARED) is None, name
    track_background_presences(ctx, nonce=0)
    ledger = temp_db.wget(ctx.chat.id, "background_presences", {})
    owing = [presence_display_name(k, r) for k, r in ledger.items()
             if isinstance(r, dict) and r.get("pending_reply")]
    assert len(owing) <= 1, owing
    assert not any("forged" in str((r or {}).get("pending_reply"))
                   for r in ledger.values() if isinstance(r, dict))


def test_the_gate_forces_no_chorus_on_a_role_word(temp_db):
    ctx = _ctx(temp_db, WHISPER)
    out = pick_voice_demand(ctx, ctx.director_resolve, cap=1)
    assert len(out["picks"]) <= 1, out
