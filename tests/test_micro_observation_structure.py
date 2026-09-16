"""Micro-round evidence retains the boundaries and gates of its deliveries."""

from copy import deepcopy
import json
import time

import pytest

import agents.loops as loops
from core.db import wset
from core.pipeline_context import ChatData, PipelineContext, TurnData
from story.character_schema import default_character_data


@pytest.fixture
def micro_scene(temp_db):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Micro evidence", "", time.time()),
    )
    cast = [{"id": cid, "sheet": json.dumps(default_character_data(name)),
             "cstate": "{}", "stance": "{}"}
            for cid, name in ((1, "Alice"), (2, "Bob"), (3, "Cara"))]
    scene = {
        "location": "hall", "time": "day",
        "rooms": {"hall": {"name": "Hall", "light": "lit", "adjacent": []}},
        "positions": {name: "hall" for name in ("Alice", "Bob", "Cara")},
        "entities": {}, "attire": {}, "overlays": {},
    }
    wset(chat_id, "scene", scene)
    wset(chat_id, "known", {
        name: ["Alice", "Bob", "Cara"] for name in ("Alice", "Bob", "Cara")})
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Micro evidence", scenario="",
                      persona_id=None, lorebook_id=None, created=time.time()),
        turn=TurnData(id=1, chat_id=chat_id, idx=1, player_input="",
                      created=time.time()), cast=cast, input="",
        director_interpret={"flow": {"reactors": [1, 2], "addressed_to": [1]}},
        perception_act={
            "views": {str(cid): "The hall is lit." for cid in (1, 2, 3)},
            "observations": {str(cid): [{
                "observation_id": f"current:{cid}:0", "phase": "state",
                "standing": True, "kind": "environment", "channel": "sight",
                "observed": {"text": "The hall is lit."},
            }] for cid in (1, 2, 3)},
        },
    )
    return ctx, scene


def _texts(rows):
    return [row["observed"]["text"] for row in rows]


def test_delivered_speech_action_speech_remain_separate(micro_scene):
    ctx, scene = micro_scene
    result = {"sequence": [
        {"type": "speech", "text": "Wait. There are two keys."},
        {"type": "action", "observable": "raises one finger",
         "attempt": "SECRET_PLAN: distract Bob", "private_ground": "SECRET_VITAL"},
        {"type": "speech", "text": "Take the brass one."},
    ]}
    observations = {}
    views, _ = loops.deterministic_micro_perception(
        ctx, 1, result, scene, observation_out=observations, event_prefix="micro:4:1")
    rows = observations[2]
    assert _texts(rows) == views[2]
    assert [row["kind"] for row in rows] == ["speech", "action", "speech"]
    assert [row["actor"] for row in rows] == ["Alice"] * 3
    assert [row["order"] for row in rows] == [0, 1, 2]
    assert [row["observation_id"] for row in rows] == [
        "current:2:micro:4:1:0", "current:2:micro:4:1:1", "current:2:micro:4:1:2"]
    assert all(row["phase"] == "event" for row in rows)
    assert "SECRET" not in json.dumps(observations)
    assert rows[0]["observed"]["text"].count("Wait. There are two keys.") == 1


def test_concealment_and_unknown_identity_hold_in_observation_metadata(micro_scene):
    ctx, scene = micro_scene
    wset(ctx.chat.id, "known", {})
    result = {"sequence": [
        {"type": "speech", "text": "HIDDEN_PHRASE", "visibility": "concealed",
         "conceal_from": [2]},
        {"type": "action", "observable": "waves a hand", "attempt": "HIDDEN_MOTIVE"},
    ]}
    observations = {}
    views, _ = loops.deterministic_micro_perception(
        ctx, 1, result, scene, observation_out=observations)
    assert _texts(observations[2]) == views[2]
    assert len(observations[2]) == 1
    assert "HIDDEN" not in json.dumps(observations[2])
    assert "Alice" not in json.dumps(observations[2])
    assert "HIDDEN_PHRASE" in json.dumps(observations[3])
    assert "HIDDEN_MOTIVE" not in json.dumps(observations)


def test_contentless_trace_does_not_regain_actor_or_words(micro_scene, monkeypatch):
    ctx, scene = micro_scene
    monkeypatch.setattr(loops, "_delivery_ok", lambda *a, **kw: True)
    monkeypatch.setattr(loops, "hear_level", lambda *a, **kw: "trace")
    observations = {}
    views, _ = loops.deterministic_micro_perception(
        ctx, 1, {"sequence": [{"type": "speech", "text": "SECRET_WORDS"}]},
        scene, observation_out=observations)
    row = observations[2][0]
    assert _texts(observations[2]) == views[2]
    assert row["kind"] == "sound"
    assert row["fidelity"] == "ambiguous"
    assert "actor" not in row
    assert "Alice" not in json.dumps(row)
    assert "SECRET_WORDS" not in json.dumps(row)


def test_self_evidence_keeps_verbatim_words_and_observable_only():
    observations = []
    view = loops.self_micro_view({"sequence": [
        {"type": "speech", "text": "Keep both keys.", "visibility": "concealed"},
        {"type": "action", "observable": "nods", "attempt": "SECRET_INTENT"},
        {"type": "action", "observable": "", "attempt": "SECRET_THOUGHT"},
    ]}, observation_out=observations, observer_id=1, event_prefix="micro:3:1")
    assert _texts(observations) == view
    assert len(observations) == 2
    assert all(row["directed_at_self"] for row in observations)
    assert "SECRET" not in json.dumps(observations)
    assert "Keep both keys." in observations[0]["observed"]["text"]


def _install_loop(monkeypatch, ctx, *, wave, seen):
    monkeypatch.setattr(loops, "dialogue_config", lambda *_: {
        "max_micro_rounds": 3, "max_character_calls": 3,
        "initial_parallel_reactors": wave, "stop_on_question_to_player": False,
        "allow_npc_to_npc_dialogue": True, "silence_ends_exchange": False,
    })
    monkeypatch.setattr(loops, "_untargeted_order", lambda ctx, ids, nonce: ids)
    monkeypatch.setattr(loops, "_requires_director_resolution", lambda *_: False)
    monkeypatch.setattr(loops, "_next_speaker_candidates",
                        lambda *_: [1] if len(seen) == 2 else [])

    def speak(context, cid, nonce):
        seen.append((cid, deepcopy(context._extra["interaction_observations"][cid])))
        return {"sequence": [
            {"type": "speech", "text": f"Line from {cid}, call {len(seen)}."},
            {"type": "action", "observable": "nods", "attempt": "PRIVATE_MOTIVE"},
        ]}

    monkeypatch.setattr(loops, "character_step", speak)


@pytest.mark.parametrize("wave", [1, 2])
def test_rounds_preserve_evidence_timing_and_resume_exactly(
        micro_scene, monkeypatch, wave):
    ctx, _ = micro_scene
    base = deepcopy(ctx.perception_act)
    seen = []
    _install_loop(monkeypatch, ctx, wave=wave, seen=seen)
    result = loops.interaction_loop(ctx, nonce=7)
    assert [cid for cid, _ in seen] == [1, 2, 1]
    assert len(seen[0][1]) == 1
    assert len(seen[1][1]) == (1 if wave == 2 else 3)
    assert len(seen[2][1]) == 5
    assert seen[2][1][0]["phase"] == "state"
    event_rows = seen[2][1][1:]
    assert [row["kind"] for row in event_rows] == ["speech", "action"] * 2
    assert len({row["observation_id"] for row in event_rows}) == len(event_rows)
    assert "PRIVATE_MOTIVE" not in json.dumps(ctx._extra["interaction_observations"])
    assert ctx.perception_act == base

    live_views = deepcopy(ctx._extra["interaction_views"])
    live_observations = deepcopy(ctx._extra["interaction_observations"])
    ctx._extra.clear()
    loops.rehydrate_loop_views(ctx, "interaction_loop", json.loads(json.dumps(result)))
    assert ctx._extra["interaction_views"] == live_views
    assert ctx._extra["interaction_observations"] == live_observations


def test_legacy_round_does_not_publish_incomplete_structured_map(micro_scene):
    ctx, _ = micro_scene
    loops.rehydrate_loop_views(ctx, "interaction_loop", {"rounds": [{
        "speaker_id": 1, "delivered_views": {"2": ["Alice says something."]},
        "self_view": ["You said something."],
    }]})
    assert 1 not in ctx._extra["interaction_observations"]
    assert 2 not in ctx._extra["interaction_observations"]
    assert ctx._extra["interaction_observations"][3] == ctx.perception_act["observations"]["3"]


def test_legacy_base_context_survives_new_micro_round(micro_scene, monkeypatch):
    ctx, _ = micro_scene
    ctx.perception_act.pop("observations")
    seen = []
    _install_loop(monkeypatch, ctx, wave=1, seen=seen)
    loops.interaction_loop(ctx, nonce=0)
    rows = seen[1][1]
    assert rows[0]["phase"] == "context"
    assert rows[0]["observed"]["text"] == "The hall is lit."
    assert rows[1]["kind"] == "speech"


def test_reaction_rehydration_preserves_base_observation_handles(micro_scene):
    ctx, _ = micro_scene
    loops.rehydrate_loop_views(ctx, "reaction_loop", {"rounds": [{"reactor_id": 2}]})
    assert ctx._extra["reaction_observations"][2] == ctx.perception_act["observations"]["2"]
    assert ctx._extra["reaction_observations"][2] is not ctx.perception_act["observations"]["2"]


def test_live_reactors_each_receive_their_original_evidence(micro_scene, monkeypatch):
    ctx, _ = micro_scene
    ctx.director_interpret["flow"]["resolution_flags"] = {"contested": True}
    monkeypatch.setattr(loops, "reaction_config", lambda *_: {"enabled": True})
    monkeypatch.setattr(loops, "_requires_director_resolution", lambda *_: False)
    received = {}

    def react(context, cid, nonce):
        received[cid] = deepcopy(context._extra["reaction_observations"][cid])
        return {"sequence": [{"type": "speech", "text": "Wait!"}]}

    monkeypatch.setattr(loops, "character_step", react)
    result = loops.reaction_loop(ctx, nonce=0)
    assert result["calls"] == 2
    assert received == {cid: ctx.perception_act["observations"][str(cid)]
                        for cid in (1, 2)}
