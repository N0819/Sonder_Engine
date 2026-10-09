"""A captured payload is what the call SENT, never what its caller made of it
afterwards.

Every sink a provider exchange lands in keeps it past the call that made it
-- a step's until the step saves (`runtime._flush_exchanges`), a quick
start's until its failed-setup record is written -- and only then is the
payload serialised and hashed (`llm_capture._payload_hashes`). Kept by
reference, a payload its caller went on changing was captured as it stood
when the record was written. The room designer hands every step the same
live `draft` and keeps building it, so all 29 multi-step designer runs in the
2026-10-08 play database (chats 154-166) carried ONE draft hash across their
steps: each step's capture showed the finished draft, and what any step was
actually sent could not be read back. `pipeline_context.sent_payload` takes
the copy at call time, in the one funnel every deferred capture passes
through (`note_step_exchange`).
"""

from __future__ import annotations

import json
import time

from agents import director_rooms, runtime
from core.pipeline_context import current_exchange_sink, current_step_key
from llm.llm_quality import note_provider_exchange
from persist import llm_capture


SCENE = {
    "rooms": {
        "hall": {"name": "Hall", "desc": "A hall.", "extent": {"w": 6, "d": 4},
                 "adjacent": [{"to": "study", "barrier": "open", "dir": "n"}]},
        "study": {"name": "Study", "desc": "A study.", "adjacent": [
            {"to": "hall", "barrier": "open", "dir": "s"}]},
    },
    "positions": {},
}


def test_a_payload_changed_after_its_call_is_captured_as_it_was_sent(temp_db):
    temp_db.set_setting("llm_capture_enabled", "1")
    seen = []
    token = current_exchange_sink.set(seen.append)
    payload = {"draft": {"rooms": {"gallery": {"name": "Gallery"}}}, "step": 1}
    try:
        note_provider_exchange(role="director_rooms", system="S", payload=payload,
                               response="{}", ok=True, started=time.time())
    finally:
        current_exchange_sink.reset(token)
    # The caller goes on building what it sent, as the room designer does.
    payload["draft"]["rooms"]["gallery"]["anchors"] = {"rail": {"dir": "n"}}
    payload["draft"]["rooms"]["cellar"] = {"name": "Cellar"}
    payload["step"] = 2

    (entry,) = seen
    assert entry["payload"] == {"draft": {"rooms": {"gallery": {"name": "Gallery"}}},
                                "step": 1}


def test_with_the_capture_off_no_copy_is_taken(temp_db):
    """Off by default, the capture writes nothing, and the copy nothing would
    read cost 2.4-6 ms on the largest payloads, on every call of ordinary
    play (round one's review, 2026-10-08): the sink gets what was sent."""
    temp_db.set_setting("llm_capture_enabled", "")
    seen = []
    token = current_exchange_sink.set(seen.append)
    payload = {"draft": {"rooms": {"gallery": {"name": "Gallery"}}}, "step": 1}
    try:
        note_provider_exchange(role="director_rooms", system="S", payload=payload,
                               response="{}", ok=True, started=time.time())
    finally:
        current_exchange_sink.reset(token)
    (entry,) = seen
    assert entry["payload"] is payload


def test_a_quick_starts_record_keeps_what_each_call_was_sent_with_the_capture_off(temp_db):
    """A quick start's failed-setup record is written whatever the capture
    says (`greetings._write_failed_setup`), so its sink keeps every payload
    as it was SENT even with the capture off: copied only for the capture, a
    payload changed after its call was filed as changed (round two's review,
    2026-10-08)."""
    from story.greetings import _recording_exchanges, _trimmed_exchanges
    temp_db.set_setting("llm_capture_enabled", "")
    assert not llm_capture.capture_enabled()
    payload = {"town_plan": {"rooms": ["a"]}}
    with _recording_exchanges() as collected:
        note_provider_exchange(role="utility", system="S", payload=payload,
                               response="{}", ok=True, started=time.time())
        payload["town_plan"]["rooms"].append("b")      # the caller goes on
    (entry,) = _trimmed_exchanges(collected)
    assert entry["payload"] == {"town_plan": {"rooms": ["a"]}}


class _Step:
    """What the runtime's capture flush reads off a context, and the sink a
    step arms (`runtime._run_step`)."""

    def __init__(self, turn_id):
        self.turn_id = turn_id
        self.exchanges = []

    def note_exchange(self, entry):
        self.exchanges.append({"step_key": current_step_key.get(), **entry})

    def exchanges_for_step(self, key):
        return [dict(e) for e in self.exchanges if e.get("step_key") == key]


def test_each_step_of_a_designer_run_is_captured_with_the_draft_it_was_sent(temp_db):
    temp_db.set_setting("llm_capture_enabled", "1")
    temp_db.set_setting("llm_capture_bodies", "full")
    chat_id = temp_db.qi("INSERT INTO chats(name,created) VALUES('t',0)")
    turn_id = temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
                         "VALUES(?,0,'hi',0)", (chat_id,))
    steps = iter([
        {"calls": [{"tool": "draft_room", "args": {"room_id": "gallery", "room": {
            "name": "Gallery", "desc": "A narrow gallery.", "extent": {"w": 4, "d": 3},
            "adjacent": [{"to": "hall", "barrier": "open", "dir": "n"}]}}}]},
        {"calls": [{"tool": "draft_room", "args": {"room_id": "gallery", "room": {
            "anchors": {"rail": {"desc": "an iron rail", "dir": "s",
                                 "height": "waist", "footprint": "run"}}}}}]},
        {"calls": [{"tool": "submit", "args": {}}]},
    ])
    sent_drafts = []

    def call(system, payload):
        # What `complete_validated_json` does with every call it makes.
        sent_drafts.append(json.dumps(payload["draft"], ensure_ascii=False,
                                      sort_keys=True))
        note_provider_exchange(role="director_rooms", system=system, payload=payload,
                               response="{}", ok=True, started=time.time())
        return next(steps)

    ctx = _Step(turn_id)
    sink = current_exchange_sink.set(ctx.note_exchange)
    key = current_step_key.set("director_resolve")
    try:
        director_rooms.design_rooms(None, SCENE, {"prose": ""}, "sheet", ["gallery"],
                                    call, {})
    finally:
        current_step_key.reset(key)
        current_exchange_sink.reset(sink)
    runtime._flush_exchanges(ctx, "director_resolve")

    rows = llm_capture.exchanges_for_turn(turn_id)
    assert len(rows) == 3
    captured = [row["payload_hashes"]["draft"] for row in rows]
    assert len(set(captured)) == 3, "every step carried one draft hash"
    assert captured == [llm_capture.blob_hash(text) for text in sent_drafts]
