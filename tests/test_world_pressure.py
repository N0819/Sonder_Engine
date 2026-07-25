"""Regression tests for the world-pressure ledger (F5 -- THE WORLD ACTS,
docs/FABLE_REVIEW_FOLLOWUPS.md): the Enterprise run's environmental failure
mode, where an actively scanned alien Array produced zero world response
across 12 beats because nothing ever forced the Director to even decline to
act.

Mechanism under test:
- director_establish/director_resolve emit world_pressure ops
  (open/tick/hold/resolve); commit.py's commit_world_pressure applies them
  deterministically to the world-KV `world_pressures` ledger.
- world_pressure_view surfaces each open pressure with beats_since_tick and
  a must_tick_this_beat flag into the resolve payload.
- SILENCE about an open pressure is recorded as an implicit hold AND warned,
  so an inert world is always a visible choice.
- A pressure held past WORLD_PRESSURE_STALL_AGE is flagged must-tick; the
  director enforces the flag with one bounded correction retry.
"""

import json
import time

import commit
from character_schema import default_character_data
from pipeline_context import ChatData, PipelineContext, TurnData


def _simple_scene():
    return {
        "location": "Bridge",
        "time": "day",
        "rooms": {"bridge": {"name": "Bridge", "adjacent": []}},
        "positions": {"Mara": "bridge"},
        "entities": {},
        "attire": {},
        "overlays": {},
    }


def _make_ctx(temp_db, *, turn_idx=1):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )
    sheet = default_character_data("Mara")
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Mara", json.dumps(sheet), "{}", time.time(), "char_mara"),
    )
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"),
    )
    temp_db.wset(chat_id, "scene", _simple_scene())
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,),
    )
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, turn_idx, "speak", time.time()),
    )
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=turn_idx,
                      player_input="speak", created=time.time()),
        cast=cast,
        input="speak",
    )
    ctx.director_interpret = {
        "sequence": [], "speech": None, "action": None, "movement": None,
        "flow": {"reactors": [], "authority_claims": [],
                 "resolution_flags": {}, "fiction_frame": {}},
    }
    return ctx


def _entry(temp_db, chat_id, **overrides):
    entry = {"id": "wp:1:0", "subject": "active scan of the Kelvan Array",
             "note": "an unknown alien artifact being actively probed",
             "level": 0, "opened_turn": 1, "last_tick_turn": 1,
             "held_streak": 0}
    entry.update(overrides)
    temp_db.wset(chat_id, "world_pressures", [entry])
    return entry


# ---- ledger ops ----

def test_open_op_appends_and_dedupes(temp_db):
    ctx = _make_ctx(temp_db, turn_idx=3)
    op = {"op": "open", "subject": "active scan of the Kelvan Array",
          "note": "the Array may answer"}
    ctx.director_resolve = {"world_pressure": [op, dict(op)]}

    result = commit.commit_world_pressure(ctx, nonce=0)

    ledger = temp_db.wget(ctx.chat.id, "world_pressures", [])
    assert result["opened"] == 1
    assert len(ledger) == 1
    assert ledger[0]["opened_turn"] == 3
    assert ledger[0]["level"] == 0
    assert ledger[0]["id"]

    # Re-opening the same process next beat is not a second pressure.
    ctx.turn = TurnData(id=ctx.turn.id, chat_id=ctx.chat.id, idx=4,
                        player_input="speak", created=time.time())
    ctx.director_resolve = {"world_pressure": [dict(op)]}
    commit.commit_world_pressure(ctx, nonce=0)
    assert len(temp_db.wget(ctx.chat.id, "world_pressures", [])) == 1


def test_tick_escalates_and_resets_streak(temp_db):
    ctx = _make_ctx(temp_db, turn_idx=5)
    _entry(temp_db, ctx.chat.id, held_streak=2)
    ctx.director_resolve = {"world_pressure": [
        {"op": "tick", "id": "wp:1:0", "note": "the Array emits a pulse"},
    ]}

    result = commit.commit_world_pressure(ctx, nonce=0)

    ledger = temp_db.wget(ctx.chat.id, "world_pressures", [])
    assert result["ticked"] == 1
    assert ledger[0]["level"] == 1
    assert ledger[0]["held_streak"] == 0
    assert ledger[0]["last_tick_turn"] == 5
    assert ledger[0]["note"] == "the Array emits a pulse"
    assert not ctx.warnings


def test_explicit_hold_grows_streak_without_warning(temp_db):
    ctx = _make_ctx(temp_db, turn_idx=5)
    _entry(temp_db, ctx.chat.id)
    ctx.director_resolve = {"world_pressure": [
        {"op": "hold", "id": "wp:1:0", "note": "the scan is still running"},
    ]}

    result = commit.commit_world_pressure(ctx, nonce=0)

    ledger = temp_db.wget(ctx.chat.id, "world_pressures", [])
    assert result["held"] == 1
    assert ledger[0]["held_streak"] == 1
    assert not ctx.warnings


def test_silence_becomes_implicit_hold_and_warns(temp_db):
    # The spec's core requirement: silence about an open pressure is a
    # recorded, visible choice -- never a free default.
    ctx = _make_ctx(temp_db, turn_idx=5)
    _entry(temp_db, ctx.chat.id)
    ctx.director_resolve = {"world_pressure": []}

    result = commit.commit_world_pressure(ctx, nonce=0)

    ledger = temp_db.wget(ctx.chat.id, "world_pressures", [])
    assert result["unaddressed"] == 1
    assert ledger[0]["held_streak"] == 1
    assert any("unaddressed" in w for w in ctx.warnings)


def test_stalled_pressure_warns_and_flags_must_tick(temp_db):
    ctx = _make_ctx(temp_db, turn_idx=6)
    _entry(temp_db, ctx.chat.id, held_streak=1)
    ctx.director_resolve = {"world_pressure": []}  # silence again

    result = commit.commit_world_pressure(ctx, nonce=0)

    assert result["stalled"] == 1
    assert any("stalled" in w for w in ctx.warnings)
    view = commit.world_pressure_view(ctx.chat.id, 7)
    assert view[0]["must_tick_this_beat"] is True
    assert view[0]["beats_since_tick"] == commit.WORLD_PRESSURE_STALL_AGE


def test_resolve_removes_entry(temp_db):
    ctx = _make_ctx(temp_db, turn_idx=5)
    _entry(temp_db, ctx.chat.id)
    ctx.director_resolve = {"world_pressure": [
        # No id: the fuzzy overlapping-subject fallback must find it.
        {"op": "resolve", "subject": "scan of the Kelvan Array"},
    ]}

    result = commit.commit_world_pressure(ctx, nonce=0)

    assert result["resolved"] == 1
    assert temp_db.wget(ctx.chat.id, "world_pressures", []) == []
    assert not ctx.warnings


def test_establish_openers_apply_on_opening_turn(temp_db):
    ctx = _make_ctx(temp_db, turn_idx=0)
    ctx.director_establish = {"world_pressure": [
        {"op": "open", "subject": "the Array's dormant response protocol",
         "note": "an answered signal may wake it"},
        # Establishment may only OPEN; a stray tick op is ignored.
        {"op": "tick", "id": "nonsense"},
    ]}
    ctx.director_resolve = None

    result = commit.commit_world_pressure(ctx, nonce=0)

    ledger = temp_db.wget(ctx.chat.id, "world_pressures", [])
    assert result["opened"] == 1
    assert len(ledger) == 1
    assert ledger[0]["subject"] == "the Array's dormant response protocol"


# ---- director integration ----

def test_resolve_payload_surfaces_pressures_and_must_tick(temp_db, monkeypatch):
    import agents.director as director

    ctx = _make_ctx(temp_db, turn_idx=7)
    _entry(temp_db, ctx.chat.id, held_streak=2)

    captured = {}

    def fake_agent_json(role, step_key, system, payload, **kwargs):
        captured.update(payload)
        return {"world_pressure": [{"op": "tick", "id": "wp:1:0"}]}

    monkeypatch.setattr(director, "_agent_json", fake_agent_json)
    director.director_resolve(ctx, nonce=0)

    pressures = captured["world_pressure"]
    assert pressures[0]["id"] == "wp:1:0"
    assert pressures[0]["must_tick_this_beat"] is True
    assert "correction_notes" not in captured  # tick supplied -> no retry


def test_must_tick_violation_triggers_one_retry(temp_db, monkeypatch):
    import agents.director as director

    ctx = _make_ctx(temp_db, turn_idx=7)
    _entry(temp_db, ctx.chat.id, held_streak=2)

    calls = []

    def fake_agent_json(role, step_key, system, payload, **kwargs):
        calls.append(dict(payload))
        if len(calls) == 1:
            return {"resolved_event": "Everyone talks.", "world_pressure": []}
        return {"resolved_event": "The Array answers with a pulse.",
                "world_pressure": [{"op": "tick", "id": "wp:1:0",
                                    "note": "the Array answers"}]}

    monkeypatch.setattr(director, "_agent_json", fake_agent_json)
    out = director.director_resolve(ctx, nonce=0)

    assert len(calls) >= 2
    assert "WORLD PRESSURE HARD RULE" in calls[1].get("correction_notes", "")
    ticks = [op for op in out.get("world_pressure") or []
             if op.get("op") == "tick"]
    assert ticks and ticks[0]["id"] == "wp:1:0"
    assert not any("must-tick violated" in w for w in ctx.warnings)


def test_must_tick_violation_that_survives_retry_warns(temp_db, monkeypatch):
    import agents.director as director

    ctx = _make_ctx(temp_db, turn_idx=7)
    _entry(temp_db, ctx.chat.id, held_streak=2)

    def fake_agent_json(role, step_key, system, payload, **kwargs):
        return {"resolved_event": "Everyone keeps talking.",
                "world_pressure": []}

    monkeypatch.setattr(director, "_agent_json", fake_agent_json)
    out = director.director_resolve(ctx, nonce=0)

    assert any("must-tick violated" in w.lower() or
               "must-tick" in w for w in ctx.warnings)
    assert out.get("world_pressure_warnings")
