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


# ---------------------------------------------------------------------------
# The two agents the runs asked for
# ---------------------------------------------------------------------------
#
# The seam above was built and the callers were not wired to it: the Planner
# and the Dramaturge each still called `providers.chat_complete` directly, so
# the recorder existed and recorded nothing either of them did.


def test_the_planners_own_call_is_recorded(temp_db, monkeypatch):
    """Not `room_call` -- `agents/story_planner.py`'s own model call, which
    is the one every play run asked to read."""
    from core import db
    from agents import story_planner
    _seal(monkeypatch)
    db.set_setting("llm_capture_enabled", "1")
    db.set_setting("llm_capture_bodies", "full")
    chat_id, turn_id = _chat_with_a_turn(db)

    with llm_capture.room_capture(chat_id, "planner"):
        out = story_planner._call("PLANNER SHEET", {"task": {"kind": "fill"}},
                                  max_tokens=64)
    assert out == {"reply": "ok"}, "the seam returns what it always returned"

    export = pipeline_trace.export_turn_debug(turn_id)
    calls = [e for e in export["timeline"] if e["kind"] == "call"]
    assert [c["step"] for c in calls] == ["room:planner"]
    assert calls[0]["sent"]["system"] == "PLANNER SHEET"
    assert calls[0]["sent"]["payload"]["task"] == {"kind": "fill"}


def test_the_dramaturges_own_call_is_recorded(temp_db, monkeypatch):
    """And it names its own phase, so a pass reads apart from a reply."""
    from core import db
    from agents import dramaturge
    _seal(monkeypatch, answer='{"proposals": []}')
    db.set_setting("llm_capture_enabled", "1")
    chat_id, turn_id = _chat_with_a_turn(db)

    with llm_capture.room_capture(chat_id, "planner"):
        dramaturge._call("DRAMATURGE SHEET", {"dial": 2})

    rows = llm_capture.exchanges_for_turn(turn_id)
    assert [r["step_key"] for r in rows] == ["room:dramaturge"]


def test_neither_agent_records_when_capture_is_off(temp_db, monkeypatch):
    """Off by default, the same as every stage. The setting is the whole
    of the gate: wiring the seam did not turn anything on."""
    from core import db
    from agents import dramaturge, story_planner
    _seal(monkeypatch)
    chat_id, turn_id = _chat_with_a_turn(db)

    with llm_capture.room_capture(chat_id, "planner"):
        story_planner._call("SHEET", {"task": "recap"}, max_tokens=64)
        dramaturge._call("SHEET", {"dial": 1})

    assert llm_capture.exchanges_for_turn(turn_id) == []
    assert pipeline_trace.export_turn_debug(turn_id)["room_calls_captured"] == 0


def test_a_job_queued_from_the_commit_tail_arms_its_own_scope(
        temp_db, monkeypatch):
    """`core/jobs.py` clears turn-scoped contextvars by design and these
    jobs are submitted outside a reply, so a scope taken around the SUBMIT
    is not one the job body can see. It is armed inside the body, which is
    the only place it reaches the calls."""
    from core import db, jobs
    from agents import story_planner
    from story import mandates, room_bible, room_frontier, room_proposals
    _seal(monkeypatch)
    db.set_setting("llm_capture_enabled", "1")
    chat_id, turn_id = _chat_with_a_turn(db)

    monkeypatch.setattr(room_frontier, "frontier_report",
                        lambda *a, **k: {"rooms_short": 2})
    monkeypatch.setattr(room_frontier, "record_measure", lambda *a, **k: None)
    monkeypatch.setattr(room_frontier, "spend_this_hour", lambda *a, **k: 0)
    monkeypatch.setattr(room_frontier, "fills_this_hour", lambda *a, **k: 0)
    monkeypatch.setattr(mandates, "spend_limits",
                        lambda *a, **k: {"calls_per_hour": 10})
    monkeypatch.setattr(mandates, "fill_limit", lambda *a, **k: 3)
    monkeypatch.setattr(mandates, "surprise_dial", lambda *a, **k: None)
    monkeypatch.setattr(mandates, "beats_per_proposal", lambda *a, **k: 1)
    monkeypatch.setattr(room_proposals, "last_pass_turn", lambda *a, **k: None)
    monkeypatch.setattr(room_bible, "schedule_fold", lambda *a, **k: None)
    # The fill's own work is not what this holds; that it runs armed is.
    monkeypatch.setattr(story_planner, "run_fill",
                        lambda *a, **k: story_planner._call(
                            "FILL SHEET", {"kind": "fill"}, max_tokens=64))

    bodies = []
    monkeypatch.setattr(jobs, "submit",
                        lambda cid, key, fn, **k: bodies.append(fn) or fn)

    class _Turn:
        idx, frame_id = 3, None

    class _Chat:
        id = chat_id

    class _Ctx:
        chat, turn = _Chat(), _Turn()

    story_planner.schedule_room_work(_Ctx())
    assert bodies, "a fill was due and should have been queued"
    bodies[0](None)

    rows = llm_capture.exchanges_for_turn(turn_id)
    assert [r["step_key"] for r in rows] == ["room:planner"], (
        "the call a fill job makes is filed against the turn in play")
