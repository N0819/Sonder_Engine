"""Two things that only share a word stay two things.

`_fold_duplicate_mints` folds a mint onto a standing record it names -- the
room ledger's duplicate floor, applied to entities -- and it matched on every
label either record answered to, aliases included. Saltmarsh Crossing
(2026-10-11, scratch chat 170): the player's "survey ledger" was minted with
the alias "ledger", so the harbour's lading book (`lading_ledger`,
"cloth-bound ledger", aliases "lading book", "running record", "ledger",
"book") was folded onto it on beat 8, its tally was filed on her ledger, and
by beat 14 her ledger carried a grain office's description.

The rule now: one side's own key or display name has to be something the
other answers to. Two records that each list the same word among their
aliases -- a kind's name -- are two things.
"""
from __future__ import annotations

import copy
import time

from core.pipeline_context import ChatData, PipelineContext, TurnData
from persist import commit


def _ctx(temp_db):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Ledgers", "", time.time()))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 8, "", time.time()))
    return PipelineContext(
        chat=ChatData(id=chat_id, name="Ledgers", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=8, player_input="",
                      created=time.time()),
        cast=[], input="")


SURVEY = {"name": "survey ledger", "kind": "book", "portable": True,
          "aliases": ["ledger"], "description": "her own survey book"}


def _prev():
    return {"rooms": {"harbour_office": {"name": "Harbour office"}},
            "positions": {"Agnes": "harbour_office", "agnes_ledger": "harbour_office"},
            "entities": {"agnes_ledger": dict(SURVEY)}}


def _fold(temp_db, mint_key, mint):
    prev = _prev()
    diff = {"entities": {mint_key: mint}, "positions": {mint_key: "harbour_office"}}
    sc = copy.deepcopy(prev)
    sc["entities"][mint_key] = copy.deepcopy(mint)
    sc["positions"][mint_key] = "harbour_office"
    ctx = _ctx(temp_db)
    return commit._fold_duplicate_mints(ctx, ctx.chat.id, sc, prev, diff), sc


def test_the_harbours_book_is_not_her_ledger(temp_db):
    folded, sc = _fold(temp_db, "lading_ledger", {
        "name": "cloth-bound ledger", "kind": "book",
        "aliases": ["lading book", "running record", "ledger", "book"],
        "description": "the harbour's running record of ladings"})
    assert folded == []
    assert sc["entities"]["lading_ledger"]["description"].startswith("the harbour's")
    assert sc["entities"]["agnes_ledger"]["description"] == "her own survey book"


def test_a_mint_called_by_her_ledgers_own_name_is_her_ledger(temp_db):
    folded, sc = _fold(temp_db, "ledger_2", {"name": "survey ledger", "kind": "book",
                                             "state": {"open": "at the tally"}})
    assert folded == [("ledger_2", "agnes_ledger")]
    assert sc["entities"]["agnes_ledger"]["state"] == {"open": "at the tally"}


def test_a_mint_answering_to_her_ledgers_name_is_her_ledger(temp_db):
    folded, _ = _fold(temp_db, "the_book", {"name": "the book", "kind": "book",
                                            "aliases": ["survey ledger"]})
    assert folded == [("the_book", "agnes_ledger")]


def test_a_mint_whose_own_name_she_answers_to_is_hers(temp_db):
    """The buzzer case, from the other side: a mint whose own name is a word
    the standing thing claims as its own."""
    folded, _ = _fold(temp_db, "ledger", {"name": "ledger", "kind": "book"})
    assert folded == [("ledger", "agnes_ledger")]
