"""The capture records HOW a call was shaped, not only what it sent.

Two specialist calls hung for 22 minutes on 2026-09-14 and nobody could prove
afterwards whether a grammar was on the wire. `llm_capture` held the sheet,
the payload, the response, the reasoning, the model and the duration -- and
not the request's `response_format` type, the reasoning effort, the
`max_tokens`, or the finish reason, all of which `llm/providers.py` knew at
the POST and dropped at the response boundary.

The rule that now holds: every capture row carries the shape of the body the
provider layer ACTUALLY put on the wire -- after the staged 400 ladder, not
before it -- and the finish reason the provider returned. The seam is a
contextvar set at every POST site (`providers.last_request_shape`), read by
the two recorders on the thread that made the call, the way the reasoning
trace and the finish reason already travel.
"""

import json
import time

import pytest

from llm import providers


# ---------------------------------------------------------------------------
# A fake wire: what the provider layer posted, and a scripted answer
# ---------------------------------------------------------------------------

def _sse(*chunks):
    lines = [("data: " + json.dumps(c)).encode("utf-8") for c in chunks]
    lines.append(b"data: [DONE]")
    return lines


def _answer(finish="stop"):
    return _sse(
        {"model": "fake-model",
         "choices": [{"delta": {"content": '{"a": 1}'}}]},
        {"model": "fake-model",
         "choices": [{"delta": {}, "finish_reason": finish}],
         "usage": {"prompt_tokens": 1, "completion_tokens": 1}},
    )


class _Response:
    def __init__(self, status, lines=(), text=""):
        self.status_code = status
        self._lines = list(lines)
        self.text = text

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def iter_lines(self):
        return iter(self._lines)

    def close(self):
        pass


class _Wire:
    """Records every body posted; answers from a script, in order."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.bodies = []

    def post(self, url, **kw):
        self.bodies.append(kw.get("json"))
        if not self.responses:
            raise AssertionError("more posts than scripted")
        return self.responses.pop(0)


@pytest.fixture
def wire(monkeypatch):
    prov = {"name": "fake", "kind": "openai",
            "base_url": "http://fake.invalid/v1", "api_key": "k"}
    cfg = {"provider": "fake", "model": "fake-model"}
    monkeypatch.setattr(providers, "resolve_role_candidates",
                        lambda role: [(prov, "fake-model", cfg)])
    monkeypatch.setattr(providers, "reasoning_effort_for", lambda role: "low")
    monkeypatch.setattr(providers, "_json_schema_supported",
                        lambda prov, model: True)
    # The ladder's bookkeeping is process-wide and persisted; a test that
    # refuses a grammar must not cost every later test its grammar.
    monkeypatch.setattr(providers, "_note_json_schema_rejected",
                        lambda prov, model: None)
    monkeypatch.setattr(providers, "_note_json_object_rejected",
                        lambda prov, model: None, raising=False)
    holder = {}

    def arm(responses):
        holder["wire"] = _Wire(responses)
        monkeypatch.setattr(providers, "_session", lambda: holder["wire"])
        return holder["wire"]

    return arm


def test_the_shape_on_the_wire_is_what_is_reported(wire):
    w = wire([_Response(200, _answer("stop"))])

    out = providers.chat_complete("director", "SYS", "{}", json_mode=True,
                                  json_schema={"type": "object"},
                                  max_tokens=500)

    assert out == '{"a": 1}'
    assert w.bodies[0]["response_format"]["type"] == "json_schema"
    assert providers.request_shape() == {
        "response_format": "json_schema",
        "reasoning_effort": "low",
        "max_tokens": 500,
        "finish_reason": "stop",
    }


def test_a_refused_grammar_reports_the_rung_that_was_actually_sent(wire):
    """The whole point. `_apply_json_mode` shaped a json_schema body; the
    provider 400'd it; the ladder re-sent json_object and THAT answered.
    A record of what the engine meant to send would say json_schema and
    be wrong about the call that ran."""
    w = wire([_Response(400, text="response_format.type must be json_object"),
              _Response(200, _answer("length"))])

    providers.chat_complete("director", "SYS", "{}", json_mode=True,
                            json_schema={"type": "object"}, max_tokens=500)

    assert [b["response_format"]["type"] for b in w.bodies] == [
        "json_schema", "json_object"]
    shape = providers.request_shape()
    assert shape["response_format"] == "json_object"
    assert shape["finish_reason"] == "length"
    # Dropping the grammar must not have dropped the reasoning control: the
    # ladder's first rung keeps every other field, and the record says so.
    assert shape["reasoning_effort"] == "low"


def test_a_call_that_never_posted_reads_empty_not_stale(wire, monkeypatch):
    """Cleared at the start of every completion, like the finish reason: a
    completion that begins and dies before its POST must not inherit the
    previous call's shape and claim a grammar it never sent."""
    wire([_Response(200, _answer("stop"))])
    providers.chat_complete("director", "SYS", "{}", json_mode=True,
                            json_schema={"type": "object"}, max_tokens=500)
    assert providers.request_shape()["response_format"] == "json_schema"

    def dies_shaping(body, prov, model, json_mode, json_schema=None):
        raise RuntimeError("schema failed to compile")
    monkeypatch.setattr(providers, "_apply_json_mode", dies_shaping)
    monkeypatch.setattr(providers, "DEFAULT_RETRY",
                        providers.RetryConfig(max_retries=0))
    with pytest.raises(Exception):
        providers.chat_complete("director", "SYS", "{}", json_mode=True,
                                json_schema={"type": "object"})

    assert providers.request_shape() == {
        "response_format": "", "reasoning_effort": "",
        "max_tokens": None, "finish_reason": ""}


def test_openrouters_reasoning_object_is_rendered_as_its_effort():
    providers._note_request_shape({"reasoning": {"effort": "high"},
                                   "max_tokens": "300"})
    assert providers.request_shape()["reasoning_effort"] == "high"
    assert providers.request_shape()["max_tokens"] == 300
    providers._note_request_shape({"reasoning": {"enabled": False}})
    assert providers.request_shape()["reasoning_effort"] == "off"
    providers._note_request_shape({"reasoning_effort": "none"})
    assert providers.request_shape()["reasoning_effort"] == "none"
    providers._note_request_shape({})
    assert providers.request_shape()["response_format"] == ""
    providers.last_request_shape.set(None)


# ---------------------------------------------------------------------------
# The two recorders carry it
# ---------------------------------------------------------------------------

def test_the_pipeline_funnel_carries_the_shape_into_the_entry(monkeypatch):
    from core.pipeline_context import current_exchange_sink
    from llm.llm_quality import note_provider_exchange

    seen = []
    token = current_exchange_sink.set(seen.append)
    shape_token = providers.last_request_shape.set(
        {"response_format": "json_schema", "reasoning_effort": "low",
         "max_tokens": 4000})
    providers._capture_finish_reason("length")
    try:
        note_provider_exchange(role="director", system="S", payload={"x": 1},
                               response="", ok=False, started=time.time(),
                               error="hung")
    finally:
        current_exchange_sink.reset(token)
        providers.last_request_shape.reset(shape_token)
        providers._capture_finish_reason(None)

    assert len(seen) == 1
    entry = seen[0]
    assert entry["response_format"] == "json_schema"
    assert entry["reasoning_effort"] == "low"
    assert entry["max_tokens"] == 4000
    assert entry["finish_reason"] == "length"


def _turn(db):
    chat_id = db.qi("INSERT INTO chats(name,created) VALUES('t',0)")
    return chat_id, db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) "
        "VALUES(?,0,'hi',0)", (chat_id,))


def test_the_row_and_the_export_carry_the_shape(temp_db):
    from persist import llm_capture
    from persist.pipeline_trace import export_turn_debug

    temp_db.set_setting("llm_capture_enabled", "1")
    _chat, turn_id = _turn(temp_db)

    llm_capture.record_exchange(
        turn_id=turn_id, step_key="director_resolve", role="director",
        system="SHEET", payload={"a": 1}, response={"ok": True},
        response_format="json_schema", reasoning_effort="low",
        max_tokens=4000, finish_reason="length")

    (row,) = llm_capture.exchanges_for_turn(turn_id)
    assert row["response_format"] == "json_schema"
    assert row["reasoning_effort"] == "low"
    assert row["max_tokens"] == 4000
    assert row["finish_reason"] == "length"

    (event,) = [e for e in export_turn_debug(turn_id)["timeline"]
                if e["kind"] == "call"]
    assert event["request"] == {"response_format": "json_schema",
                                "reasoning_effort": "low",
                                "max_tokens": 4000}
    assert event["received"]["finish_reason"] == "length"


def test_a_row_written_without_a_shape_reads_empty(temp_db):
    """Empty is the honest reading -- the shape was not recorded -- and it
    is distinct from a recorded 'no response_format was sent' only in the
    export reader's head; both are '' on the row, by design."""
    from persist import llm_capture

    temp_db.set_setting("llm_capture_enabled", "1")
    _chat, turn_id = _turn(temp_db)
    llm_capture.record_exchange(
        turn_id=turn_id, step_key="narrator", role="narrator",
        system="S", payload={}, response="prose")
    (row,) = llm_capture.exchanges_for_turn(turn_id)
    assert (row["response_format"], row["reasoning_effort"],
            row["max_tokens"], row["finish_reason"]) == ("", "", None, "")


def test_the_rooms_recorder_carries_the_shape_too(temp_db, monkeypatch):
    from persist import llm_capture
    from story import room_calls

    temp_db.set_setting("llm_capture_enabled", "1")
    chat_id, turn_id = _turn(temp_db)

    def fake_chat_complete(role, system, user, **kwargs):
        providers._note_request_shape({"response_format": {"type": "json_object"},
                                       "reasoning_effort": "medium",
                                       "max_tokens": 8000})
        providers._capture_finish_reason("stop")
        return '{"plan": []}'

    monkeypatch.setattr(providers, "chat_complete", fake_chat_complete)
    try:
        with llm_capture.room_capture(chat_id, "planner"):
            room_calls.room_call("story_planner", "SYS", {"q": 1})
    finally:
        providers.last_request_shape.set(None)
        providers._capture_finish_reason(None)

    (row,) = llm_capture.exchanges_for_turn(turn_id)
    assert row["step_key"] == "room:planner"
    assert row["response_format"] == "json_object"
    assert row["reasoning_effort"] == "medium"
    assert row["max_tokens"] == 8000
    assert row["finish_reason"] == "stop"


# ---------------------------------------------------------------------------
# The migration
# ---------------------------------------------------------------------------

def test_an_existing_capture_table_gains_the_columns_on_migration(temp_db):
    """A v39 file carries the old table. SCHEMA's CREATE IF NOT EXISTS
    leaves it alone, so the v39 -> v40 list must add the columns."""
    db = temp_db
    with db.transaction() as c:
        c.execute("DROP TABLE llm_capture")
        c.execute("""CREATE TABLE llm_capture(
            id INTEGER PRIMARY KEY,
            turn_id INTEGER NOT NULL REFERENCES turns(id) ON DELETE CASCADE,
            seq INTEGER NOT NULL,
            step_key TEXT NOT NULL DEFAULT '',
            role TEXT NOT NULL DEFAULT '',
            requested TEXT NOT NULL DEFAULT '',
            served TEXT NOT NULL DEFAULT '',
            started REAL NOT NULL DEFAULT 0,
            duration REAL NOT NULL DEFAULT 0,
            ok INTEGER NOT NULL DEFAULT 1,
            error TEXT NOT NULL DEFAULT '',
            system_hash TEXT,
            payload_hashes TEXT NOT NULL DEFAULT '{}',
            response_hash TEXT,
            reasoning_hash TEXT)""")
        c.execute("INSERT INTO schema_meta(key,value) VALUES('version','39') "
                  "ON CONFLICT(key) DO UPDATE SET value=excluded.value")
    db.close_connection()

    db.init()

    columns = {r["name"] for r in db.q("PRAGMA table_info(llm_capture)")}
    assert {"response_format", "reasoning_effort", "max_tokens",
            "finish_reason"} <= columns
    version = db.q("SELECT value FROM schema_meta WHERE key='version'",
                   one=True)
    assert int(version["value"]) == db.SCHEMA_VERSION
