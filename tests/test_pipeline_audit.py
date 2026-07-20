"""Regression tests for a verified pipeline audit:

1. Contested turn at autonomy=0 ran every reactor's character_step twice
   (reaction_loop + unconditional parallel character:<id> steps) and then
   dropped the parallel steps' speech from dialogue_log entirely, while
   perception_outcome still injected their actions.
2. perception_outcome built the primary player's perceiver before extra
   players were appended to `sources`, so co-players had no spatial/visual
   channel to each other (multiplayer only).
3. An only_key reroll skipped the stale-upstream check the from_key paths
   make, silently consuming stale hydrated content and stamping the step
   fresh on top of it.
4. A from_key rerun with a MISSING director_interpret proceeded on `{}` and
   only failed the materialization assert after commit had already run; an
   unknown from_key silently degraded into a full recompute.
5. The narrator did a durable wset (narration_person) mid-pipeline, before
   commit -- violating "commit.py is the sole persistence boundary".
6. _normalise_views dropped a model-returned "Player"/"Extra:<id>" view key
   instead of casefolding it onto the canonical perceiver id, and
   _chat_has_extra_players ignored frames, adding a spurious narrator_extra
   step for co-players stationed in another frame.
"""

from __future__ import annotations

import json
import time

import pytest

import agents.loops
import agents.runtime as runtime
from agents.runtime import (
    StaleStepError, _chat_has_extra_players, _run_pipeline, build_plan,
)
from agents.storage import active_content, mark_steps_stale, save_step, variant_count
from character_schema import default_character_data, default_persona_data
from pipeline_context import ChatData, PipelineContext, TurnData


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


def _make_persona(db, name="Extra Player"):
    sheet = default_persona_data(name)
    return db.qi(
        "INSERT INTO personas(name,sheet,source,resource_uid) VALUES(?,?,?,?)",
        (name, json.dumps(sheet), json.dumps({"format": "native"}),
         f"persona_{name.lower().replace(' ', '_')}"),
    )


def _basic_scene(positions=None):
    return {
        "location": "Old Manor", "time": "evening",
        "rooms": {
            "kitchen": {"name": "Kitchen", "desc": "", "adjacent": [
                {"to": "hallway", "barrier": "open", "distance": "near"}]},
            "hallway": {"name": "Hallway", "desc": "", "adjacent": [
                {"to": "kitchen", "barrier": "open", "distance": "near"},
                {"to": "study", "barrier": "open", "distance": "near"}]},
            "study": {"name": "Study", "desc": "", "adjacent": [
                {"to": "hallway", "barrier": "open", "distance": "near"}]},
        },
        "positions": positions or {},
        "entities": {}, "overlays": {}, "attire": {},
    }


def _make_ctx(db, chat_id, turn_id, cast_rows=None, idx=1, player_input=""):
    return PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=idx,
                      player_input=player_input, created=time.time()),
        cast=cast_rows or [], input=player_input,
    )


def _stub_handlers(monkeypatch, overrides=None, reactors=None, contested=False):
    """Stub every LLM stage handler; build_plan and reaction_loop stay real."""
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


# ---- bug 1: contested turn at autonomy=0 double-ran reactors ----

class TestContestedAutonomyZeroPlan:
    def test_contested_autonomy_zero_has_no_parallel_character_steps(self, temp_db):
        chat_id = _make_chat(temp_db)
        ids, cast_rows = _make_cast(temp_db, chat_id, ["Alice", "Bob"])
        temp_db.wset(chat_id, "dialogue_config", {"autonomy": 0})
        interp = {"flow": {
            "needs_mapping": False,
            "reactors": list(ids.values()),
            "resolution_flags": {"contested": True},
        }}
        keys = [k for k, _ in build_plan(interp, cast_rows, chat_id=chat_id)]
        assert "reaction_loop" in keys
        assert not any(k.startswith("character:") for k in keys)
        assert "interaction_loop" not in keys

    def test_uncontested_autonomy_zero_keeps_parallel_character_steps(self, temp_db):
        chat_id = _make_chat(temp_db)
        ids, cast_rows = _make_cast(temp_db, chat_id, ["Alice", "Bob"])
        temp_db.wset(chat_id, "dialogue_config", {"autonomy": 0})
        interp = {"flow": {
            "needs_mapping": False,
            "reactors": list(ids.values()),
            "resolution_flags": {},
        }}
        keys = [k for k, _ in build_plan(interp, cast_rows, chat_id=chat_id)]
        assert "reaction_loop" not in keys
        assert [k for k in keys if k.startswith("character:")] == [
            f"character:{cid}" for cid in ids.values()
        ]

    def test_contested_positive_autonomy_keeps_interaction_loop(self, temp_db):
        chat_id = _make_chat(temp_db)
        ids, cast_rows = _make_cast(temp_db, chat_id, ["Alice"])
        temp_db.wset(chat_id, "dialogue_config", {"autonomy": 50})
        interp = {"flow": {
            "needs_mapping": False,
            "reactors": list(ids.values()),
            "resolution_flags": {"contested": True},
        }}
        keys = [k for k, _ in build_plan(interp, cast_rows, chat_id=chat_id)]
        assert "reaction_loop" in keys
        assert "interaction_loop" in keys
        assert not any(k.startswith("character:") for k in keys)

    def test_contested_autonomy_zero_runs_each_reactor_exactly_once(
        self, temp_db, monkeypatch,
    ):
        chat_id = _make_chat(temp_db)
        ids, _ = _make_cast(temp_db, chat_id, ["Alice"])
        alice = ids["Alice"]
        temp_db.wset(chat_id, "dialogue_config", {"autonomy": 0})
        temp_db.wset(chat_id, "scene", _basic_scene({"Alice": "kitchen"}))
        turn_id = _make_turn(temp_db, chat_id, idx=1)

        calls = []

        def fake_character_step(ctx, char_id, nonce):
            calls.append(char_id)
            return {"name": "Alice",
                    "sequence": [{"type": "speech", "text": "Back off!"}]}

        monkeypatch.setattr(agents.loops, "character_step", fake_character_step)
        monkeypatch.setattr(runtime, "character_step", fake_character_step)

        captured = {}

        def fake_resolve(ctx, nonce):
            captured["reaction_rounds"] = (ctx.reaction_loop or {}).get("rounds")
            return {"dialogue_log": [], "state_diff": {}}

        _stub_handlers(monkeypatch, reactors=[alice], contested=True,
                       overrides={"director_resolve": fake_resolve})

        list(_run_pipeline(chat_id, turn_id))

        # Exactly one character_step call for the reactor -- previously two
        # (once via reaction_loop, once via the parallel character:<id> step).
        assert calls == [alice]
        keys = {r["key"] for r in temp_db.q(
            "SELECT key FROM steps WHERE turn_id=?", (turn_id,))}
        assert "reaction_loop" in keys
        assert not any(k.startswith("character:") for k in keys)
        # The reactor's declared speech reached director_resolve.
        rounds = captured["reaction_rounds"]
        assert rounds and rounds[0]["result"]["sequence"][0]["text"] == "Back off!"


class TestDirectorResolveMergesUncoveredCharacterResults:
    def test_parallel_step_speech_is_not_dropped_when_loop_declarations_exist(
        self, temp_db, monkeypatch,
    ):
        """A character whose result lives only in ctx.character_results (a
        parallel character:<id> step) must still reach dialogue_log even
        when reaction/interaction declarations exist for OTHER characters.
        Previously any loop declaration made director_resolve ignore
        ctx.character_results entirely."""
        import agents.director as director

        chat_id = _make_chat(temp_db)
        ids, cast_rows = _make_cast(temp_db, chat_id, ["Alice", "Bob"])
        temp_db.wset(chat_id, "scene",
                     _basic_scene({"Alice": "kitchen", "Bob": "kitchen",
                                   "The Stranger": "kitchen"}))
        turn_id = _make_turn(temp_db, chat_id, idx=2)
        ctx = _make_ctx(temp_db, chat_id, turn_id, cast_rows, idx=2,
                        player_input="I step forward.")
        ctx["director_interpret"] = {"flow": {"dice": [],
                                              "resolution_flags": {}},
                                     "sequence": [], "movement": None}
        ctx["mapping_quick"] = {"relevant_lore": []}
        ctx["reaction_loop"] = {"rounds": [{
            "round": 0, "reactor_id": ids["Alice"], "reactor": "Alice",
            "result": {"sequence": [
                {"type": "speech", "text": "Stay where you are."}]},
        }]}
        ctx.character_results[ids["Bob"]] = {
            "name": "Bob",
            "sequence": [{"type": "speech", "text": "Everyone calm down."}],
        }

        seen = {}

        def fake_agent_json(role, step_key, system, payload, **kw):
            seen["payload"] = payload
            return {"resolved_event": "Voices overlap.", "summary": "beat",
                    "dialogue_log": [], "state_diff": {}}

        monkeypatch.setattr(director, "_agent_json", fake_agent_json)
        monkeypatch.setattr(director, "validate_llm_output",
                            lambda key, out: (out, []))

        out = director.director_resolve(ctx, 0)

        declared_names = {d.get("name") for d in
                          seen["payload"]["character_declarations"]}
        assert {"Alice", "Bob"} <= declared_names

        by_speaker = {}
        for d in out["dialogue_log"]:
            by_speaker.setdefault(d["speaker"], []).append(d["exact_quote"])
        assert any("Stay where you are." in quote
                   for quote in by_speaker.get("Alice", []))
        # This is the line that was silently dropped before the fix.
        assert any("Everyone calm down." in quote
                   for quote in by_speaker.get("Bob", []))

    def test_loop_covered_character_is_not_duplicated(self, temp_db, monkeypatch):
        """interaction_loop stores its speakers in ctx.character_results too;
        those ids are covered by loop declarations and must not be merged a
        second time."""
        import agents.director as director

        chat_id = _make_chat(temp_db)
        ids, cast_rows = _make_cast(temp_db, chat_id, ["Alice"])
        temp_db.wset(chat_id, "scene",
                     _basic_scene({"Alice": "kitchen", "The Stranger": "kitchen"}))
        turn_id = _make_turn(temp_db, chat_id, idx=2)
        ctx = _make_ctx(temp_db, chat_id, turn_id, cast_rows, idx=2)
        ctx["director_interpret"] = {"flow": {"dice": [],
                                              "resolution_flags": {}},
                                     "sequence": [], "movement": None}
        ctx["mapping_quick"] = {"relevant_lore": []}
        result = {"name": "Alice",
                  "sequence": [{"type": "speech", "text": "Hello there."}]}
        ctx["interaction_loop"] = {"combined_declarations": [{
            "char_id": ids["Alice"], "name": "Alice",
            "sequence": result["sequence"],
        }], "rounds": []}
        ctx.character_results[ids["Alice"]] = result

        monkeypatch.setattr(
            director, "_agent_json",
            lambda *a, **kw: {"resolved_event": "x", "summary": "x",
                              "dialogue_log": [], "state_diff": {}})
        monkeypatch.setattr(director, "validate_llm_output",
                            lambda key, out: (out, []))

        out = director.director_resolve(ctx, 0)
        alice_lines = [d for d in out["dialogue_log"]
                       if d["speaker"] == "Alice"]
        assert len(alice_lines) == 1


# ---- bug 2: co-players missing from each other's perception sources ----

class TestPerceptionOutcomeMultiplayerSources:
    def test_every_player_has_a_channel_to_every_other_player(
        self, temp_db, monkeypatch,
    ):
        import agents.perception as perception

        chat_id = _make_chat(temp_db)
        temp_db.wset(chat_id, "scene", _basic_scene({
            "The Stranger": "kitchen",
            "Extra One": "hallway",
            "Extra Two": "study",
        }))
        turn_id = _make_turn(temp_db, chat_id, idx=2)
        ctx = _make_ctx(temp_db, chat_id, turn_id, [], idx=2,
                        player_input="I look around.")
        ctx.extra_players = [
            {"persona_id": 11, "name": "Extra One", "pronouns": {},
             "appearance": "", "idle": False, "input": "I wave."},
            {"persona_id": 12, "name": "Extra Two", "pronouns": {},
             "appearance": "", "idle": True, "input": ""},
        ]
        ctx["director_interpret"] = {"flow": {"reactors": []}, "sequence": [],
                                     "other_players": {}}
        ctx["director_resolve"] = {"resolved_event": "", "dialogue_log": [],
                                   "state_diff": {}}

        seen = {}

        def fake_agent_json(role, step_key, system, payload, **kw):
            seen["payload"] = payload
            return {"views": {}}

        monkeypatch.setattr(perception, "_agent_json", fake_agent_json)

        perception.perception_outcome(ctx, 0)

        perceivers = {p["id"]: p for p in seen["payload"]["perceivers"]}
        # The primary player's perceiver was previously built before any
        # extra player entered `sources`.
        player_spatial = perceivers["player"]["spatial_to_sources"]
        assert "Extra One" in player_spatial
        assert "Extra Two" in player_spatial
        assert "Extra One" in perceivers["player"]["visual_channel_to_sources"]
        # Each co-player must have a channel to the OTHER co-player (before
        # the fix, extra:11 was built before Extra Two was appended).
        assert "Extra Two" in perceivers["extra:11"]["spatial_to_sources"]
        assert "Extra One" in perceivers["extra:12"]["spatial_to_sources"]
        assert "The Stranger" in perceivers["extra:11"]["spatial_to_sources"]


# ---- bug 3: only_key reroll skipped the stale-upstream check ----

class TestOnlyKeyStaleUpstream:
    def _seed_steps(self, temp_db, chat_id):
        turn_id = _make_turn(temp_db, chat_id, idx=1)
        plan = [("director_interpret", "Director"), ("mapping_quick", "Mapping"),
                ("narrator", "Narrator")]
        for i, (key, label) in enumerate(plan):
            save_step(turn_id, key, label, i,
                      {"flow": {}} if key == "director_interpret"
                      else {"prose": "old"} if key == "narrator"
                      else {"relevant_lore": []})
        return turn_id

    def test_only_key_reroll_refuses_a_stale_upstream_step(
        self, temp_db, monkeypatch,
    ):
        chat_id = _make_chat(temp_db)
        turn_id = self._seed_steps(temp_db, chat_id)
        mark_steps_stale(turn_id, ["mapping_quick"])
        monkeypatch.setitem(runtime.STEP_HANDLERS, "narrator",
                            lambda ctx, nonce: {"prose": "new"})

        with pytest.raises(StaleStepError):
            list(_run_pipeline(chat_id, turn_id, only_key="narrator"))

        # Refused with NO side effects: no new variant, target not re-stamped,
        # downstream not marked stale.
        assert variant_count(turn_id, "narrator") == 1
        assert active_content(turn_id, "narrator") == {"prose": "old"}
        row = temp_db.q(
            "SELECT stale FROM steps WHERE turn_id=? AND key='narrator'",
            (turn_id,), one=True)
        assert not row["stale"]

    def test_only_key_reroll_of_the_stale_step_itself_is_allowed(
        self, temp_db, monkeypatch,
    ):
        chat_id = _make_chat(temp_db)
        turn_id = self._seed_steps(temp_db, chat_id)
        mark_steps_stale(turn_id, ["mapping_quick"])
        monkeypatch.setitem(runtime.STEP_HANDLERS, "mapping_quick",
                            lambda ctx, nonce: {"relevant_lore": ["fresh"]})

        events = list(_run_pipeline(chat_id, turn_id, only_key="mapping_quick"))
        assert events[-1]["type"] == "done"
        assert active_content(turn_id, "mapping_quick") == {"relevant_lore": ["fresh"]}

    def test_only_key_reroll_adds_a_variant_without_mutating_the_old_one(
        self, temp_db, monkeypatch,
    ):
        chat_id = _make_chat(temp_db)
        turn_id = self._seed_steps(temp_db, chat_id)
        monkeypatch.setitem(runtime.STEP_HANDLERS, "narrator",
                            lambda ctx, nonce: {"prose": "new"})

        events = list(_run_pipeline(chat_id, turn_id, only_key="narrator"))
        assert events[-1]["type"] == "done"

        assert variant_count(turn_id, "narrator") == 2
        step = temp_db.q(
            "SELECT id FROM steps WHERE turn_id=? AND key='narrator'",
            (turn_id,), one=True)
        rows = temp_db.q(
            "SELECT content, active FROM variants WHERE step_id=? ORDER BY id",
            (step["id"],))
        contents = [json.loads(r["content"]) for r in rows]
        assert contents == [{"prose": "old"}, {"prose": "new"}]
        assert [r["active"] for r in rows] == [0, 1]


# ---- bug 4: from_key rerun with a missing director_interpret ----

class TestFromKeyMissingInterpret:
    def test_missing_interpret_restarts_from_director_interpret(
        self, temp_db, monkeypatch,
    ):
        chat_id = _make_chat(temp_db)
        turn_id = _make_turn(temp_db, chat_id, idx=1)
        _stub_handlers(monkeypatch)
        list(_run_pipeline(chat_id, turn_id))

        # Simulate an absent (not stale) director_interpret step.
        step = temp_db.q(
            "SELECT id FROM steps WHERE turn_id=? AND key='director_interpret'",
            (turn_id,), one=True)
        temp_db.qi("DELETE FROM variants WHERE step_id=?", (step["id"],))
        temp_db.qi("DELETE FROM steps WHERE id=?", (step["id"],))

        calls = {"interpret": 0}

        def counting_interpret(ctx, nonce):
            calls["interpret"] += 1
            return {"flow": {"needs_mapping": False, "reactors": [],
                             "resolution_flags": {}}}

        _stub_handlers(monkeypatch,
                       overrides={"director_interpret": counting_interpret})

        events = list(_run_pipeline(chat_id, turn_id, from_key="narrator"))
        assert events[-1]["type"] == "done"
        # Restarted from director_interpret instead of substituting {} and
        # failing the materialization assert only after commit.
        assert calls["interpret"] == 1
        assert isinstance(active_content(turn_id, "director_interpret"), dict)

    def test_unknown_from_key_raises_instead_of_full_recompute(
        self, temp_db, monkeypatch,
    ):
        chat_id = _make_chat(temp_db)
        turn_id = _make_turn(temp_db, chat_id, idx=1)
        _stub_handlers(monkeypatch)
        list(_run_pipeline(chat_id, turn_id))

        counts_before = {
            r["key"]: variant_count(turn_id, r["key"]) for r in temp_db.q(
                "SELECT key FROM steps WHERE turn_id=?", (turn_id,))
        }

        with pytest.raises(RuntimeError, match="not in this turn's plan"):
            list(_run_pipeline(chat_id, turn_id, from_key="bogus_step"))

        # Refused before any side effect: nothing recomputed, nothing stale.
        counts_after = {
            r["key"]: variant_count(turn_id, r["key"]) for r in temp_db.q(
                "SELECT key FROM steps WHERE turn_id=?", (turn_id,))
        }
        assert counts_after == counts_before
        assert all(not r["stale"] for r in temp_db.q(
            "SELECT stale FROM steps WHERE turn_id=?", (turn_id,)))

    def test_valid_from_key_rerun_still_rerolls_downstream_only(
        self, temp_db, monkeypatch,
    ):
        chat_id = _make_chat(temp_db)
        turn_id = _make_turn(temp_db, chat_id, idx=1)
        _stub_handlers(monkeypatch)
        list(_run_pipeline(chat_id, turn_id))

        _stub_handlers(monkeypatch, overrides={
            "narrator": lambda ctx, nonce: {"prose": "second draft"}})
        events = list(_run_pipeline(chat_id, turn_id, from_key="narrator"))
        assert events[-1]["type"] == "done"

        assert variant_count(turn_id, "narrator") == 2
        assert variant_count(turn_id, "director_interpret") == 1
        assert active_content(turn_id, "narrator") == {"prose": "second draft"}
        assert all(not r["stale"] for r in temp_db.q(
            "SELECT stale FROM steps WHERE turn_id=?", (turn_id,)))


# ---- bug 5: narrator wrote narration_person durably before commit ----

class TestNarrationPersonDeferredToCommit:
    def test_resolver_records_into_pending_instead_of_writing(self, temp_db):
        from agents.narration import _resolve_narration_person

        chat_id = _make_chat(temp_db)
        pending = {}
        got = _resolve_narration_person(
            chat_id, "I open the door.", "Alex", {"subj": "he"},
            pending=pending)
        assert got == "first"
        assert pending == {"narration_person": "first"}
        assert temp_db.wget(chat_id, "narration_person", None) is None

    def test_resolver_without_pending_keeps_direct_write(self, temp_db):
        from agents.narration import _resolve_narration_person

        chat_id = _make_chat(temp_db)
        got = _resolve_narration_person(
            chat_id, "I open the door.", "Alex", {"subj": "he"})
        assert got == "first"
        assert temp_db.wget(chat_id, "narration_person", None) == "first"

    def test_narrator_stage_defers_the_write_onto_its_step_content(
        self, temp_db, monkeypatch,
    ):
        import agents.narration as narration

        chat_id = _make_chat(temp_db)
        turn_id = _make_turn(temp_db, chat_id, idx=1,
                             player_input="I open the door.")
        ctx = _make_ctx(temp_db, chat_id, turn_id, [], idx=1,
                        player_input="I open the door.")
        ctx["director_interpret"] = {"sequence": [], "speech": None}
        ctx["perception_outcome"] = {"views": {"player": "The hallway is quiet."}}

        monkeypatch.setattr(
            narration, "_agent_json",
            lambda *a, **kw: {"prose": "The door creaks open.",
                              "new_specifics": []})
        monkeypatch.setattr(narration, "validate_llm_output",
                            lambda key, out: (out, []))

        out = narration.narrator(ctx, 0)

        # No durable write happened during the narrator stage itself.
        assert temp_db.wget(chat_id, "narration_person", None) is None
        # The detected person rides the returned step content for commit.
        assert out["narration_person_writes"] == {"narration_person": "first"}

    def test_commit_applies_the_deferred_writes(self, temp_db):
        from commit import commit_narration_person

        chat_id = _make_chat(temp_db)
        turn_id = _make_turn(temp_db, chat_id, idx=1)
        ctx = _make_ctx(temp_db, chat_id, turn_id, [], idx=1)
        ctx["narrator"] = {
            "prose": "x",
            "narration_person_writes": {"narration_person": "first"},
        }
        ctx["narrator_extra"] = {"7": {
            "prose": "y",
            "narration_person_writes": {"narration_person:extra:7": "third"},
        }}

        result = commit_narration_person(ctx, 0)
        assert result == {"applied": 2}
        assert temp_db.wget(chat_id, "narration_person", None) == "first"
        assert temp_db.wget(chat_id, "narration_person:extra:7", None) == "third"

    def test_commit_rejects_unknown_keys_and_values(self, temp_db):
        from commit import commit_narration_person

        chat_id = _make_chat(temp_db)
        turn_id = _make_turn(temp_db, chat_id, idx=1)
        ctx = _make_ctx(temp_db, chat_id, turn_id, [], idx=1)
        ctx["narrator"] = {"narration_person_writes": {
            "narration_person": "fourth",       # not a valid person
            "scene": {"rooms": {}},              # not a narration_person key
        }}

        result = commit_narration_person(ctx, 0)
        assert result == {"applied": 0}
        assert temp_db.wget(chat_id, "narration_person", None) is None
        assert temp_db.wget(chat_id, "scene", None) is None

    def test_commit_all_wires_the_domain(self):
        import inspect

        import commit
        source = inspect.getsource(commit._commit_all_locked)
        assert "commit_narration_person" in source


# ---- bug 6a: _normalise_views dropped "Player"/"Extra:<id>" keys ----

class TestNormaliseViewsCasefoldsSpecialIds:
    def test_capitalised_player_and_extra_keys_fold_onto_canonical_ids(self):
        from agents.common import _normalise_views

        perceivers = [
            {"id": "player", "name": "Alex"},
            {"id": "extra:7", "name": "Bea"},
            {"id": 3, "name": "Cid"},
        ]
        raw = {"Player": "view one", "Extra:7": "view two", "3": "view three"}
        clean = _normalise_views(raw, perceivers)
        assert clean == {"player": "view one", "extra:7": "view two",
                         "3": "view three"}

    def test_player_key_still_dropped_when_no_player_perceiver(self):
        from agents.common import _normalise_views

        perceivers = [{"id": 3, "name": "Cid"}]
        clean = _normalise_views({"Player": "x", "Cid": "y"}, perceivers)
        assert "player" not in clean and "Player" not in clean
        assert clean == {"3": "y"}


# ---- bug 6b: _chat_has_extra_players ignored frames ----

class TestExtraPlayersFrameFilter:
    def _attach(self, db, chat_id, persona_id, frame_id=None):
        db.qi(
            "INSERT INTO chat_personas(chat_id,persona_id,status,frame_id) "
            "VALUES(?,?,'active',?)",
            (chat_id, persona_id, frame_id),
        )

    def test_other_frame_co_player_does_not_count_for_the_present(self, temp_db):
        chat_id = _make_chat(temp_db)
        frame_id = temp_db.qi(
            "INSERT INTO frames(chat_id,label,created) VALUES(?,?,?)",
            (chat_id, "past era", time.time()),
        )
        persona_id = _make_persona(temp_db)
        self._attach(temp_db, chat_id, persona_id, frame_id=frame_id)

        assert _chat_has_extra_players(chat_id) is False
        assert _chat_has_extra_players(chat_id, frame_id) is True

    def test_build_plan_narrator_extra_respects_the_frame(self, temp_db):
        chat_id = _make_chat(temp_db)
        frame_id = temp_db.qi(
            "INSERT INTO frames(chat_id,label,created) VALUES(?,?,?)",
            (chat_id, "past era", time.time()),
        )
        persona_id = _make_persona(temp_db)
        self._attach(temp_db, chat_id, persona_id, frame_id=frame_id)

        present_keys = [k for k, _ in build_plan({}, [], chat_id=chat_id)]
        framed_keys = [k for k, _ in build_plan({}, [], chat_id=chat_id,
                                                frame_id=frame_id)]
        assert "narrator_extra" not in present_keys
        assert "narrator_extra" in framed_keys

    def test_same_frame_none_still_counts(self, temp_db):
        chat_id = _make_chat(temp_db)
        persona_id = _make_persona(temp_db)
        self._attach(temp_db, chat_id, persona_id, frame_id=None)
        assert _chat_has_extra_players(chat_id) is True
        keys = [k for k, _ in build_plan({}, [], chat_id=chat_id)]
        assert "narrator_extra" in keys
