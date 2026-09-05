"""The Writers' Room's own calls are readable, on the same terms as a beat's.

`record_exchange` was called from `agents/runtime.py` and nowhere else, so
every pipeline stage and every Director specialist could be read and the
two agents a host most wants to read could not. All five play runs of
2026-09-05 named it; the caravanserai run counted it ("24 model calls of
author-facing work left no payload to read") and the flat run stated the
cause ("`llm_capture` records `agents/runtime.py` only").

The same recorder, the same content-addressed dedup, the same
off-by-default rule. A Room call is filed against THE TURN IN PLAY under a
`room:<phase>` step key, so one export reads in order: this beat happened,
then the room said this about it.
"""

import pytest

from persist import llm_capture, pipeline_trace
from story.room_calls import room_call


def _chat_with_a_turn(db):
    chat_id = db.qi("INSERT INTO chats(name,created) VALUES('t',0)")
    turn_id = db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
                    "VALUES(?,0,'hi',0)", (chat_id,))
    return chat_id, turn_id


def _seal(monkeypatch, answer='{"reply": "ok"}'):
    from llm import providers
    monkeypatch.setattr(providers, "chat_complete",
                        lambda *a, **k: answer, raising=False)
    monkeypatch.setattr(providers, "agent_models",
                        lambda: {"story_planner": {"model": "a-model"}},
                        raising=False)


def test_a_room_call_is_not_recorded_when_capture_is_off(temp_db, monkeypatch):
    """The default. The room is as silent as everything else is."""
    from core import db
    _seal(monkeypatch)
    chat_id, turn_id = _chat_with_a_turn(db)
    with llm_capture.room_capture(chat_id, "planner"):
        room_call("story_planner", "SHEET", {"task": "recap"})
    assert llm_capture.exchanges_for_turn(turn_id) == []
    export = pipeline_trace.export_turn_debug(turn_id)
    assert export["room_calls_captured"] == 0
    assert not [e for e in export["timeline"] if e.get("origin") == "room"]


def test_a_room_call_appears_in_the_turns_debug_export_with_its_payload(
        temp_db, monkeypatch):
    from core import db
    _seal(monkeypatch)
    db.set_setting("llm_capture_enabled", "1")
    db.set_setting("llm_capture_bodies", "full")
    chat_id, turn_id = _chat_with_a_turn(db)

    with llm_capture.room_capture(chat_id, "planner"):
        room_call("story_planner", "PLANNER SHEET",
                  {"task": "recap", "bible": {"cast": ["Halvard"]}})

    export = pipeline_trace.export_turn_debug(turn_id)
    calls = [e for e in export["timeline"] if e["kind"] == "call"]
    assert len(calls) == 1
    call = calls[0]
    assert call["origin"] == "room"
    assert call["room_phase"] == "planner"
    assert call["step"] == "room:planner"
    assert call["model"] == "a-model"
    assert call["sent"]["system"] == "PLANNER SHEET", (
        "what the room was SENT is the half the play runs asked for")
    assert call["sent"]["payload"]["bible"] == {"cast": ["Halvard"]}
    assert call["received"]["output"] == {"reply": "ok"}
    assert export["room_calls_captured"] == 1


def test_a_room_call_outside_a_scope_records_nothing(temp_db, monkeypatch):
    """Capture is armed by the seam that knows which chat is being planned.
    A call with no scope has no chat and no turn to belong to."""
    from core import db
    _seal(monkeypatch)
    db.set_setting("llm_capture_enabled", "1")
    _chat, turn_id = _chat_with_a_turn(db)
    room_call("story_planner", "SHEET", {"task": "recap"})
    assert llm_capture.exchanges_for_turn(turn_id) == []


def test_a_failed_room_call_is_recorded_with_its_error(temp_db, monkeypatch):
    """The call a reader most wants is the one that raised."""
    from core import db
    from llm import providers

    def boom(*a, **k):
        raise RuntimeError("no content in response")

    monkeypatch.setattr(providers, "chat_complete", boom, raising=False)
    monkeypatch.setattr(providers, "agent_models", lambda: {}, raising=False)
    db.set_setting("llm_capture_enabled", "1")
    chat_id, turn_id = _chat_with_a_turn(db)

    with pytest.raises(RuntimeError):
        with llm_capture.room_capture(chat_id, "dramaturge"):
            room_call("dramaturge", "SHEET", {"dial": 2})

    rows = llm_capture.exchanges_for_turn(turn_id)
    assert len(rows) == 1 and not rows[0]["ok"]
    assert "no content in response" in rows[0]["error"]
    assert rows[0]["step_key"] == "room:dramaturge"


def test_the_rooms_sheet_is_stored_once_across_a_whole_reply(
        temp_db, monkeypatch):
    """The dedup earns more here than anywhere: the room's tool table alone
    measured 15.6k characters on 2026-09-04, byte-identical on every step of
    every reply."""
    from core import db
    _seal(monkeypatch)
    db.set_setting("llm_capture_enabled", "1")
    db.set_setting("llm_capture_bodies", "full")
    chat_id, turn_id = _chat_with_a_turn(db)
    sheet = "TOOL TABLE " * 1000

    with llm_capture.room_capture(chat_id, "planner"):
        for step in range(6):
            room_call("story_planner", sheet, {"step": step, "task": "recap"})

    assert len(llm_capture.exchanges_for_turn(turn_id)) == 6
    stored = db.q("SELECT COUNT(*) AS n FROM llm_blobs WHERE hash=?",
                  (llm_capture.blob_hash(sheet),), one=True)["n"]
    assert stored == 1


def test_a_room_call_sorts_after_the_beat_it_was_about(temp_db, monkeypatch):
    """A room call is not a stage of the turn -- the panel is opened between
    beats -- so it is filed against the turn in play and reads after it."""
    from core import db
    _seal(monkeypatch)
    db.set_setting("llm_capture_enabled", "1")
    chat_id, turn_id = _chat_with_a_turn(db)
    llm_capture.record_exchange(turn_id=turn_id, step_key="narrator",
                               role="narrator", system="S", started=100.0,
                               payload={}, response={})
    with llm_capture.room_capture(chat_id, "planner"):
        room_call("story_planner", "SHEET", {"task": "recap"})

    order = [(e["step"], e.get("origin")) for e in
             pipeline_trace.export_turn_debug(turn_id)["timeline"]
             if e["kind"] == "call"]
    assert order == [("narrator", "pipeline"), ("room:planner", "room")]


def test_the_bible_fold_is_a_room_call_too(temp_db, monkeypatch):
    """Every model call the room makes, not only the Planner's."""
    from core import db
    from story import room_bible
    _seal(monkeypatch, answer='{"entries": []}')
    db.set_setting("llm_capture_enabled", "1")
    chat_id, turn_id = _chat_with_a_turn(db)

    with llm_capture.room_capture(chat_id, "planner"):
        room_bible._call("BIBLE SHEET", {"sections": []})

    rows = llm_capture.exchanges_for_turn(turn_id)
    assert [r["step_key"] for r in rows] == ["room:bible"], (
        "a fold names its own phase even inside a planner scope")
