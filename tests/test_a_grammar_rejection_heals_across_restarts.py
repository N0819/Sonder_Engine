"""A json_schema rejection is re-tested a day after it happened, not a day
after every restart.

A 400 naming the grammar is written to the `providers_no_json_schema` row,
and at load every row entry became a NEW 24-hour suspension. Nothing ever
removed an entry -- not a lapsed one, not a grammar that later answered -- so
on `make run`, which restarts on every edit, or any nightly restart, every
role on that model ran without its grammar for the next day, every day,
indefinitely; and a 400 on a second model rewrote the row from this process's
own set, silently dropping the first (review 2026-11-01, llm_providers_quality
F8, reproduced: "proc2 A supported? False | suspended until in h: 24.0 ...
proc3 A supported? False").

Each rejection is now written with WHEN it happened and rehydrated with that
expiry; a lapsed entry is pruned at load; the row is merged, never rewritten
from one process's set; and a grammar that answers prunes its entry. Within
the process that saw the 400 it stays permanent, as before.
"""
from __future__ import annotations

import json

import pytest

from llm import providers

PROV = {"id": 1, "kind": "openai", "name": "host", "api_key": "k",
        "base_url": "http://x/v1"}
DAY = providers._SCHEMA_SUSPEND_SECONDS


@pytest.fixture
def clock(temp_db, monkeypatch):
    now = [1_800_000_000.0]
    monkeypatch.setattr(providers.time, "time", lambda: now[0])
    _restart()
    yield now
    _restart()


def _restart():
    """A new process: nothing in memory, the rows as the last one left them."""
    providers._NO_JSON_SCHEMA.clear()
    providers._SCHEMA_SUSPENDED.clear()
    providers._SCHEMA_STALLS.clear()
    providers._SCHEMA_REJECTED_AT.clear()
    providers._json_schema_supported._loaded = False


def _row():
    from core.db import get_setting
    return json.loads(get_setting(providers._NO_JSON_SCHEMA_SETTING) or "{}")


def _names(row):
    return sorted(str(entry).split("\u0000", 1)[1] for entry in row)


def test_the_window_counts_from_the_rejection_not_from_the_restart(clock):
    assert providers._json_schema_supported(PROV, "glm-a")
    providers._note_json_schema_rejected(PROV, "glm-a")
    assert not providers._json_schema_supported(PROV, "glm-a")

    clock[0] += 3600
    _restart()
    assert not providers._json_schema_supported(PROV, "glm-a")
    key = providers._json_object_key(PROV, "glm-a")
    assert providers._SCHEMA_SUSPENDED[key] == pytest.approx(
        clock[0] - 3600 + DAY), "a restart renewed the window"

    clock[0] += DAY
    _restart()
    assert providers._json_schema_supported(PROV, "glm-a")
    assert _names(_row()) == [], "a lapsed rejection stayed written down"


def test_a_second_rejection_does_not_drop_the_first(clock):
    providers._json_schema_supported(PROV, "glm-a")
    providers._note_json_schema_rejected(PROV, "glm-a")
    clock[0] += 3600
    _restart()
    providers._json_schema_supported(PROV, "glm-b")
    providers._note_json_schema_rejected(PROV, "glm-b")
    assert _names(_row()) == ["glm-a", "glm-b"]


def test_a_grammar_that_answers_prunes_its_entry(clock):
    providers._json_schema_supported(PROV, "glm-a")
    providers._note_json_schema_rejected(PROV, "glm-a")
    clock[0] += DAY / 2
    _restart()
    providers._json_schema_supported(PROV, "glm-a")   # load
    # The suspension ran out in this process and the grammar answered.
    providers._SCHEMA_SUSPENDED.clear()
    providers._note_json_schema_answered(PROV, "glm-a")
    assert _names(_row()) == []


def test_an_answered_grammar_call_reaches_the_prune(clock, monkeypatch):
    """Wired where a grammar-bearing stream returns, not only callable."""
    from tests.helpers import streamed

    class _Ok:
        status_code = 200
        text = ""

        def json(self):
            return {"choices": [{"message": {"content": '{"prose": "x"}'},
                                 "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 3, "completion_tokens": 2}}

    class _Session:
        def post(self, url, json=None, stream=None, **kw):
            assert json["response_format"]["type"] == "json_schema"
            return streamed(_Ok(), stream)

    from core.db import set_setting
    set_setting("reasoning_effort", json.dumps({"default": "off"}))
    providers._json_schema_supported(PROV, "glm-a")
    providers._SCHEMA_REJECTED_AT[providers._json_object_key(PROV, "glm-a")] = \
        clock[0] - DAY - 1
    providers._persist_schema_blacklist()
    monkeypatch.setattr(providers, "_session", lambda: _Session())
    providers._chat_complete_once(
        "narrator", "sys", "usr", None, True, 500, None,
        resolved=(PROV, "glm-a", {}),
        json_schema={"type": "object", "properties": {"prose": {"type": "string"}}})
    assert _names(_row()) == []


def test_a_row_from_before_timestamps_is_written_with_one_once(clock):
    from core.db import set_setting
    set_setting(providers._NO_JSON_SCHEMA_SETTING,
                json.dumps(["1\u0000glm-old"]))
    assert not providers._json_schema_supported(PROV, "glm-old")
    stamped = _row()
    assert list(stamped.values()) == [pytest.approx(clock[0])]
    clock[0] += DAY + 1
    _restart()
    assert providers._json_schema_supported(PROV, "glm-old")


def test_the_process_that_saw_the_400_keeps_it(clock):
    """Unchanged: within the process, a provider that described itself is
    believed (`tests/test_schema_stall_recovers.py`)."""
    providers._json_schema_supported(PROV, "glm-a")
    providers._note_json_schema_rejected(PROV, "glm-a")
    clock[0] += DAY * 100
    assert not providers._json_schema_supported(PROV, "glm-a")
