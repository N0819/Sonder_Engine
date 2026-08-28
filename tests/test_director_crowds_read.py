"""One crowds read per Director stage, and the gate reads the same one.

The defect this file pins (perf audit finding 10, 2026-08-28, chat 95,
307-body town): `_crowds_view` fired four times per turn -- once per stage
for the payload, and once more per stage inside `_gate_facts`, which threw
the rows away and kept a bool. Worse than the duplicate work, the gate's
private read passed no `turn_idx`, so it froze the presented-bodies lapse
(DESIGN_BACKGROUND_PRESENTATION SC3) and derived a DIFFERENT crowd set than
the payload: measured live, the gate's read returned 1 crowd row where the
payload's aged read returned 2. A beat where the conservative read returns
zero rows while the aged read has crowds would gate the crowd channel OUT
of dispatch while the payload stood ready to serve it.

The fix: each stage computes `_crowds_view` once, hands the rows to its
payload AND to `_gate_facts(crowds_rows=...)`; the gate's fallback recompute
(kept for callers without a payload) now passes the turn's own idx.
"""

from __future__ import annotations

import inspect
import json
import re
import time

import pytest

from core.pipeline_context import ChatData, PipelineContext, TurnData

import agents.director as director
import agents.director_scopes as director_scopes


BASE_SCENE = {
    "location": "Market Town",
    "time": "midday",
    "rooms": {
        "square": {"name": "Market Square", "adjacent": []},
    },
    "positions": {"Joren": "square"},
    "entities": {},
    "attire": {},
    "overlays": {},
}


def _make_ctx(temp_db):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )
    temp_db.wset(chat_id, "scene", json.loads(json.dumps(BASE_SCENE)))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 7, "hello", time.time()),
    )
    return PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=7,
                      player_input="hello", created=time.time()),
        cast=[], input="hello",
    )


def test_gate_reuses_the_stage_crowds_read(temp_db, monkeypatch):
    """`crowds_rows` handed in means zero `_crowds_view` calls in the gate.

    The call-count guard for the dedup: on the live 307-body turn the gate's
    private recompute was 2 of the turn's 4 `_crowds_view` calls. Patched at
    `director_scopes` because that module DEFINES the reader (the facade
    rule from persist/commit applies here too).
    """
    calls = []

    def counting(cid, sc, turn_idx=None):
        calls.append(turn_idx)
        return []

    monkeypatch.setattr(director_scopes, "_crowds_view", counting)
    ctx = _make_ctx(temp_db)
    sc = json.loads(json.dumps(BASE_SCENE))

    facts = director_scopes._gate_facts(
        ctx, sc, physical=False, speech=False,
        crowds_rows=[{"crowd_id": "crowd_1"}])
    assert facts["crowds_present"] is True
    assert calls == []

    facts = director_scopes._gate_facts(
        ctx, sc, physical=False, speech=False, crowds_rows=[])
    assert facts["crowds_present"] is False
    assert calls == []


def test_gate_fallback_ages_the_presented_lapse(temp_db, monkeypatch):
    """A gate left to recompute passes the turn's own idx.

    The old no-idx read took the conservative no-lapse `presented_bodies`
    set, subtracting long-lapsed bodies from the derived crowds -- measured
    live as 1 row against the payload's 2. The fallback must derive the
    same world the payload would.
    """
    calls = []

    def recording(cid, sc, turn_idx=None):
        calls.append((cid, turn_idx))
        return [{"crowd_id": "crowd_1"}]

    monkeypatch.setattr(director_scopes, "_crowds_view", recording)
    ctx = _make_ctx(temp_db)
    sc = json.loads(json.dumps(BASE_SCENE))

    facts = director_scopes._gate_facts(ctx, sc, physical=False, speech=False)
    assert facts["crowds_present"] is True
    assert calls == [(ctx.chat["id"], 7)]


def test_director_stages_read_crowds_once():
    """Each Director stage names `_crowds_view` exactly once, and every
    channel-gate call in the module shares that read via `crowds_rows`.

    A wiring pin, because this is exactly where the dedup silently regresses:
    someone adds a `_crowds_view` call to a payload or a gate without
    threading the shared rows, and nothing fails -- the turn just pays the
    derivation again and the gate can disagree with the payload once more.
    """
    source = inspect.getsource(director)
    reads = re.findall(r"_crowds_view\(", source)
    assert len(reads) == 2, (
        f"expected one _crowds_view read per Director stage (2 total), "
        f"found {len(reads)}; thread the stage's existing read instead")
    # Every channel-gate call in director.py hands its stage's rows in.
    # A window, not a paren matcher: the call sites nest calls in their
    # keyword arguments, and 400 chars comfortably covers both today
    # (interpret's spans ~180, resolve's ~230).
    sites = [m.start() for m in re.finditer(r"(?<!_prose)_gate_facts\(",
                                            source)]
    assert sites, "no _gate_facts call sites found -- pin needs updating"
    for start in sites:
        window = source[start:start + 400]
        assert "crowds_rows=" in window, (
            "a _gate_facts call site stopped sharing the stage's crowds "
            f"read:\n{window}")
