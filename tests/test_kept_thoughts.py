"""A mind keeps its thinking for a few turns (`mind/thoughts.py`, the owner,
2026-10-05: "preserving the reasoning block in context for about 5 turns, but
it should be chronologically ordered with recent episodes").
"""

from __future__ import annotations

import json
from copy import deepcopy

import pytest

from mind import thoughts as th
from tests.test_character_continuity import story  # noqa: F401 -- the fixture


# ---- what is kept, and for how long ----------------------------------------------

def test_a_thought_lives_its_turns_of_the_story_then_goes():
    st = {}
    for turn in range(1, 9):
        th.keep_thought(st, turn, f"k{turn}", [f"thought {turn}"], kept=5)
    assert [t["turn"] for t in st["thoughts"]] == [4, 5, 6, 7, 8]
    assert [t["turn"] for t in th.recent_thoughts(st, 9, kept=5)] == [4, 5, 6, 7, 8]
    assert [t["turn"] for t in th.recent_thoughts(st, 11, kept=5)] == [6, 7, 8]
    quiet = {}
    th.keep_thought(quiet, 1, "k1", ["long ago"], kept=5)
    th.keep_thought(quiet, 20, "k20", ["now"], kept=5)
    assert [t["turn"] for t in quiet["thoughts"]] == [20], "a quiet mind's old thinking is not recent"


def test_a_beats_calls_are_kept_in_order_and_cut_at_the_end_they_concluded_with():
    st = {}
    th.keep_thought(st, 3, "k3", ["first call", "second call"], kept=5)
    assert st["thoughts"][0]["thought"] == "first call\n\nsecond call"
    long = "x" * (th.THOUGHT_CHARS + 500) + " and so I decided"
    th.keep_thought(st, 4, "k4", [long], kept=5)
    kept = st["thoughts"][-1]["thought"]
    assert len(kept) == th.THOUGHT_CHARS and kept.endswith("and so I decided")
    th.keep_thought(st, 4, "k4", ["the beat again, rerolled"], kept=5)
    assert [t["thought"] for t in st["thoughts"] if t["turn"] == 4] == ["the beat again, rerolled"]


def test_off_keeps_nothing_and_clears_what_was_kept():
    st = {}
    th.keep_thought(st, 1, "k1", ["something"], kept=5)
    th.keep_thought(st, 2, "k2", ["more"], kept=0)
    assert "thoughts" not in st
    assert th.recent_thoughts({"thoughts": [{"turn": 1, "key": "k", "thought": "x"}]}, 2, kept=0) == []


def test_each_thought_stands_beside_its_turns_memory_oldest_first(monkeypatch):
    rows = [{"memory_ref": "k5", "details": "five"}, {"memory_ref": "k9", "details": "nine"}]
    monkeypatch.setattr(th, "q", lambda sql, args: [{"event_key": "k5", "turn_idx": 5},
                                                    {"event_key": "k9", "turn_idx": 9}])
    out = th.beside_their_turns(1, 2, rows, [
        {"turn": 5, "key": "k5", "thought": "T5"}, {"turn": 6, "key": "x6", "thought": "T6"},
        {"turn": 7, "key": "x7", "thought": "T7"}, {"turn": 10, "key": "x10", "thought": "T10"}])
    assert [r.get("details") or r.get("what_you_were_thinking") for r in out] == \
        ["five", "T6", "T7", "nine", "T10"]
    assert out[0]["what_you_were_thinking"] == "T5"


# ---- the card says what is true ----------------------------------------------------

@pytest.mark.parametrize("language", ["en", "ja"])
def test_the_card_says_whether_thinking_carries_over(temp_db, language):
    from agents.character_bare import prompt
    from llm.prompts import character_thinking_text
    off = prompt("Mara", [], language=language)
    assert character_thinking_text("not_kept", language) in off and "{thinking_carry}" not in off
    temp_db.set_setting("character_thoughts_kept", "5")
    on = prompt("Mara", [], language=language)
    assert character_thinking_text("kept", language).replace("{turns}", "5") in on
    assert character_thinking_text("not_kept", language) not in on


# ---- the step and the commit --------------------------------------------------------

def _reply():
    return {"want": "hear the visitor out", "held_back": "send them away",
            "hinge": "they may know something", "unsure": "whether it is true",
            "sequence": [{"say": "Tell me what happened.", "to": "the visitor", "how": "evenly",
                          "why": "I need to know"}],
            "demeanor": "calm", "tells": [], "notebook": [], "changes": [],
            "note": "hearing the visitor out"}


def _run(story, monkeypatch, thinking, previous=None, index=1):
    """The step at turn `index`, committed as turn `index + 1` (the fixture
    writes a turn row for each)."""
    import agents.character as character
    from llm import decisions, providers
    from tests.test_character_bare import _answer
    char_id, context, commit = story
    sent = []

    def model(role, step_key, system, payload, **kwargs):
        sent.append({"system": system, "payload": deepcopy(payload)})
        providers.last_reasoning.set(thinking)
        return deepcopy(_reply())

    monkeypatch.setattr(decisions, "OVERRIDE", lambda state, questions: _answer([])(questions))
    monkeypatch.setattr(character, "_agent_json", model)
    result = character.character_step(context(previous, index), char_id, 1)
    state, _prepared = commit(result, previous, index + 1)
    return result, state, sent


def test_a_mind_is_handed_its_own_thinking_beside_the_turn_it_was_had_in(temp_db, story, monkeypatch):
    temp_db.set_setting("character_thoughts_kept", "5")
    result, state, _sent = _run(story, monkeypatch, "The visitor is lying about the road.", index=1)
    assert result["_thought"] == ["The visitor is lying about the road."]
    assert state["thoughts"][-1]["turn"] == 2
    assert state["thoughts"][-1]["thought"] == "The visitor is lying about the road."
    _result, _state, sent = _run(story, monkeypatch, "Now I ask about the road.",
                                 previous=state, index=3)
    recent = sent[0]["payload"]["memory"].get("recent_memories") or []
    beside = [r for r in recent if r.get("what_you_were_thinking")]
    assert [r["what_you_were_thinking"] for r in beside] == ["The visitor is lying about the road."]
    assert "what_you_were_thinking" in sent[0]["system"]


def test_with_the_setting_off_nothing_is_kept_or_shown(temp_db, story, monkeypatch):
    result, state, _sent = _run(story, monkeypatch, "Private reasoning.", index=1)
    assert "_thought" not in result and "thoughts" not in state
    _r, _s, sent = _run(story, monkeypatch, "More.", previous=state, index=3)
    assert "what_you_were_thinking" not in json.dumps(sent[0]["payload"])
    assert "what_you_were_thinking" not in sent[0]["system"]


def test_a_memory_that_surfaces_unbidden_still_works_with_nothing_kept(temp_db, story, monkeypatch):
    """Measured on the first replay (2026-10-06): the kept-thinking block once
    imported `MemoryClock` inside `character_step`, which made the name local
    to the whole step -- and the unbidden-memory path, further down, read it
    on a beat with no thinking kept: UnboundLocalError, the beat dead, every
    later turn refused behind it."""
    import time
    import agents.character as character
    from mind.memory import _UNSET, _row_memory, add_memories_batch, visible_memory_rows
    char_id, context, _commit = story
    chat_id = context().chat.id
    add_memories_batch([{"chat_id": chat_id, "char_id": char_id, "turn_id": None, "turn_idx": 0,
                         "kind": "episodic", "category": "episode", "provenance": "witnessed",
                         "salience": 0.7, "content": "The harbour bell rang at dawn.",
                         "event_key": "event:bell", "encoded_at_seconds": 0.0}])
    monkeypatch.setattr(character, "_unbidden_trigger", lambda *a, **k: ("a test", True))
    monkeypatch.setattr(character, "contrast_memory", lambda chat, cid, *a, **k: [
        _row_memory(r) for r in visible_memory_rows(chat, cid, before_turn_idx=None,
                                                    viewer_frame_id=_UNSET, include_archived=True)])
    result, _state, sent = _run(story, monkeypatch, "Quiet thinking.", index=5)
    assert result["sequence"], "the beat stands"


def test_no_function_in_this_work_re_imports_a_module_level_name():
    """The class of that failure, held structurally where it was made: a
    function-local import of a name the module already imports makes the
    name local to the whole function, so a read on any path that skipped the
    import raises."""
    import ast
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    for rel in ("agents/character.py", "agents/character_tools.py", "mind/thoughts.py",
                "persist/about_backfill.py"):
        tree = ast.parse((root / rel).read_text(encoding="utf-8"))
        module = {a.asname or a.name.split(".")[0] for n in tree.body
                  if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names if a.name != "*"}
        for fn in (n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))):
            for node in ast.walk(fn):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    clash = {a.asname or a.name.split(".")[0] for a in node.names} & module
                    assert not clash, f"{rel}:{node.lineno} {fn.name} re-imports {sorted(clash)}"
