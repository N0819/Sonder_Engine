"""The deterministic reactive rung: authored plans, no hidden agent call."""

from __future__ import annotations

import json
import time
import types


class _Chat(dict):
    @property
    def id(self):
        return self["id"]


class _Ctx(types.SimpleNamespace):
    def add_warning(self, message):
        self.warnings.append(str(message))


def _world(temp_db, *, enabled=True):
    cid = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()))
    sheet = json.dumps({
        "identity": {"name": "Mora", "uid": "mora_uid"},
        "simulation": {"tier": "major"},
    })
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        ("Mora", sheet, "{}", time.time()))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state,sheet) "
        "VALUES(?,?,?,'{}','')", (cid, char_id, "active"))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, 1, "", time.time()))
    temp_db.wset(cid, "dialogue_config", {
        "offscreen_life": "reactive", "max_offscreen_actors": 3})
    temp_db.wset(cid, "living_world", {
        "antagonist_ladder": "floor" if enabled else "off"})
    scene = {
        "location": "Citadel",
        "rooms": {"war_room": {"name": "War Room", "adjacent": []}},
        "positions": {"Mora": "war_room"},
    }
    op = {
        "op": "open", "plan_id": "seal-the-gate", "actor": "Mora",
        "objective": "Seal the gate after the warning bell",
        "basis": "I will seal the gate after the warning bell",
        "stages": [{
            "stage_id": "orders",
            "trigger": {"after_seconds": 60},
            "effect": {
                "what": "the citadel gate is sealed",
                "where": "war_room", "due_seconds": 3600,
                "witnessed": "Mora issued the order", "originator": "Mora",
            },
        }],
    }
    ctx = _Ctx(
        chat=_Chat(id=cid), turn=types.SimpleNamespace(
            id=turn_id, idx=1, frame_id=None),
        cast=[{"id": char_id, "sheet": sheet}],
        character_results={char_id: {
            "sequence": [{"type": "speech",
                          "text": "I will seal the gate after the warning bell."}],
            "intent_ops": [], "project_ops": [],
        }},
        director_resolve={"state_diff": {"offscreen_plan_ops": [op]}},
        director_establish=None, warnings=[],
    )
    return cid, char_id, scene, ctx, op


class TestPlanAuthoring:
    def test_a_grounded_plan_is_frame_state(self, temp_db):
        from db import wget
        from offscreen import apply_plan_ops

        cid, _, scene, ctx, _ = _world(temp_db)
        result = apply_plan_ops(ctx, scene, {"elapsed_seconds": 0})
        assert result["applied"] == 1 and result["active"] == 1
        plan = wget(cid, "offscreen_plans", [])[0]
        assert plan["actor_id"] == "mora_uid"
        assert plan["stages"][0]["trigger"]["due_at"] == 60.0
        assert plan["stages"][0]["effect"]["where"] == "war_room"

    def test_the_mechanism_setting_gates_the_write(self, temp_db):
        from db import wget
        from offscreen import apply_plan_ops

        cid, _, scene, ctx, _ = _world(temp_db, enabled=False)
        result = apply_plan_ops(ctx, scene, {"elapsed_seconds": 0})
        assert result == {"offered": 1, "applied": 0, "active": 0,
                          "warnings": 1, "enabled": False}
        assert wget(cid, "offscreen_plans", []) == []

    def test_the_director_cannot_invent_an_absent_minds_plan(self, temp_db):
        from db import wget
        from offscreen import apply_plan_ops

        cid, _, scene, ctx, _ = _world(temp_db)
        ctx.character_results = {}
        result = apply_plan_ops(ctx, scene, {"elapsed_seconds": 0})
        assert result["applied"] == 0 and result["warnings"] == 1
        assert wget(cid, "offscreen_plans", []) == []

    def test_an_unrelated_basis_is_refused(self, temp_db):
        from offscreen import apply_plan_ops

        _, _, scene, ctx, _ = _world(temp_db)
        ctx.director_resolve["state_diff"]["offscreen_plan_ops"][0]["basis"] = (
            "Perhaps the northern fleet changes course")
        result = apply_plan_ops(ctx, scene, {"elapsed_seconds": 0})
        assert result["applied"] == 0
        assert any("basis is not grounded" in w for w in ctx.warnings)

    def test_a_character_can_cancel_their_own_plan(self, temp_db):
        from db import wget
        from offscreen import apply_plan_ops

        cid, _, scene, ctx, _ = _world(temp_db)
        apply_plan_ops(ctx, scene, {"elapsed_seconds": 0})
        ctx.director_resolve["state_diff"]["offscreen_plan_ops"] = [{
            "op": "cancel", "plan_id": "seal-the-gate", "actor": "Mora",
            "basis": "I will seal the gate after the warning bell",
        }]
        result = apply_plan_ops(ctx, scene, {"elapsed_seconds": 10})
        assert result["applied"] == 1 and result["active"] == 0
        assert wget(cid, "offscreen_plans", [])[0]["status"] == "cancelled"

    def test_dict_sheets_keep_their_display_name(self, temp_db):
        from db import wget
        from offscreen import apply_plan_ops

        cid, _, scene, ctx, _ = _world(temp_db)
        ctx.cast[0]["sheet"] = json.loads(ctx.cast[0]["sheet"])
        result = apply_plan_ops(ctx, scene, {"elapsed_seconds": 0})
        assert result["applied"] == 1
        assert wget(cid, "offscreen_plans", [])[0]["actor_display"] == "Mora"

    def test_plan_state_restores_with_a_checkpoint(self, temp_db):
        from checkpoints import ensure_checkpoint, restore_checkpoint
        from db import wget, wset
        from offscreen import apply_plan_ops

        cid, _, scene, ctx, _ = _world(temp_db)
        apply_plan_ops(ctx, scene, {"elapsed_seconds": 0})
        original = wget(cid, "offscreen_plans", [])
        ensure_checkpoint(cid, 2)
        wset(cid, "offscreen_plans", [])
        restore_checkpoint(cid, 2)
        assert wget(cid, "offscreen_plans", []) == original


class TestPlanFiring:
    def test_crossing_a_plan_deadline_creates_its_own_epoch(self, temp_db):
        from db import transaction, wget
        from offscreen import advance_epoch, apply_plan_ops

        cid, _, scene, ctx, _ = _world(temp_db)
        apply_plan_ops(ctx, scene, {"elapsed_seconds": 0})
        ctx.turn = types.SimpleNamespace(
            id=temp_db.qi(
                "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
                (cid, 2, "", time.time())), idx=2, frame_id=None)
        with transaction():
            result = advance_epoch(ctx, {
                "scene": scene, "prev_scene": scene,
                "prev_clock": {"elapsed_seconds": 30},
                "clock": {"elapsed_seconds": 60},
            }, {})
        assert result["reasons"] == ["reactive_due"]
        assert result["reactive_fired"] == 1
        assert wget(cid, "offscreen_plans", [])[0]["status"] == "completed"

    def test_a_due_stage_mints_its_preauthored_effect_and_completes(self,
                                                                   temp_db):
        from db import transaction, wget
        from offscreen import advance_reactive_plans, apply_plan_ops

        cid, _, scene, ctx, _ = _world(temp_db)
        apply_plan_ops(ctx, scene, {"elapsed_seconds": 0})
        ctx.turn = types.SimpleNamespace(
            id=temp_db.qi(
                "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
                (cid, 2, "", time.time())), idx=2, frame_id=None)
        with transaction():
            result = advance_reactive_plans(
                ctx, scene, {"elapsed_seconds": 60}, {}, "epoch_due")
        assert result == {"reactive_considered": 1, "reactive_fired": 1,
                          "reactive_effect_opportunities": 1,
                          "reactive_effects_minted": 1}
        plan = wget(cid, "offscreen_plans", [])[0]
        assert plan["status"] == "completed"
        row = temp_db.q(
            "SELECT * FROM scheduled_events WHERE chat_id=?", (cid,), one=True)
        assert row["status"] == "pending" and row["seed"] == "epoch_due"
        assert json.loads(row["payload"])["what"] == "the citadel gate is sealed"

    def test_an_event_trigger_is_narrowed_by_kind_and_location(self, temp_db):
        from db import transaction, wget
        from offscreen import advance_reactive_plans, apply_plan_ops

        cid, _, scene, ctx, op = _world(temp_db)
        op["stages"][0]["trigger"] = {
            "event_kind": "news_arrival", "location": "war_room"}
        apply_plan_ops(ctx, scene, {"elapsed_seconds": 0})
        ctx.turn = types.SimpleNamespace(
            id=temp_db.qi(
                "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
                (cid, 2, "", time.time())), idx=2, frame_id=None)
        with transaction():
            missed = advance_reactive_plans(ctx, scene, {}, {
                "fired_events": [{"kind": "news_arrival",
                                  "location_id": "elsewhere"}]}, "epoch_a")
        assert missed["reactive_fired"] == 0
        with transaction():
            hit = advance_reactive_plans(ctx, scene, {}, {
                "fired_events": [{"kind": "news_arrival",
                                  "location_id": "war_room"}]}, "epoch_b")
        assert hit["reactive_fired"] == 1
        assert wget(cid, "offscreen_plans", [])[0]["status"] == "completed"

    def test_the_reactive_path_has_no_provider_call(self):
        import inspect
        import offscreen

        source = inspect.getsource(offscreen.advance_reactive_plans)
        assert "providers" not in source
        assert "chat_complete" not in source


def test_schema_keeps_plan_ops():
    from schemas import validate_llm_output

    out, warnings = validate_llm_output("director_resolve", {
        "state_diff": {"offscreen_plan_ops": [{
            "op": "open", "plan_id": "p", "actor": "Mora",
            "objective": "wait", "basis": "I will wait",
            "stages": [{"stage_id": "s", "trigger": {"after_seconds": 60}}],
        }]},
    })
    assert not warnings
    assert out["state_diff"]["offscreen_plan_ops"][0]["plan_id"] == "p"
