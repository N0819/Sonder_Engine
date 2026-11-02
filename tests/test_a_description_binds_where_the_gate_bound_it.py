"""A description the player addressed binds, at commit, to the body the gate
bound it to -- even when that body has walked off by then.

`descriptor_bindings` mints a binding: "the man with the apron" is bound to
one co-present body by a seeded pick over the cohort standing in the
player's room, and the commit persists the phrase onto that body's sketch,
maps the address to it (`addressed_turns`, the promotion counter) and writes
its reply debt. The commit re-derived the binding AFTER the departure
applier had moved the bound body: the cohort no longer held it, the seed
picked the other body, and the phrase, the counter and a reply owed for a
question somebody else answered all landed on the wrong person (review
2026-11-01, persist_background_memory F6). The binding is derived once,
before anything this domain writes moves a body.
"""

from __future__ import annotations

import time

from core.pipeline_context import ChatData, PipelineContext, TurnData
from persist.commit import (descriptor_bindings, presence_display_name,
                            track_background_presences)

PHRASE = "the one with the apron"


def _ctx(temp_db):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()))
    temp_db.wset(chat_id, "scene", {
        "location": "inn",
        "rooms": {
            "taproom": {"name": "Taproom", "adjacent": [
                {"to": "cellar", "barrier": "open_door"}]},
            "cellar": {"name": "Cellar", "adjacent": [
                {"to": "taproom", "barrier": "open_door"}]}},
        "positions": {"The Stranger": "taproom", "Tapster Ben": "taproom",
                      "Cook Ama": "taproom"},
        "entities": {}, "attire": {}})
    temp_db.wset(chat_id, "background_presences", {
        "Tapster Ben": {"first_turn": 1, "last_turn": 4},
        "Cook Ama": {"first_turn": 1, "last_turn": 4}})
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 7, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=7,
                      player_input="You -- with the apron. An ale, please.",
                      created=time.time()),
        cast=[], input="You -- with the apron. An ale, please.",
        director_resolve={"resolved_event": "The taproom is busy.",
                          "dialogue_log": []})
    ctx["director_interpret"] = {"flow": {"addressed_to_refs": [PHRASE]}}
    return ctx


def test_the_bound_body_keeps_the_phrase_after_it_walks_off(temp_db):
    ctx = _ctx(temp_db)
    bound = descriptor_bindings(ctx, ctx.director_resolve)[PHRASE]
    other = ({"Tapster Ben", "Cook Ama"} - {bound}).pop()
    ctx["background_react"] = {"selected": [bound], "reactions": [{
        "name": bound, "room": "taproom", "goes_to": "cellar",
        "dialogue_log_entry": {"speaker": bound,
                               "exact_quote": "Right away.",
                               "intended_target": "The Stranger"}}]}
    track_background_presences(ctx, nonce=0)
    ledger = temp_db.wget(ctx.chat.id, "background_presences", {})
    by_name = {presence_display_name(k, r): r for k, r in ledger.items()
               if isinstance(r, dict)}
    assert temp_db.wget(ctx.chat.id, "scene")["positions"][bound] == "cellar"
    assert PHRASE in ((by_name[bound].get("sketch") or {})
                      .get("descriptors") or []), by_name[bound]
    assert not (by_name[other].get("sketch") or {}).get("descriptors"), \
        "the phrase was persisted onto the body that did not walk off"
    assert 7 not in (by_name[other].get("addressed_turns") or [])
    assert not by_name[other].get("pending_reply")
