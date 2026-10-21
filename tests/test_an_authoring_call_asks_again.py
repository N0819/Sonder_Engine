"""AN AUTHORING CALL ASKS AGAIN BEFORE IT REFUSES (2026-10-20).

Every whole-document authoring site -- generating a character or a persona,
re-importing one with AI reinterpretation, drafting a promotion, the
psychology, appearance and interior fills -- refuses a cut-off answer
(`_require_whole_json`, pinned in `tests/test_lore_write_path_truncation.py`),
and rightly: a half-written card looks finished. But each site asked ONCE.
Measured on a probe story's setup the same day: GLM 5.2 stopped a character
card after its reasoning at `"simulation": {` (874 characters of JSON at
6,828 response tokens against a 20,000 ceiling), and the whole story's setup
failed on it, where every pipeline stage would have asked again.

Pinned here: a site asks again (up to `AUTHORING_ATTEMPTS`) while the answer
is unreadable or cut off, keeps the first answer that arrives whole, and an
answer that never does is refused exactly as before with nothing written.
"""

from __future__ import annotations

import json

import pytest

from core.db import q
from story import importers

SHEET = {
    "identity": {"name": "Iseul", "aliases": ["the courier"]},
    "psychology": {
        "drive": {"essence": "deliver what was entrusted",
                  "expression": "keeps moving", "taboo": "opening the parcel"},
    },
    "social": {"voice": {"register": "clipped", "markers": ["short answers"]}},
}


def _cut(payload):
    """A cut of the payload that still parses once its braces are closed --
    the shape of an answer that stopped partway."""
    whole = json.dumps(payload)
    for n in range(len(whole) - 10, 10, -1):
        if importers._jparse_salvage(whole[:n]) and not importers._json_arrived_whole(whole[:n]):
            return whole[:n]
    raise AssertionError("no cut found")


def _answers(monkeypatch, *texts):
    """Stub the model with a queue of answers; the last repeats."""
    calls = []

    def fake(*_a, **_k):
        calls.append(1)
        return texts[min(len(calls), len(texts)) - 1]

    monkeypatch.setattr(importers, "chat_complete", fake)
    return calls


def test_a_cut_off_card_is_asked_for_again_and_the_whole_one_kept(temp_db, monkeypatch):
    calls = _answers(monkeypatch, _cut(SHEET), json.dumps(SHEET))
    cid, sheet = importers.generate_character("a courier")
    assert len(calls) == 2
    assert sheet["identity"]["name"] == "Iseul"
    assert sheet["psychology"]["drive"]["essence"] == "deliver what was entrusted"
    assert q("SELECT COUNT(*) AS c FROM characters", one=True)["c"] == 1


def test_an_unreadable_answer_is_asked_for_again(temp_db, monkeypatch):
    calls = _answers(monkeypatch, "I'm sorry, here is the card:", json.dumps(SHEET))
    _pid, sheet = importers.generate_persona("a courier")
    assert len(calls) == 2 and sheet["identity"]["name"] == "Iseul"


def test_an_answer_that_never_arrives_whole_is_refused_as_before(temp_db, monkeypatch):
    calls = _answers(monkeypatch, _cut(SHEET))
    with pytest.raises(RuntimeError, match="[Mm]ax output tokens"):
        importers.generate_character("a courier")
    assert len(calls) == importers.AUTHORING_ATTEMPTS
    assert q("SELECT COUNT(*) AS c FROM characters", one=True)["c"] == 0


def test_a_whole_first_answer_is_asked_once(temp_db, monkeypatch):
    calls = _answers(monkeypatch, json.dumps(SHEET))
    importers.generate_character("a courier")
    assert len(calls) == 1


def test_every_whole_document_site_asks_through_the_one_helper():
    """The eight sites, by the prompt each asks with; the promotion's
    memory-seed call deliberately degrades to an empty list and is not one."""
    import inspect
    source = inspect.getsource(importers)
    for prompt in ("generator_character", "generator_persona",
                   "import_character_reinterpret", "import_persona_reinterpret",
                   "fill_character_psychology", "fill_appearance"):
        at = source.index(f'get_prompt("{prompt}"')
        assert "_ask_whole(lambda: chat_complete(" in source[at - 300:at], prompt
    interior = source[source.index("def fill_body_interior("):]
    assert "_ask_whole(lambda: chat_complete(" in interior[:interior.index("_jparse_salvage(")]
    assert source.count("seed_raw = chat_complete(") == 1
