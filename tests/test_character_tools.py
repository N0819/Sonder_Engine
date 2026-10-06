"""A character looks things up while it decides (`agents/character_tools.py`,
the owner, 2026-10-05): four read-only lookups over its own stores, answered
mid-thought with a budget of five a beat, and whatever comes back delivered
as recall's own rows are.
"""

from __future__ import annotations

import json
import time

import numpy as np
import pytest

from llm.providers import EmbeddingBatch
from story.character_schema import default_character_data
from tests.helpers import patch_provider_seam

DIM = 48


def _vector(text):
    v = np.zeros(DIM, dtype=np.float32)
    for word in str(text or "").lower().split():
        v[sum(map(ord, word.strip(".,:;!?'\""))) % DIM] += 1.0
    return v / (float(np.linalg.norm(v)) or 1.0)


@pytest.fixture
def embeddings(monkeypatch):
    patch_provider_seam(monkeypatch, "embed_texts_meta", lambda texts, **_kw: EmbeddingBatch(
        vectors=[_vector(t) for t in texts], model_key="test-words", dimensions=DIM))


def _story(temp_db, name="Mara"):
    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)", ("T", "", time.time()))
    char_id = temp_db.qi("INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
                         (name, json.dumps(default_character_data(name)), "{}", time.time()))
    temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
               (chat_id, char_id, "active", "{}"))
    return chat_id, char_id


def _mint(chat_id, char_id, turn_idx, content, *, key=None, seconds=None):
    from mind.memory import add_memories_batch
    return add_memories_batch([{
        "chat_id": chat_id, "char_id": char_id, "turn_id": None, "turn_idx": turn_idx,
        "kind": "episodic", "category": "episode", "provenance": "witnessed", "salience": 0.6,
        "content": content, "event_key": key or f"event:{char_id}:{turn_idx}",
        "encoded_at_seconds": seconds if seconds is not None else
        (None if turn_idx is None else float(turn_idx) * 60.0)}])[0]


class _Holding:
    def __init__(self):
        self.memories = []
        self.notebook = {}


def _lookups(chat_id, char_id, turn_idx, *, handles=None, memory_context=None, holding=None,
             state=None, concerns=(), ponder_inputs=None):
    from agents.character_tools import Lookups
    return Lookups(chat_id=chat_id, char_id=char_id, turn_idx=turn_idx, bank=None,
                   handles=handles if handles is not None else {},
                   memory_context=memory_context if memory_context is not None else {},
                   memory_internal={}, holding=holding,
                   notebook_inputs={"state": state or {}, "concerns": list(concerns)},
                   ponder_inputs=ponder_inputs or {"known": [], "known_names": [],
                                                   "unsettled": [], "limit": 5})


def _turns(result):
    return [m.get("details") or m.get("gist") for m in result["memories"]]


# ---- expand and continue ---------------------------------------------------------

def test_expand_brings_back_five_turns_each_side_in_order(temp_db, embeddings):
    chat_id, char_id = _story(temp_db)
    for t in range(1, 16):
        _mint(chat_id, char_id, t, f"Turn {t}: Oren said line {t}.")
    look = _lookups(chat_id, char_id, 20)
    result = look.run("expand", {"memory_ref": f"event:{char_id}:8"})
    assert _turns(result) == [f"Turn {t}: Oren said line {t}." for t in range(3, 14)]
    assert all(m["memory_ref"].startswith("m") for m in result["memories"])


def test_continue_reads_on_or_further_back(temp_db, embeddings):
    chat_id, char_id = _story(temp_db)
    for t in range(1, 16):
        _mint(chat_id, char_id, t, f"Turn {t}.")
    look = _lookups(chat_id, char_id, 20)
    before = look.run("continue", {"memory_ref": f"event:{char_id}:8", "direction": "before"})
    after = look.run("continue", {"memory_ref": f"event:{char_id}:8", "direction": "after"})
    assert _turns(before) == [f"Turn {t}." for t in range(3, 8)]
    assert _turns(after) == [f"Turn {t}." for t in range(9, 14)]
    edge = look.run("continue", {"memory_ref": f"event:{char_id}:15", "direction": "after"})
    assert edge == {"memories": [], "nothing_further": True}


def test_a_seeded_past_expands_in_the_order_it_was_formed(temp_db, embeddings):
    chat_id, char_id = _story(temp_db)
    for i in range(9):
        _mint(chat_id, char_id, -1, f"Seeded {i}.", key=f"seed:{i}", seconds=float(i))
    look = _lookups(chat_id, char_id, 5)
    assert _turns(look.run("expand", {"memory_ref": "seed:4"})) == [f"Seeded {i}." for i in range(0, 9)]
    fresh = _lookups(chat_id, char_id, 5)
    assert _turns(fresh.run("expand", {"memory_ref": "seed:0"})) == [f"Seeded {i}." for i in range(0, 6)]


def test_what_this_call_already_returned_is_pointed_at_not_repeated(temp_db, embeddings):
    """A second lookup over the same span costs the context nothing new: the
    rows an earlier lookup returned come back as pointers, and are delivered
    once."""
    chat_id, char_id = _story(temp_db)
    for t in range(1, 16):
        _mint(chat_id, char_id, t, f"Turn {t}.")
    look = _lookups(chat_id, char_id, 20)
    first = look.run("expand", {"memory_ref": f"event:{char_id}:8"})
    again = look.run("expand", {"memory_ref": f"event:{char_id}:9"})
    assert _turns(first) == [f"Turn {t}." for t in range(3, 14)]
    held = [m for m in again["memories"] if m.get("already_in_front_of_you")]
    assert len(held) == 10 and _turns({"memories": [m for m in again["memories"]
                                                   if not m.get("already_in_front_of_you")]}) == ["Turn 14."]
    assert [m["memory_ref"] for m in held] == [m["memory_ref"] for m in first["memories"]][1:]
    assert len(look.delivered) == 12 and len(look.reached_ids) == 12


def test_continue_reads_on_from_the_edge_of_what_was_read(temp_db, embeddings):
    """The owner: "remember 5 before or after a memory span" -- continuing
    from an expanded memory reads past the expansion, never back over it."""
    chat_id, char_id = _story(temp_db)
    for t in range(1, 26):
        _mint(chat_id, char_id, t, f"Turn {t}.")
    look = _lookups(chat_id, char_id, 30)
    look.run("expand", {"memory_ref": f"event:{char_id}:12"})          # turns 7-17
    before = look.run("continue", {"memory_ref": f"event:{char_id}:12", "direction": "before"})
    after = look.run("continue", {"memory_ref": f"event:{char_id}:12", "direction": "after"})
    assert _turns(before) == [f"Turn {t}." for t in range(2, 7)]
    assert _turns(after) == [f"Turn {t}." for t in range(18, 23)]
    further = look.run("continue", {"memory_ref": f"event:{char_id}:12", "direction": "before"})
    assert _turns(further) == ["Turn 1."]
    assert look.run("continue", {"memory_ref": f"event:{char_id}:12", "direction": "before"}) == \
        {"memories": [], "nothing_further": True}


def test_a_cut_result_delivers_only_what_it_returned(temp_db, embeddings, monkeypatch):
    from agents import character_tools
    chat_id, char_id = _story(temp_db)
    for t in range(1, 16):
        _mint(chat_id, char_id, t, f"Turn {t}: " + "a long remembered moment " * 20)
    monkeypatch.setattr(character_tools, "RESULT_CHARS", 1500)
    look = _lookups(chat_id, char_id, 20)
    result = look.run("expand", {"memory_ref": f"event:{char_id}:8"})
    assert result.get("more_before") and result.get("more_after") and 0 < len(result["memories"]) < 11
    returned = {m["memory_ref"] for m in result["memories"]}
    assert len(look.delivered) == len(result["memories"]) == len(look.reached_ids)
    assert set(look.handles) >= returned and not (set(
        k for k in look.handles if k.startswith("m")) - returned), "no handle for an unreturned row"


def test_an_expansion_too_long_to_fit_keeps_its_anchor_and_continue_finds_the_rest(
        temp_db, embeddings, monkeypatch):
    """Measured on the old code (review 2026-10-05): 44% of first expansions of
    an older memory on a heavy bank came back without the memory asked about,
    and `continue` then skipped the turns the cut had dropped."""
    from agents import character_tools
    chat_id, char_id = _story(temp_db)
    for t in range(1, 26):
        for k in range(3):
            _mint(chat_id, char_id, t, f"Turn {t} row {k}: " + "a long moment " * 30,
                  key=f"event:{char_id}:{t}:{k}", seconds=t * 60.0 + k)
    monkeypatch.setattr(character_tools, "RESULT_CHARS", 9000)
    look = _lookups(chat_id, char_id, 30)
    first = look.run("expand", {"memory_ref": f"event:{char_id}:12:1"})
    turns = sorted({int(m["details"].split()[1]) for m in first["memories"]})
    assert 12 in turns and turns == list(range(turns[0], turns[-1] + 1)), "the anchor, and whole turns around it"
    assert first.get("more_before") and first.get("more_after")
    before = look.run("continue", {"memory_ref": f"event:{char_id}:12:1", "direction": "before"})
    after = look.run("continue", {"memory_ref": f"event:{char_id}:12:1", "direction": "after"})
    got_before = sorted({int(m["details"].split()[1]) for m in before["memories"]})
    got_after = sorted({int(m["details"].split()[1]) for m in after["memories"]})
    assert got_before[-1] == turns[0] - 1 and got_after[0] == turns[-1] + 1, "picked up exactly at the edge"


def test_what_a_lookup_returns_carries_no_engine_number(temp_db, embeddings):
    """The owner, 2026-10-01: no engine number reaches a mind -- its packet
    words its judgements and drops the rest, and so does what it looks up."""
    chat_id, char_id = _story(temp_db)
    for t in range(1, 6):
        _mint(chat_id, char_id, t, f"Turn {t}.")
    look = _lookups(chat_id, char_id, 10)
    result = look.run("expand", {"memory_ref": f"event:{char_id}:3"})
    for row in result["memories"]:
        assert not any(isinstance(v, float) for v in row.values()), row
    assert any(isinstance(v, float) for row in look.delivered for v in row.values()), \
        "the engine keeps its own form"
    folded = look.folded({"memory": {}})
    assert not any(isinstance(v, float) for row in folded["memory"]["looked_up"] for v in row.values())


def test_a_lookup_reads_only_this_minds_past(temp_db, embeddings):
    """The firewall's own read: another mind's rows, the deciding turn and
    later, never; a ref this mind does not hold is refused."""
    chat_id, char_id = _story(temp_db)
    other = temp_db.qi("INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
                       ("Oren", json.dumps(default_character_data("Oren")), "{}", time.time()))
    for t in range(1, 10):
        _mint(chat_id, char_id, t, f"Mine {t}.")
    _mint(chat_id, other, 5, "Oren's own secret.", key="event:oren:5")
    look = _lookups(chat_id, char_id, 7)
    texts = _turns(look.run("expand", {"memory_ref": f"event:{char_id}:5"}))
    assert texts == [f"Mine {t}." for t in range(1, 7)]
    assert look.run("expand", {"memory_ref": "event:oren:5"})["refused"]
    assert look.run("expand", {"memory_ref": f"event:{char_id}:8"})["refused"]


def test_a_memory_already_in_front_of_the_mind_is_pointed_at_not_repeated(temp_db, embeddings):
    chat_id, char_id = _story(temp_db)
    for t in range(1, 6):
        _mint(chat_id, char_id, t, f"Turn {t}.")
    packet = {"recent_memories": [{"memory_ref": f"event:{char_id}:4", "details": "Turn 4."}]}
    look = _lookups(chat_id, char_id, 10, handles={"m1": f"event:{char_id}:4"},
                    memory_context=packet)
    result = look.run("expand", {"memory_ref": "m1"})
    held = [m for m in result["memories"] if m.get("already_in_front_of_you")]
    assert [m["memory_ref"] for m in held] == ["m1"] and "details" not in held[0]
    # New handles continue the packet's own numbering.
    assert {m["memory_ref"] for m in result["memories"]} - {"m1"} <= {f"m{n}" for n in range(2, 10)}


# ---- notebook, ponder ---------------------------------------------------------------

def test_the_notebook_lookup_shows_everything_kept_and_joins_the_read_back(temp_db):
    chat_id, char_id = _story(temp_db)
    holding = _Holding()
    holding.notebook = {"on_your_mind": [{"id": "x", "note": "already shown"}]}
    concerns = [f"worry {i}" for i in range(9)]
    look = _lookups(chat_id, char_id, 3, holding=holding, concerns=concerns,
                    state={"notebook": [{"id": "r1", "note": "ask about the box", "last_turn": 0}]})
    result = look.run("notebook", {})
    assert len(result["on_your_mind"]) == 9
    assert result["to_keep"][0]["id"] == "r1"
    assert holding.notebook["on_your_mind"][0]["id"] == "x"
    assert len(holding.notebook["on_your_mind"]) == 10 and holding.notebook["to_keep"][0]["id"] == "r1"


def test_a_ponder_answers_now_with_the_minds_own_memories(temp_db, embeddings):
    chat_id, char_id = _story(temp_db)
    _mint(chat_id, char_id, 2, "Oren hid the cedar box under the floorboard by the hearth.")
    _mint(chat_id, char_id, 3, "Rain all day.")
    look = _lookups(chat_id, char_id, 10)
    result = look.run("ponder", {"query": "where did Oren hide the cedar box"})
    assert any("cedar box" in str(m.get("details") or m.get("gist")) for m in result["memories"])
    assert look.run("ponder", {"query": "  "})["refused"]


# ---- delivered as recall's own rows ------------------------------------------------

def test_what_a_lookup_brought_is_delivered(temp_db, embeddings):
    chat_id, char_id = _story(temp_db)
    for t in range(1, 6):
        _mint(chat_id, char_id, t, f"Turn {t}.")
    holding, context = _Holding(), {}
    look = _lookups(chat_id, char_id, 10, holding=holding, memory_context=context)
    look.run("expand", {"memory_ref": f"event:{char_id}:3"})
    look.register()
    assert [r["memory_ref"] for r in context["looked_up"]] == [f"event:{char_id}:{t}" for t in range(1, 6)]
    assert [m["ref"] for m in holding.memories] == [f"event:{char_id}:{t}" for t in range(1, 6)]
    assert len(look.memory_internal["memory_access_ids"]) == 5
    folded = look.folded({"memory": {"recent_memories": []}})
    assert [m["memory_ref"][:1] for m in folded["memory"]["looked_up"]] == ["m"] * 5
    assert look.calls[0]["tool"] == "expand" and len(look.calls[0]["refs"]) == 5


# ---- the loop ------------------------------------------------------------------------

class _FakeModel:
    """`chat_complete` for tool rounds: each call answers from `script`."""

    def __init__(self, script):
        self.script = list(script)
        self.seen = []

    def __call__(self, role, system, user, *, history=None, tools=None, tool_choice=None,
                 turn=None, **kw):
        self.seen.append({"system": system, "user": user, "history": list(history or ()),
                          "tools": tools, "tool_choice": tool_choice, "json_mode": kw.get("json_mode"),
                          "max_tokens": kw.get("max_tokens", "unset")})
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        turn.clear()
        turn.update(content=step.get("content", ""), reasoning=step.get("reasoning", ""),
                    tool_calls=step.get("calls", []))
        return step.get("content", "")


class _Recorder:
    def __init__(self):
        self.calls = []

    def run(self, tool, args):
        self.calls.append((tool, args))
        return {"memories": [{"memory_ref": f"m{len(self.calls)}", "details": f"result {len(self.calls)}"}]}


def _call(name="ponder", args='{"query": "the key"}', cid=None):
    return {"id": cid or "", "name": name, "arguments": args}


def _loop(monkeypatch, script, budget=5):
    from agents import character_tools
    model = _FakeModel(script)
    monkeypatch.setattr("llm.providers.chat_complete", model)
    record = {}
    out = character_tools.look_then_answer("character_major", "SYSTEM", {"self": {}},
                                           _Recorder(), budget=budget, record=record)
    return out, record, model


def test_a_round_that_looks_and_then_answers(temp_db, monkeypatch):
    out, record, model = _loop(monkeypatch, [
        {"reasoning": "I should look.", "calls": [_call(cid="c1")]},
        {"content": '{"sequence": []}', "reasoning": "Now I know."}])
    assert out["answer"] == '{"sequence": []}'
    assert record["rounds"] == 2 and record["calls"] == 1 and record["stopped"] == "answered"
    assert [m["role"] for m in out["history"]] == ["assistant", "tool"]
    assert out["history"][0]["reasoning"] == "I should look."
    assert out["reasoning"].startswith("Now I know.")


def test_every_round_sends_the_same_prefix_and_only_appends(temp_db, monkeypatch):
    """The cache holds the packet only while it does not change."""
    _out, _record, model = _loop(monkeypatch, [
        {"calls": [_call(cid="c1")]}, {"calls": [_call(cid="c2")]}, {"content": "{}"}])
    assert len({(s["system"], s["user"]) for s in model.seen}) == 1
    hist = [s["history"] for s in model.seen]
    assert hist[0] == [] and hist[1] == hist[2][:len(hist[1])] and len(hist[2]) > len(hist[1])
    assert all(s["json_mode"] is False and s["tool_choice"] == "auto" for s in model.seen)
    assert all(s["max_tokens"] is None for s in model.seen), "the configured ceiling, as the single call's"


def test_the_budget_answers_every_call_and_then_closes(temp_db, monkeypatch):
    calls = [_call(cid=f"c{i}") for i in range(3)]
    out, record, _model = _loop(monkeypatch, [{"calls": calls}, {"calls": calls}], budget=5)
    assert record["calls"] == 5 and record["stopped"] == "budget"
    results = [json.loads(m["content"]) for m in out["history"] if m["role"] == "tool"]
    assert len(results) == 6 and results[-1] == {"not_run": "no lookups left this turn"}
    assert out["answer"] is None and out["history"]


def test_a_malformed_or_unknown_call_is_refused_and_counted(temp_db, monkeypatch):
    out, record, _model = _loop(monkeypatch, [
        {"calls": [_call(args="{not json", cid="c1")]}, {"content": "{}"}])
    assert record["calls"] == 1
    assert json.loads(out["history"][1]["content"]) == {"refused": "the arguments could not be read"}


def test_a_route_without_tools_falls_back_to_one_call(temp_db, monkeypatch):
    from llm.providers import ToolsUnsupported
    out, record, _model = _loop(monkeypatch, [ToolsUnsupported("no tools here")])
    assert out is None and "no tools here" in record["fallback"]


def test_the_lookups_are_off_unless_a_role_is_named(temp_db):
    from agents.character_tools import tools_enabled
    assert not tools_enabled("character_major")
    temp_db.set_setting("character_tools", "character_major")
    assert tools_enabled("character_major") and not tools_enabled("character_mid")


# ---- the step ------------------------------------------------------------------------

from tests.test_character_continuity import story  # noqa: E402,F401 -- the fixture


def _bare_reply():
    return {"want": "find out where the key went", "held_back": "accuse the visitor",
            "hinge": "I remember where it was", "unsure": "whether it was moved",
            "sequence": [{"say": "The key was in the cedar box.", "to": "the visitor",
                          "how": "evenly", "why": "I remember it"}],
            "demeanor": "calm", "tells": [], "notebook": [], "changes": [],
            "note": "the key was in the box"}


class _Route:
    """`chat_complete` for a whole beat: each tool round calls `per_round`
    lookups until `rounds` are spent, then answers -- in a round that calls
    nothing, or (when `close` is set) only once the closing round asks.

    It expands from turn 14: recall in this fixture delivers turns 1-9 and 19
    (measured), so that span holds rows only a lookup brings."""

    def __init__(self, char_id, *, rounds=1, per_round=1, close=False, first_answer=None,
                 fail_round=None, refuse_closing=False):
        self.char_id, self.rounds, self.per_round, self.close = char_id, rounds, per_round, close
        self.first_answer = first_answer
        self.fail_round, self.refuse_closing = fail_round, refuse_closing
        self.seen = []

    def __call__(self, role, system, user, *, history=None, tools=None, tool_choice=None,
                 turn=None, json_schema=None, **kw):
        self.seen.append({"role": role, "system": system, "user": user, "tools": tools,
                          "tool_choice": tool_choice, "history": list(history or ()),
                          "json_schema": json_schema})
        if turn is not None:
            turn.clear()
        if tools and tool_choice == "none" and self.refuse_closing:
            from llm.providers import ToolsUnsupported
            raise ToolsUnsupported("400: tool_choice none beside a grammar")
        if tools and tool_choice != "none":
            done = sum(1 for m in history or () if m.get("role") == "assistant")
            if done == self.fail_round:
                from llm.providers import LLMError
                raise LLMError("upstream 502")
            if done < self.rounds:
                calls = [{"id": f"r{done}c{i}", "name": "expand",
                          "arguments": json.dumps({"memory_ref": f"event:{self.char_id}:{14 + i}"})}
                         for i in range(self.per_round)]
                turn.update(content="", reasoning=f"round {done}: let me look back.",
                            tool_calls=calls)
                return ""
            if self.close:
                turn.update(content="", reasoning="", tool_calls=[
                    {"id": "x", "name": "notebook", "arguments": "{}"}])
                return ""
        reply = json.dumps(_bare_reply())
        if self.first_answer is not None:
            reply, self.first_answer = self.first_answer, None
        if turn is not None:
            turn.update(content=reply, reasoning="now I remember.", tool_calls=[])
        return reply


def _beat(story, monkeypatch, route_kw, *, index=30, ctx=None):
    import agents.character as character
    from agents import character_tools
    from llm import decisions
    from tests.test_character_bare import _answer
    char_id, context, _commit = story
    ctx = ctx or context(index=index)
    chat_id = ctx.chat.id
    if not getattr(ctx, "_minted", False):
        for t in range(1, 21):
            _mint(chat_id, char_id, t, f"Turn {t}: the visitor spoke of the cedar box {t}.")
        ctx._minted = True
    route = _Route(char_id, **route_kw)
    patch_provider_seam(monkeypatch, "chat_complete", route)
    monkeypatch.setattr(character_tools, "route_takes_tools", lambda role: True)
    monkeypatch.setattr(decisions, "OVERRIDE", lambda state, questions: _answer([])(questions))
    return character.character_step(ctx, char_id, 1), route, ctx


def _role_of(temp_db, story):
    from story.character_schema import character_tier
    char_id = story[0]
    sheet = json.loads(temp_db.q("SELECT sheet FROM characters WHERE id=?", (char_id,))[0]["sheet"])
    return {"bg": "character_bg", "mid": "character_mid",
            "major": "character_major"}.get(character_tier(sheet), "character_mid")


def test_a_mind_looks_back_mid_thought_and_answers(temp_db, story, embeddings, monkeypatch):
    temp_db.set_setting("character_tools", _role_of(temp_db, story))
    result, route, ctx = _beat(story, monkeypatch, {"rounds": 1})
    rounds = [s for s in route.seen if s["tools"]]
    assert len(rounds) == 2, "one round that looked, one that answered"
    assert len({(s["system"], s["user"]) for s in rounds}) == 1, "the cached prefix holds"
    assert "LOOKING BACK" in rounds[0]["system"]
    assert "lookups left this turn: 5)" in rounds[0]["system"] and "{lookups_left}" not in rounds[0]["system"]
    assert not any(s["json_schema"] for s in rounds), "no grammar on a tool round"
    # The answer given in the round that called nothing is the beat: no second call.
    assert not [s for s in route.seen if s["tool_choice"] == "none"]
    assert len(route.seen) == 2, "the round's answer is validated, not paid for twice"
    assert result["sequence"][0]["text"] == "The key was in the cedar box."
    looked = [c for c in result["tool_calls"] if c.get("tool")]
    assert looked[0]["tool"] == "expand" and f"event:{story[0]}:14" in looked[0]["refs"]
    assert result["tool_calls"][-1]["rounds"]["calls"] == 1
    assert ctx._extra["_tool_spend"][str(story[0])] == 1
    reached = set(result["recalled_memory_ids"])
    ids = {r["id"] for r in temp_db.q(
        "SELECT id FROM memories WHERE char_id=? AND turn_idx BETWEEN 10 AND 18", (story[0],))}
    assert ids and ids <= reached, "what a lookup brought is counted as reached"


def test_a_spent_budget_closes_on_the_grammar(temp_db, story, embeddings, monkeypatch):
    temp_db.set_setting("character_tools", _role_of(temp_db, story))
    result, route, _ctx = _beat(story, monkeypatch, {"rounds": 3, "per_round": 2})
    closing = [s for s in route.seen if s["tool_choice"] == "none"]
    assert len(closing) == 1 and closing[0]["json_schema"] and closing[0]["history"]
    tool_results = [json.loads(m["content"]) for m in closing[0]["history"] if m["role"] == "tool"]
    assert len(tool_results) == 6 and tool_results[-1] == {"not_run": "no lookups left this turn"}
    assert result["tool_calls"][-1]["rounds"]["stopped"] == "budget"
    assert result["sequence"][0]["text"] == "The key was in the cedar box."


def test_the_budget_is_the_beats_not_the_calls(temp_db, story, embeddings, monkeypatch):
    """Five a beat across an interaction loop's micro-rounds: the second
    call of the same beat looks up only what the first left."""
    temp_db.set_setting("character_tools", _role_of(temp_db, story))
    _result, _route, ctx = _beat(story, monkeypatch, {"rounds": 2, "per_round": 2})
    assert ctx._extra["_tool_spend"][str(story[0])] == 4
    _result, route, ctx = _beat(story, monkeypatch, {"rounds": 3, "per_round": 1}, ctx=ctx)
    assert ctx._extra["_tool_spend"][str(story[0])] == 5
    assert "lookups left this turn: 1)" in route.seen[0]["system"], "the card says what is left"
    carried = json.loads(route.seen[0]["user"])["memory"].get("looked_up") or []
    assert any("cedar box 14" in str(m.get("details") or m.get("gist")) for m in carried), \
        "what it looked up earlier this beat is in front of it again"
    _result, route, ctx = _beat(story, monkeypatch, {"rounds": 3, "per_round": 1}, ctx=ctx)
    assert not any(s["tools"] for s in route.seen), "nothing left: one call, as before"
    assert "LOOKING BACK" not in route.seen[0]["system"]


def test_a_re_ask_of_the_beat_carries_what_was_looked_up(temp_db, story, embeddings, monkeypatch):
    temp_db.set_setting("character_tools", _role_of(temp_db, story))
    result, route, _ctx = _beat(story, monkeypatch, {"rounds": 1, "first_answer": "{}"})
    again = [s for s in route.seen if not s["tools"]]
    assert len(again) == 1, "the empty answer is asked once more, as a fresh request"
    assert "LOOKING BACK" not in again[0]["system"], "a rung offers no tools, and promises none"
    looked = json.loads(again[0]["user"])["memory"]["looked_up"]
    assert {m["memory_ref"][:1] for m in looked} == {"m"}, "named by handle, as the packet is"
    assert any("cedar box 14" in str(m.get("details") or m.get("gist")) for m in looked)
    assert result["sequence"][0]["text"] == "The key was in the cedar box."


def test_with_the_setting_off_the_card_and_the_call_are_unchanged(temp_db, story, embeddings,
                                                                   monkeypatch):
    result, route, ctx = _beat(story, monkeypatch, {"rounds": 1})
    assert len(route.seen) == 1 and not route.seen[0]["tools"]
    assert "LOOKING BACK" not in route.seen[0]["system"]
    assert "tool_calls" not in result
    assert "_tool_spend" not in ctx._extra


def _packet_in(user):
    """The step's packet inside a later call, wherever the rung puts it: whole
    (a re-ask), or as the original request (a rebuild); None for a rung that
    sends only the broken fields."""
    body = json.loads(user)
    if "memory" in body:
        return body
    return body.get("original_request")


@pytest.mark.parametrize("first, broken", [
    ("{}", None),                                   # the empty-object re-ask
    (json.dumps({"sequence": "not a list"}), "unparseable"),  # fragment fails, then a rebuild
])
def test_every_rung_that_resends_the_packet_resends_what_was_looked_up(temp_db, monkeypatch,
                                                                         first, broken):
    """A re-ask is a fresh request with no tool history, so the packet it
    carries has the lookups' results folded in -- or it would be answered
    from a packet that no longer holds what the mind had just read."""
    from llm.llm_quality import complete_validated_json
    seen = []

    def route(role, system, user, **kw):
        seen.append({"packet": _packet_in(user), "history": kw.get("history"),
                     "tools": kw.get("tools")})
        if broken and system.startswith("You repair ONE malformed field"):
            return broken
        return json.dumps(_bare_reply())

    patch_provider_seam(monkeypatch, "chat_complete", route)
    folded = {"memory": {"looked_up": [{"memory_ref": "m9", "details": "The box was cedar."}]}}
    out = complete_validated_json(
        role="character_major", step_key="character_bare", system="S",
        payload={"memory": {}}, first_raw=first, folded_payload=folded, repair_attempts=1)
    carried = [s["packet"] for s in seen if s["packet"] is not None]
    assert carried, "some rung resent the packet"
    assert all(p["memory"]["looked_up"][0]["memory_ref"] == "m9" for p in carried)
    assert not any(s["history"] or s["tools"] for s in seen)
    assert out["sequence"][0]["say"] == "The key was in the cedar box."


# ---- when a round fails, and what the capture shows ----------------------------------

def test_a_round_that_fails_ends_the_lookups_not_the_beat(temp_db, story, embeddings, monkeypatch):
    temp_db.set_setting("character_tools", _role_of(temp_db, story))
    result, route, ctx = _beat(story, monkeypatch, {"rounds": 3, "fail_round": 1})
    plain = [s for s in route.seen if not s["tools"]]
    assert len(plain) == 1, "one plain call answers"
    assert "LOOKING BACK" not in plain[0]["system"], "no lookups promised where none can be made"
    looked = json.loads(plain[0]["user"])["memory"]["looked_up"]
    assert any("cedar box 14" in str(m.get("details") or m.get("gist")) for m in looked)
    assert result["sequence"][0]["text"] == "The key was in the cedar box."
    assert any("the lookups stopped after 1" in w for w in ctx.warnings)
    assert result["tool_calls"][-1]["rounds"]["fallback"].startswith("LLMError")


def test_a_failure_before_any_lookup_is_the_single_call_as_before(temp_db, story, embeddings,
                                                                  monkeypatch):
    temp_db.set_setting("character_tools", _role_of(temp_db, story))
    result, route, ctx = _beat(story, monkeypatch, {"rounds": 3, "fail_round": 0})
    plain = [s for s in route.seen if not s["tools"]]
    assert len(plain) == 1 and "looked_up" not in json.loads(plain[0]["user"])["memory"]
    assert "LOOKING BACK" not in plain[0]["system"]
    assert any("no lookups this beat" in w for w in ctx.warnings)
    assert result["sequence"][0]["text"] == "The key was in the cedar box."


def test_a_refused_closing_round_is_asked_again_plainly(temp_db, story, embeddings, monkeypatch):
    temp_db.set_setting("character_tools", _role_of(temp_db, story))
    result, route, _ctx = _beat(story, monkeypatch, {"rounds": 9, "close": True,
                                                    "refuse_closing": True})
    closing = [s for s in route.seen if s["tool_choice"] == "none"]
    plain = [s for s in route.seen if not s["tools"]]
    assert len(closing) == 1 and len(plain) == 1
    assert json.loads(plain[0]["user"])["memory"]["looked_up"], "what the lookups found, folded in"
    assert plain[0]["json_schema"], "on the grammar, as the closing round was"
    assert result["sequence"][0]["text"] == "The key was in the cedar box."


def test_one_capture_row_per_call_each_with_what_it_was_sent(temp_db, story, embeddings,
                                                              monkeypatch):
    from core.pipeline_context import current_exchange_sink
    temp_db.set_setting("character_tools", _role_of(temp_db, story))
    rows = []
    token = current_exchange_sink.set(rows.append)   # armed as `runtime._run_step` arms it
    try:
        _result, route, _ctx = _beat(story, monkeypatch, {"rounds": 2})
    finally:
        current_exchange_sink.reset(token)
    mine = [r for r in rows if str(r.get("role") or "").startswith("character")]
    assert len(mine) == len(route.seen) == 3, "two rounds that looked, one that answered"
    histories = [len(r["payload"].get("tool_history") or []) for r in mine]
    assert histories == [0, 2, 4], "each row holds the rounds it was sent, no more"
    assert all("looked_up" not in (r["payload"].get("memory") or {}) for r in mine)
    assert [r["ok"] for r in mine] == [True, True, True]
    assert "tool_calls" in json.loads(json.dumps(mine[0]["response"]))



def test_the_notebook_lookup_returns_what_the_page_was_chosen_from(temp_db, story, embeddings,
                                                                    monkeypatch):
    """Review 2026-10-05: the lookup read concerns and projects from the
    payload after the page had replaced them, and told a mind with a concern
    that it kept nothing."""
    temp_db.set_setting("character_tools", _role_of(temp_db, story))

    class _NotebookRoute(_Route):
        def __call__(self, role, system, user, *, history=None, tools=None, tool_choice=None,
                     turn=None, json_schema=None, **kw):
            if tools and tool_choice != "none" and not history:
                self.seen.append({"system": system, "user": user, "tools": tools,
                                  "tool_choice": tool_choice, "history": [], "json_schema": None})
                turn.clear()
                turn.update(content="", reasoning="", tool_calls=[
                    {"id": "n1", "name": "notebook", "arguments": "{}"}])
                return ""
            return super().__call__(role, system, user, history=history, tools=tools,
                                    tool_choice=tool_choice, turn=turn, json_schema=json_schema, **kw)

    import agents.character as character
    from agents import character_tools
    from llm import decisions
    from tests.test_character_bare import _answer
    char_id, context, _commit = story
    route = _NotebookRoute(char_id, rounds=0)
    patch_provider_seam(monkeypatch, "chat_complete", route)
    monkeypatch.setattr(character_tools, "route_takes_tools", lambda role: True)
    monkeypatch.setattr(decisions, "OVERRIDE", lambda state, questions: _answer([])(questions))
    character.character_step(context(index=3), char_id, 1)
    shown = json.loads(route.seen[1]["history"][1]["content"])
    assert "the visitor may be in danger" in json.dumps(shown.get("on_your_mind"), ensure_ascii=False)
