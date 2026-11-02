"""The reactor gates read the scene and the awareness map once a stage, and
the micro round reads each observer's bodies once.

`interaction_loop` wraps each of its widenings of `flow.reactors` in
`_drop_absent(ctx, _drop_non_awake(...))`, and each of those two gates read
the world for itself: a `get_scene` (a database read, a JSON parse -- 0.55 ms
for the largest stored scene, 54.8 KB -- plan overlays and the onset overlay)
and an `awareness_map` query per widening, about twenty scene reads a beat with
reactors (audit of 2026-11-01, agents_runtime_loops_mapping, Efficiency 1).
Nothing the gates read changes while the loop chooses who answers, so the
stage reads both once.

`deterministic_micro_perception` built the third-body admission's two sets --
the bodies the scene stands somewhere and the ones this observer's eyes reach,
a `visual_level_between` for every positioned subject -- once per ACTION EVENT
per observer, though neither depends on the event (Efficiency 3).
"""

from __future__ import annotations

import json
import time

import pytest

from core.db import wset
from core.pipeline_context import ChatData, PipelineContext, TurnData
from story.character_schema import default_character_data, default_persona_data


class _Stop(Exception):
    pass


def _chat(db):
    persona_id = db.qi("INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
                       ("Player", json.dumps(default_persona_data("Player")), "{}"))
    chat_id = db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Gates", "", time.time(), persona_id))
    ids = {}
    for name in ("Ann", "Bob"):
        cid = db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (name, json.dumps(default_character_data(name)), "{}",
             time.time(), f"char_{name.lower()}"))
        db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
              "VALUES(?,?,?,?)", (chat_id, cid, "active", "{}"))
        ids[name] = cid
    wset(chat_id, "scene", {
        "rooms": {"hall": {"name": "Hall", "desc": ".", "light": "lit",
                           "adjacent": []}},
        "positions": {"Player": "hall", "Ann": "hall", "Bob": "hall"},
        "entities": {}, "attire": {}, "overlays": {}, "stations": {}})
    cast = db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (chat_id,))
    turn_id = db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 3, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Gates", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=3, player_input="",
                      created=time.time()),
        cast=cast, input="",
        director_interpret={"flow": {"reactors": [ids["Ann"], ids["Bob"]]}})
    return ctx, ids


def test_the_interaction_loops_gates_read_the_world_once(temp_db, monkeypatch):
    from agents import loops
    ctx, ids = _chat(temp_db)
    reads = {"scene": 0, "awareness": 0}
    real_scene, real_awareness = loops.get_scene, loops.awareness_map

    def counted_scene(*a, **k):
        reads["scene"] += 1
        return real_scene(*a, **k)

    def counted_awareness(*a, **k):
        reads["awareness"] += 1
        return real_awareness(*a, **k)

    monkeypatch.setattr(loops, "get_scene", counted_scene)
    monkeypatch.setattr(loops, "awareness_map", counted_awareness)
    # every widening keeps the list as it is, so each gate pair runs
    monkeypatch.setattr(loops, "widen_reactors_to_engaged",
                        lambda chat_id, cast, reactors, *a, **k: list(reactors))
    monkeypatch.setattr(loops, "widen_reactors_to_rejoined",
                        lambda chat_id, cast, reactors, *a, **k: list(reactors))
    monkeypatch.setattr(loops, "widen_reactors_to_enclosure",
                        lambda chat_id, cast, reactors, *a, **k: list(reactors))
    monkeypatch.setattr(loops, "widen_reactors_to_acted_upon",
                        lambda chat_id, cast, interp, reactors, *a, **k: list(reactors))

    seen = {}

    def stop_after_the_gates(_ctx, ids_, _nonce):
        seen["reactors"] = list(ids_)
        raise _Stop

    monkeypatch.setattr(loops, "_untargeted_order", stop_after_the_gates)
    with pytest.raises(_Stop):
        loops.interaction_loop(ctx, 0)
    assert sorted(seen["reactors"]) == sorted([ids["Ann"], ids["Bob"]])
    assert reads == {"scene": 1, "awareness": 1}


def test_a_gate_called_outside_a_stage_still_reads_for_itself(temp_db):
    from agents import loops
    ctx, ids = _chat(temp_db)
    assert loops._drop_absent(ctx, [ids["Ann"]]) == [ids["Ann"]]
    assert loops._drop_non_awake(ctx, [ids["Bob"]]) == [ids["Bob"]]


def test_the_micro_round_reads_each_observers_bodies_once(temp_db, monkeypatch):
    from agents import loops
    ctx, ids = _chat(temp_db)
    calls = {"forms": 0, "seen": 0}
    real_forms, real_seen = loops._micro_body_forms, loops._micro_seen_bodies

    def forms(*a, **k):
        calls["forms"] += 1
        return real_forms(*a, **k)

    def seen(*a, **k):
        calls["seen"] += 1
        return real_seen(*a, **k)

    monkeypatch.setattr(loops, "_micro_body_forms", forms)
    monkeypatch.setattr(loops, "_micro_seen_bodies", seen)
    scene = loops.get_scene(ctx.chat.id, ctx.chat)
    result = {"sequence": [
        {"type": "action", "observable": "sets down a lamp"},
        {"type": "action", "observable": "turns up the wick"},
        {"type": "action", "observable": "sits"},
    ]}
    views, _ = loops.deterministic_micro_perception(ctx, ids["Ann"], result,
                                                     scene)
    assert len(views[ids["Bob"]]) == 3          # every act still delivered
    assert calls == {"forms": 1, "seen": 1}    # one observer, read once
