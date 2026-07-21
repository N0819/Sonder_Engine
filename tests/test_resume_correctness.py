"""Regression tests for two resume/reroll correctness bugs (audit #10, #11).

#10  A single-step reroll (`only_key`) of a PRE-commit stage on an
     already-committed turn ran against POST-commit world state and this
     turn's own committed memories, so onset perception/character saw
     outcome knowledge. Two independent leaks:
       (a) runtime restored nothing for a non-commit `only_key` -> the
           rerolled onset stage saw the post-commit scene/positions;
       (b) `recent_memory_buffer` included `turn_idx == current`, so a
           character's onset context contained its own committed memory of
           how this very turn ended.

#11  `ctx.character_results` was never rehydrated on resume: a resumed or
     reroll-commit turn loaded interaction_loop/reaction_loop CONTENT into
     `ctx.interaction_loop`/`ctx.reaction_loop` but left the per-character
     result maps that commit.py/perception.py read directly empty, silently
     committing no character self-memories / mind_model_updates /
     stance_updates / active_state.
"""

from __future__ import annotations

import json
import time

import pytest

import agents.loops
import agents.runtime as runtime
import memory
from agents.runtime import _rehydrate_loop_results, _run_pipeline
from agents.storage import active_content, save_step
from character_schema import default_character_data
from pipeline_context import ChatData, PipelineContext, TurnData
from scene import get_scene


# ---- shared setup helpers ----

def _make_chat(db):
    return db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )


def _make_turn(db, chat_id, idx=1, player_input="do something"):
    return db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, idx, player_input, time.time()),
    )


def _make_cast(db, chat_id, names):
    ids = {}
    for name in names:
        char_id = db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (name, json.dumps(default_character_data(name)), "{}",
             time.time(), f"char_{name.lower()}"),
        )
        db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
            (chat_id, char_id, "active", "{}"),
        )
        ids[name] = char_id
    rows = db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,),
    )
    return ids, rows


def _scene(positions):
    return {
        "location": "Old Manor", "time": "evening",
        "rooms": {
            "kitchen": {"name": "Kitchen", "desc": "", "adjacent": []},
            "study": {"name": "Study", "desc": "", "adjacent": []},
        },
        "positions": positions, "entities": {}, "overlays": {}, "attire": {},
    }


def _stub_handlers(monkeypatch, overrides=None, reactors=None, contested=False):
    def fake_interpret(ctx, nonce):
        return {"flow": {
            "needs_mapping": False,
            "reactors": reactors or [],
            "resolution_flags": {"contested": contested,
                                 "possible_reactors": reactors or []},
        }}

    stubs = {
        "director_interpret": fake_interpret,
        "mapping_quick": lambda ctx, nonce: {"relevant_lore": []},
        "perception_act": lambda ctx, nonce: {"views": {
            str(rid): "The player lunges at you." for rid in (reactors or [])
        }},
        "director_resolve": lambda ctx, nonce: {"dialogue_log": [], "state_diff": {}},
        "background_react": lambda ctx, nonce: {"fired": False},
        "perception_outcome": lambda ctx, nonce: {"views": {}},
        "narrator": lambda ctx, nonce: {"prose": "ok"},
        "commit": lambda ctx, nonce: {"committed": True},
    }
    stubs.update(overrides or {})
    for key, fn in stubs.items():
        monkeypatch.setitem(runtime.STEP_HANDLERS, key, fn)


# ---- #10(b): recent_memory_buffer excludes the current turn ----

class TestRecentMemoryBufferExcludesCurrentTurn:
    def _add_memory(self, db, chat_id, char_id, turn_idx, content):
        return db.qi(
            "INSERT INTO memories(chat_id,char_id,turn_idx,frame_id,kind,category,"
            "content,gist) VALUES(?,?,?,?,?,?,?,?)",
            (chat_id, char_id, turn_idx, None, "episodic", "episode", content, content),
        )

    def test_current_turn_memory_is_not_in_the_buffer(self, temp_db):
        chat_id = _make_chat(temp_db)
        ids, _ = _make_cast(temp_db, chat_id, ["Alice"])
        alice = ids["Alice"]

        self._add_memory(temp_db, chat_id, alice, 1, "turn 1 happened")
        self._add_memory(temp_db, chat_id, alice, 2, "turn 2 happened")
        # This is the memory the turn-3 pipeline would have committed for its
        # OWN outcome -- it must never surface while turn 3's onset stages run.
        self._add_memory(temp_db, chat_id, alice, 3, "turn 3 OUTCOME")

        buf = memory.recent_memory_buffer(
            chat_id, alice, current_turn_idx=3, turns=4, viewer_frame_id=None)

        idxs = {m["turn_idx"] for m in buf}
        assert 3 not in idxs
        assert idxs == {1, 2}
        assert all("OUTCOME" not in (m.get("content") or "") for m in buf)

    def test_prior_turns_within_window_are_still_included(self, temp_db):
        chat_id = _make_chat(temp_db)
        ids, _ = _make_cast(temp_db, chat_id, ["Alice"])
        alice = ids["Alice"]
        self._add_memory(temp_db, chat_id, alice, 2, "recent")

        buf = memory.recent_memory_buffer(
            chat_id, alice, current_turn_idx=3, turns=4, viewer_frame_id=None)
        assert [m["turn_idx"] for m in buf] == [2]


# ---- #10(a): only_key reroll of a pre-commit stage restores pre-turn state ----

class TestOnlyKeyRerollRestoresPreTurnState:
    def _run_full_turn_that_mutates_world(self, temp_db, monkeypatch, chat_id, turn_id):
        pre_scene = _scene({"Alice": "kitchen"})
        post_scene = _scene({"Alice": "study"})
        temp_db.wset(chat_id, "scene", pre_scene)

        def committing(ctx, nonce):
            # Stand in for real commit mutating durable world state.
            temp_db.wset(ctx.chat.id, "scene", post_scene)
            return {"committed": True}

        _stub_handlers(monkeypatch, overrides={"commit": committing})
        list(_run_pipeline(chat_id, turn_id))
        return pre_scene, post_scene

    def test_reroll_of_perception_act_sees_pre_turn_scene(
        self, temp_db, monkeypatch,
    ):
        chat_id = _make_chat(temp_db)
        _make_cast(temp_db, chat_id, ["Alice"])
        turn_id = _make_turn(temp_db, chat_id, idx=1)

        pre_scene, post_scene = self._run_full_turn_that_mutates_world(
            temp_db, monkeypatch, chat_id, turn_id)

        # Sanity: the committed turn left the live world in the POST state.
        assert (get_scene(chat_id, None).get("positions") or {}).get("Alice") == "study"

        seen = {}

        def capturing_perception(ctx, nonce):
            seen["positions"] = dict(
                (get_scene(ctx.chat.id, ctx.chat).get("positions") or {}))
            return {"views": {}}

        monkeypatch.setitem(runtime.STEP_HANDLERS, "perception_act",
                            capturing_perception)

        list(_run_pipeline(chat_id, turn_id, only_key="perception_act"))

        # The rerolled onset stage saw the PRE-turn positions, not the
        # post-commit outcome -- no outcome knowledge leaked in.
        assert seen["positions"].get("Alice") == "kitchen"

    def test_incomplete_turn_reroll_does_not_restore(
        self, temp_db, monkeypatch,
    ):
        """Guard: an only_key reroll on a turn whose commit step never ran
        (an interrupted turn being resumed) must NOT roll the world back."""
        chat_id = _make_chat(temp_db)
        _make_cast(temp_db, chat_id, ["Alice"])
        turn_id = _make_turn(temp_db, chat_id, idx=1)
        temp_db.wset(chat_id, "scene", _scene({"Alice": "kitchen"}))

        # Seed pre-commit steps but NO commit step.
        for i, key in enumerate(["director_interpret", "mapping_quick", "perception_act"]):
            save_step(turn_id, key, key, i,
                      {"flow": {"needs_mapping": False, "reactors": [],
                                "resolution_flags": {}}}
                      if key == "director_interpret" else {"views": {}})
        # Live world drifted to 'study' after the checkpoint was taken; a
        # non-committed reroll must leave it alone.
        temp_db.wset(chat_id, "scene", _scene({"Alice": "study"}))

        seen = {}

        def capturing_perception(ctx, nonce):
            seen["positions"] = dict(
                (get_scene(ctx.chat.id, ctx.chat).get("positions") or {}))
            return {"views": {}}

        monkeypatch.setitem(runtime.STEP_HANDLERS, "perception_act",
                            capturing_perception)
        list(_run_pipeline(chat_id, turn_id, only_key="perception_act"))
        assert seen["positions"].get("Alice") == "study"


# ---- #11: ctx.character_results / reaction_results rehydrated on resume ----

class TestRehydrateLoopResultsHelper:
    def test_interaction_loop_content_rebuilds_character_results(self):
        ctx = PipelineContext(
            chat=ChatData(id=1, name="", persona_id=None, lorebook_id=None,
                          scenario="", created=0.0),
            turn=TurnData(id=1, chat_id=1, idx=1, player_input="", created=0.0),
            cast=[], input="")
        content = {
            "character_results": {"7": {"name": "Bea", "sequence": [],
                                        "mind_model_updates": [{"x": 1}]}},
            "rounds": [{"speaker_id": 9, "result": {"name": "Cid", "sequence": []}}],
        }
        _rehydrate_loop_results(ctx, "interaction_loop", content)
        assert ctx.character_results[7]["mind_model_updates"] == [{"x": 1}]
        # Rounds fallback recovers a speaker missing from the results map.
        assert ctx.character_results[9]["name"] == "Cid"
        assert ctx.reaction_results == {}

    def test_reaction_loop_content_rebuilds_reaction_results(self):
        ctx = PipelineContext(
            chat=ChatData(id=1, name="", persona_id=None, lorebook_id=None,
                          scenario="", created=0.0),
            turn=TurnData(id=1, chat_id=1, idx=1, player_input="", created=0.0),
            cast=[], input="")
        content = {
            "reaction_results": {"3": {"name": "Alice", "sequence": []}},
            "rounds": [{"reactor_id": 5, "result": {"name": "Bob", "sequence": []}}],
        }
        _rehydrate_loop_results(ctx, "reaction_loop", content)
        assert ctx.reaction_results[3]["name"] == "Alice"
        assert ctx.reaction_results[5]["name"] == "Bob"
        assert ctx.character_results == {}

    def test_freshly_computed_result_is_not_clobbered(self):
        ctx = PipelineContext(
            chat=ChatData(id=1, name="", persona_id=None, lorebook_id=None,
                          scenario="", created=0.0),
            turn=TurnData(id=1, chat_id=1, idx=1, player_input="", created=0.0),
            cast=[], input="")
        ctx.character_results[7] = {"name": "fresh"}
        _rehydrate_loop_results(
            ctx, "interaction_loop",
            {"character_results": {"7": {"name": "stale"}}, "rounds": []})
        assert ctx.character_results[7]["name"] == "fresh"


class TestResumePopulatesCharacterResults:
    def test_resume_from_narrator_repopulates_character_results(
        self, temp_db, monkeypatch,
    ):
        chat_id = _make_chat(temp_db)
        ids, _ = _make_cast(temp_db, chat_id, ["Alice"])
        alice = ids["Alice"]
        temp_db.wset(chat_id, "dialogue_config", {"autonomy": 50})
        temp_db.wset(chat_id, "scene", _scene({"Alice": "kitchen"}))
        turn_id = _make_turn(temp_db, chat_id, idx=1)

        alice_result = {
            "name": "Alice",
            "sequence": [{"type": "speech", "text": "I chose to speak."}],
            "active_state": {"mood": "wary"},
            "mind_model_updates": [{"about": "player", "note": "hostile"}],
            "stance_updates": [{"target": "player", "trust": -0.1}],
        }

        def fake_character_step(ctx, char_id, nonce):
            return dict(alice_result)

        monkeypatch.setattr(agents.loops, "character_step", fake_character_step)
        # Keep the loop's per-round bookkeeping off the (real) scene helpers.
        monkeypatch.setattr(agents.loops, "deterministic_micro_perception",
                            lambda *a, **k: ({}, set()))

        # autonomy>0 + reactors -> an interaction_loop step (not parallel
        # character:<id> steps).
        _stub_handlers(monkeypatch, reactors=[alice], contested=False)

        list(_run_pipeline(chat_id, turn_id))

        # The interaction_loop persisted its speaker into step content.
        loop_content = active_content(turn_id, "interaction_loop")
        assert loop_content is not None
        assert str(alice) in (loop_content.get("character_results") or {})

        # Now resume from narrator; capture ctx.character_results as commit
        # would see it.
        captured = {}

        def capturing_narrator(ctx, nonce):
            captured["results"] = {k: dict(v) for k, v in ctx.character_results.items()}
            return {"prose": "ok"}

        _stub_handlers(monkeypatch, reactors=[alice], contested=False,
                       overrides={"narrator": capturing_narrator})

        list(_run_pipeline(chat_id, turn_id, from_key="narrator"))

        assert alice in captured["results"], (
            "resumed turn left ctx.character_results empty -> commit would "
            "mint no character memories/mind-model/stance updates")
        rehydrated = captured["results"][alice]
        assert rehydrated["mind_model_updates"] == alice_result["mind_model_updates"]
        assert rehydrated["stance_updates"] == alice_result["stance_updates"]
        assert rehydrated["active_state"] == alice_result["active_state"]
