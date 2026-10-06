"""Every answered decision request can be kept as training data
(`llm/decisions.capture`; the owner, 2026-10-06: "build a training data file
for the day we decide to do a fine tune").

Pinned here: nothing is written unless the `decision_capture` setting is on;
on, one JSON line a request -- state, questions with their options, answers
with their probabilities, the model that answered, the step that asked, the
story's language -- beside the database; a sharded battery is one line a
shard; and a capture that cannot be written never costs the decision.
"""

from __future__ import annotations

import json
import os

import pytest

from llm import decisions

URL = "http://127.0.0.1:8192/v1/systemone"


class _Answer:
    status_code = 200
    text = ""

    def __init__(self, questions):
        self._questions = questions

    def json(self):
        return {"model": "jev-test", "usage": {"input_tokens": 9},
                "answers": {k: {"type": "choice", "choice": "yes", "probabilities": {"yes": 0.8, "no": 0.2}}
                            for k in self._questions}}


def _posts(monkeypatch):
    import requests
    sent = []

    def post(url, headers=None, json=None, timeout=None):
        sent.append(json)
        return _Answer(json["questions"])
    monkeypatch.setattr(requests, "post", post)
    return sent


def _question(i=0):
    return {"type": "choice", "instructions": f"Is this a question? {i}", "criteria": {"yes": "Yes.", "no": "No."}}


@pytest.fixture(autouse=True)
def _own_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(decisions, "CAPTURE_ROOT", str(tmp_path / "captured"))


def _lines(path):
    if not os.path.exists(path):
        return []
    return [json.loads(x) for x in open(path, encoding="utf-8")]


def test_nothing_is_kept_unless_capture_is_on(temp_db, monkeypatch):
    temp_db.set_setting("jev_url", URL)
    _posts(monkeypatch)
    decisions.decide("WHAT YOU HEARD: hello", {"q": _question()})
    assert _lines(decisions.capture_path()) == []


def test_each_answered_request_is_one_line_with_everything_a_fine_tune_needs(temp_db, monkeypatch):
    from core.pipeline_context import current_step_key
    temp_db.set_setting("jev_url", URL)
    temp_db.set_setting("decision_capture", "on")
    _posts(monkeypatch)
    token = current_step_key.set("character:7")
    try:
        got = decisions.decide("WHAT YOU HEARD: hello", {"q": _question()})
    finally:
        current_step_key.reset(token)
    [line] = _lines(decisions.capture_path())
    assert line["state"] == "WHAT YOU HEARD: hello"
    assert line["questions"]["q"]["criteria"] == {"yes": "Yes.", "no": "No."}
    assert line["answers"] == got and line["model"] == "jev-test"
    assert line["step"] == "character:7" and line["language"] == "en"


def test_captures_live_beside_their_database_one_folder_a_database(temp_db, monkeypatch):
    """A scratch or replay database's requests never mix with the install's."""
    from core import db
    monkeypatch.setattr(decisions, "CAPTURE_ROOT", None)
    folder = os.path.dirname(decisions.capture_path("2026-10-06"))
    stem = os.path.splitext(os.path.basename(db.DB))[0]
    assert folder == os.path.join(os.path.dirname(os.path.abspath(db.DB)), "training", "decisions", stem)
    assert decisions.capture_path("2026-10-06").endswith("2026-10-06.jsonl")


def test_a_sharded_battery_is_one_line_a_shard(temp_db, monkeypatch):
    temp_db.set_setting("jev_url", URL)
    temp_db.set_setting("decision_capture", "on")
    sent = _posts(monkeypatch)
    monkeypatch.setattr(decisions, "MAX_QUESTIONS_PER_REQUEST", 2)
    decisions.decide("state", {f"q{i}": _question(i) for i in range(5)})
    lines = _lines(decisions.capture_path())
    assert len(sent) == 3 and len(lines) == 3
    assert sorted(k for line in lines for k in line["questions"]) == [f"q{i}" for i in range(5)]


def test_a_capture_that_cannot_be_written_never_costs_the_decision(temp_db, monkeypatch):
    temp_db.set_setting("jev_url", URL)
    temp_db.set_setting("decision_capture", "on")
    _posts(monkeypatch)
    blocked = os.path.dirname(decisions.capture_path())
    os.makedirs(os.path.dirname(blocked), exist_ok=True)
    with open(blocked, "w") as fh:          # a FILE where the directory should be
        fh.write("not a directory")
    got = decisions.decide("state", {"q": _question()})
    assert got["q"]["choice"] == "yes"
