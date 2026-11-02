"""A promise is stamped with the clock the beat that made it ENDS on.

`pending_act.seconds` is the one number `still_waiting_for` exists to carry
("You asked for that a quarter of an hour ago"). `_owed_clock_seconds` read
the stored clock and applied the beat's `state_diff.time` span to it -- but
`track_background_presences` runs in the `background_presences` domain,
after the `scene` domain has already written this beat's clock, so the span
was applied twice: the stamp ran one beat AHEAD of the story, a promise read
as 0 s old a beat later and was understated by one beat's span ever after.
Measured (review 2026-11-01, persist_background_memory F10): clock the scene
commit stores 1600.0, stamp 2200.0; a silent beat stored 1010.0 and stamped
1020.0.
"""

from __future__ import annotations

import time

from core.pipeline_context import ChatData, PipelineContext, TurnData
from persist.commit import presence_display_name, track_background_presences

KEEPER = "Tapster Ben"


def _ctx(temp_db, stored_end, span):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()))
    temp_db.wset(chat_id, "scene", {
        "location": "inn", "rooms": {"taproom": {"name": "Taproom"}},
        "positions": {"The Stranger": "taproom", KEEPER: "taproom"},
        "entities": {}, "attire": {}})
    temp_db.wset(chat_id, "background_presences",
                 {KEEPER: {"first_turn": 1, "last_turn": 4}})
    # What the scene domain has already written by the time this domain
    # runs: the clock this beat ENDS on.
    temp_db.wset(chat_id, "simulation_clock",
                 {"elapsed_seconds": stored_end, "display": "now"})
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 7, "An ale, please.", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=7,
                      player_input="An ale, please.", created=time.time()),
        cast=[], input="An ale, please.",
        director_resolve={"resolved_event": "The taproom hums.",
                          "dialogue_log": [],
                          "state_diff": ({"time": {"duration_seconds": span}}
                                         if span is not None else {})})
    ctx["background_react"] = {"selected": [KEEPER], "reactions": [{
        "name": KEEPER, "room": "taproom",
        "dialogue_log_entry": {"speaker": KEEPER,
                               "exact_quote": "In good time."},
        "still_owes": {"what": "a small ale", "to": "the stranger"}}]}
    return ctx


def _stamp(temp_db, ctx):
    track_background_presences(ctx, nonce=0)
    ledger = temp_db.wget(ctx.chat.id, "background_presences", {})
    rec = next(r for k, r in ledger.items()
               if presence_display_name(k, r) == KEEPER)
    return rec["pending_act"]["seconds"]


def test_a_ten_minute_beat_stamps_the_clock_it_ends_on(temp_db):
    assert _stamp(temp_db, _ctx(temp_db, 1600.0, 600)) == 1600.0


def test_a_silent_beat_stamps_the_clock_it_ends_on(temp_db):
    assert _stamp(temp_db, _ctx(temp_db, 1010.0, None)) == 1010.0
