"""A model's JSON is read by ONE reader, fences and all.

Reported from play (2026-09-08), and the log named it exactly: a quick start
made three successful model calls and then died on

    the location generator returned 3237 characters of unparseable JSON
    (Expecting value) ... Tail: ... } ] } ```

"Expecting value" at character 0 is what `json.loads` says about a response
that opens with a backtick. The provider had wrapped its object in a ```json
fence -- which providers do even under `json_mode` -- and this call site
parsed with a bare `json.loads`, so the object arrived whole and was thrown
away, along with the chat and the two calls that had already been paid for.
The diagnosis it printed then said the object was "malformed rather than cut
short", which was true of the text and useless about the cause.

`llm.llm_quality.strict_json_parse` is what every pipeline stage already
reads model output with: it strips the fence, and failing that lifts the
first balanced object out of whatever prose surrounds it. Five sites had
their own narrower answer -- three a bare `json.loads`, two a hand-rolled
regex repair -- and a story could fail at any of them for a reason the
pipeline had solved years earlier.
"""
from __future__ import annotations

import json

import pytest

from llm import providers
from llm.llm_quality import strict_json_parse


FENCED = '```json\n{"town": {"name": "Saltmarrow"}, "posts": []}\n```'
PROSE_WRAPPED = (
    'Here is the location you asked for:\n\n'
    '{"town": {"name": "Saltmarrow"}, "posts": []}\n\nLet me know!')


def test_the_shared_reader_takes_a_fence():
    assert strict_json_parse(FENCED)["town"]["name"] == "Saltmarrow"


def test_the_shared_reader_takes_an_object_out_of_prose():
    assert strict_json_parse(PROSE_WRAPPED)["town"]["name"] == "Saltmarrow"


@pytest.mark.parametrize("response", [FENCED, PROSE_WRAPPED])
def test_the_location_generator_reads_a_fenced_plan(monkeypatch, response):
    """The live failure. `_json_call` is the location generator's one call
    shape, so this covers `propose_town`, `propose_history` and the historian
    alike -- the reported failure was in `propose_history`."""
    from world import charter_generate

    # The DEFINING module: `_json_call` does `from llm.providers import
    # chat_complete` inside itself, so a patch on the generator would be inert.
    monkeypatch.setattr(providers, "chat_complete",
                        lambda *a, **k: response)
    value = charter_generate._json_call("system", {"ask": "a town"})
    assert value["town"]["name"] == "Saltmarrow"


def test_a_genuinely_unreadable_plan_still_says_so(monkeypatch):
    """The tolerance is not silence: a response with no object in it at all
    still fails, and still reports the length and the tail."""
    from world import charter_generate

    monkeypatch.setattr(providers, "chat_complete",
                        lambda *a, **k: "I cannot help with that request.")
    with pytest.raises(ValueError) as caught:
        charter_generate._json_call("system", {"ask": "a town"})
    message = str(caught.value)
    assert "unparseable JSON" in message
    assert "I cannot help" in message


def test_the_recent_life_generator_reads_a_fenced_object(monkeypatch):
    from world import charter_history

    monkeypatch.setattr(providers, "chat_complete", lambda *a, **k: FENCED)
    assert charter_history.__dict__  # module imported; the reader is shared
    assert strict_json_parse(FENCED)["posts"] == []


def test_the_recall_judge_declines_rather_than_raising():
    """`_parse` answers None for output it cannot read -- a recall the judge
    cannot read is one it declines to judge -- but it must first read
    everything the shared reader can."""
    from mind import memory_judge

    assert memory_judge._parse(FENCED)["town"]["name"] == "Saltmarrow"
    assert memory_judge._parse("no object here at all") is None


def test_no_model_response_is_parsed_with_a_bare_json_loads():
    """The class, so the next call site does not reintroduce it: nothing that
    reads a `chat_complete` response may call `json.loads` on it directly."""
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    # The reader itself is the one place a bare `json.loads` on a model
    # response belongs: `strict_json_parse` tries it first and falls back.
    reader = root / "llm" / "llm_quality.py"
    offenders = []
    for package in ("world", "story", "mind", "agents", "llm", "persist"):
        for path in (root / package).rglob("*.py"):
            if path == reader:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            raw_names = set()
            for node in ast.walk(tree):
                # `raw = chat_complete(...)` -- the name a response is bound to
                if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                    func = node.value.func
                    name = getattr(func, "id", None) or getattr(func, "attr", None)
                    if name == "chat_complete":
                        raw_names.update(
                            t.id for t in node.targets if isinstance(t, ast.Name))
            if not raw_names:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if getattr(func, "attr", None) != "loads":
                    continue
                if not node.args or not isinstance(node.args[0], ast.Name):
                    continue
                if node.args[0].id in raw_names:
                    offenders.append("%s:%d" % (path.relative_to(root), node.lineno))
    assert not offenders, (
        "a model response parsed with a bare json.loads (use "
        "llm.llm_quality.strict_json_parse): %s" % offenders)
