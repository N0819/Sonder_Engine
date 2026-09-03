"""The Writers' Room bench (`tools/room_bench.py`): it runs only on a copy,
derives the beat's walk from what was published, reads every stage of the
beat against the ledgers, checks what needs no model, and asks the critic
in the rubric's shape. No model and no network here: the critic is stubbed.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time

import pytest

from tools import room_bench as rb

PLAYER = "The Stranger"


def _story(db):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Bench", "A tannery town.", time.time()))
    db.wset(cid, "scene", {"location": "Town", "rooms": {
        "quay": {"name": "Quay", "desc": "Wet stone.",
                 "adjacent": [{"to": "warehouse", "barrier": "open_door"}]},
        "warehouse": {"name": "Warehouse", "desc": "Crates.",
                      "adjacent": [{"to": "quay", "barrier": "open_door"}]},
    }, "positions": {PLAYER: "quay"}, "entities": {}, "attire": {}})
    for i in range(3):
        db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
              (cid, i, "", time.time()))
    return cid


def _package(uid="plot:x", status="published"):
    return {"uid": uid, "title": "The Tannery Lane", "premise": "p", "status": status,
            "truths": [], "questions": [], "operations": [
                {"op": "plan_rooms", "structure": {"key": "lane"}, "rooms": {
                    "tannery_lane": {"name": "Tannery Lane",
                                     "adjacent": [{"to": "quay"}, {"to": "lime_pits"}]},
                    "lime_pits": {"name": "Lime Pits", "adjacent": [{"to": "tannery_lane"}]},
                    "far_gate": {"name": "Far Gate", "adjacent": [{"to": "nowhere_at_all"}]},
                }},
                {"op": "plan_entity", "kind": "person", "name": "Korin", "aliases": ["the cobbler"],
                 "brief": {"where": "tannery_lane"}},
            ]}


class TestTheCopy:
    def test_the_harness_refuses_anything_but_a_copy(self, tmp_path):
        with pytest.raises(SystemExit):
            rb.require_copy("/srv/stories/engine.db")
        with pytest.raises(SystemExit):
            rb.require_copy(str(tmp_path / "engine.db"))
        assert rb.require_copy(str(tmp_path / "bench.db"))  # under the tempdir
        assert rb.require_copy("/somewhere/room-bench-abc/bench.db")
        assert rb.require_copy("/srv/agent/jobs/j1/tmp/copy.db")

    def test_prepare_copy_backs_up_over_a_read_only_connection(self, tmp_path, monkeypatch):
        source = tmp_path / "source.db"
        con = sqlite3.connect(str(source))
        con.execute("CREATE TABLE t(x)")
        con.execute("INSERT INTO t VALUES (7)")
        con.commit()
        con.close()
        monkeypatch.setenv("ENGINE_DB", os.environ.get("ENGINE_DB", ""))
        workdir, copy = rb.prepare_copy(str(source))
        assert os.path.basename(workdir).startswith(rb.SCRATCH_PREFIX)
        assert os.environ["ENGINE_DB"] == copy and rb.require_copy(copy)
        assert sqlite3.connect(copy).execute("SELECT x FROM t").fetchone()[0] == 7
        # The source is untouched and still readable read-only.
        assert sqlite3.connect("file:%s?mode=ro" % source, uri=True).execute(
            "SELECT count(*) FROM t").fetchone()[0] == 1

    def test_model_overrides_land_only_for_real_roles(self, temp_db):
        out = rb.set_model_overrides(planner="3:google/gemini-3.7-flash",
                                     dramaturge="6:accounts/fireworks/routers/glm")
        assert out["story_planner"] == {"provider": 3, "model": "google/gemini-3.7-flash"}
        from core.db import get_setting
        from llm import providers
        models = json.loads(get_setting("agent_models"))
        assert models["story_planner"]["model"] == "google/gemini-3.7-flash"
        if "dramaturge" not in providers.ROLES:
            assert "ignored" in out["dramaturge"]
            assert "dramaturge" not in models


class TestTheWalk:
    def test_package_plan_reads_rooms_and_people_from_operations(self):
        rooms, people = rb.package_plan([_package()])
        assert set(rooms) == {"tannery_lane", "lime_pits", "far_gate"}
        assert rooms["tannery_lane"]["adjacent"] == ["quay", "lime_pits"]
        assert people == [{"name": "Korin", "kind": "person", "aliases": ["the cobbler"],
                           "where": "tannery_lane"}]

    def test_the_walk_goes_into_the_planned_room_beside_the_player(self, temp_db):
        cid = _story(temp_db)
        rid, text = rb.derive_walk(cid, None, [_package()])
        assert rid == "tannery_lane" and "Tannery Lane" in text
        assert rb.derive_walk(cid, None, []) == (None, None)


class TestReadingTheBeat:
    def _turn(self, db, cid, contents):
        tid = db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
                    (cid, 3, "You step through.", time.time()))
        for ordn, (key, content) in enumerate(contents):
            sid = db.qi("INSERT INTO steps(turn_id,key,label,ord) VALUES(?,?,?,?)",
                        (tid, key, key, ordn))
            db.qi("INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
                  (sid, json.dumps(content), time.time()))
            # An inactive earlier variant must not be read.
            db.qi("INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,0)",
                  (sid, json.dumps({"stale": True}), time.time()))
        return tid

    def test_read_stages_takes_the_active_variant_and_its_warnings(self, temp_db):
        cid = _story(temp_db)
        tid = self._turn(temp_db, cid, [
            ("director_interpret", {"flow": {}}),
            ("narrator", {"prose": "Korin looks up from his last.",
                          "_engine_notes": {"warnings": ["scrubbed unearned identities"]}}),
        ])
        stages, warnings = rb.read_stages(tid)
        assert set(stages) == {"director_interpret", "narrator"}
        assert stages["narrator"]["prose"].startswith("Korin")
        assert warnings == {"narrator": ["scrubbed unearned identities"]}

    def test_measure_reads_the_stages_against_the_ledgers(self, temp_db):
        from world.planned_entities import add_planned_entity, planned_entities
        from world.planning_needs import file_planning_need, planning_needs
        cid = _story(temp_db)
        plan = add_planned_entity(cid, {"kind": "person", "name": "Korin",
                                        "brief": {"where": "tannery_lane"}})
        before_plans = planned_entities(cid)
        before_needs = planning_needs(cid)
        tid = self._turn(temp_db, cid, [
            ("compile_world_context", {"movement": {"to_room": "tannery_lane",
                                                    "status": "planned"}}),
            ("director_resolve", {"state_diff": {
                "entities": {"korin": {"name": "Korin", "plan_ref": {"uid": plan["uid"]}},
                             "cart": {"name": "a handcart"}},
                "positions": {PLAYER: "tannery_lane"}}}),
            ("character:7", {"speech": ""}),
            ("narrator", {"prose": "The cobbler, Korin, nods without looking up."}),
        ])
        # After the beat: the render settled and a need was filed.
        plans = planned_entities(cid)
        plans[plan["uid"]]["rendered"] = {"entity_id": "korin", "turn": 3, "render": "lean"}
        from world.planned_entities import save_planned_entities
        save_planned_entities(cid, plans)
        file_planning_need(cid, {"kind": "thing", "surface": {"name": "the ledger"}})
        stages, warnings = rb.read_stages(tid)
        m = rb.measure(cid, None, before_plans=before_plans, before_needs=before_needs,
                       stages=stages, warnings=warnings, pkgs=[_package()])
        assert m["movement"] == {"to_room": "tannery_lane", "status": "planned"}
        assert m["player_moved_to"] == "tannery_lane"
        assert m["rendered_planned_figures"] == [
            {"entity": "korin", "name": "Korin", "plans": ["Korin"]}]
        assert m["floor_bound"] == [{"entity": "korin", "plan_ref": {"uid": plan["uid"]}}]
        assert m["settled_plans"] == [plan["uid"]]
        assert [n["subject"] for n in m["planning_needs_filed"]] == ["the ledger"]
        assert m["narrator_mentions"] == ["Korin", "the cobbler"]
        assert m["character_steps"] == ["character:7"]
        assert m["warning_count"] == 0


class TestTheCritic:
    def test_deterministic_checks_name_each_class(self, temp_db):
        cid = _story(temp_db)
        # A held identity: a registered character named Korin.
        char = temp_db.qi("INSERT INTO characters(name,sheet,created) VALUES(?,?,?)",
                          ("Korin", json.dumps({"name": "Korin"}), time.time()))
        temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status) VALUES(?,?,?)",
                   (cid, char, "active"))
        findings = rb.deterministic_checks(
            cid, None, [_package()],
            reply="I prepared the Tannery Lane and Korin.", published=[])
        checks = {f["check"] for f in findings}
        assert checks == {"reserved_name", "exit_to_nowhere", "outside_mandate",
                          "reply_claims_unlanded"}
        nowhere = [f for f in findings if f["check"] == "exit_to_nowhere"]
        assert len(nowhere) == 1 and "nowhere_at_all" in nowhere[0]["detail"]

    def test_the_checks_are_quiet_when_nothing_is_wrong(self, temp_db):
        from story import mandates as md
        cid = _story(temp_db)
        md.grant_mandate(cid, None, text="You may plan rooms and people.",
                         capabilities=["plan_rooms", "plan_entity", "create_people"])
        pkg = _package()
        pkg["operations"][0]["rooms"].pop("far_gate")
        assert rb.deterministic_checks(cid, None, [pkg], reply="Done: the Tannery Lane.",
                                       published=[pkg["uid"]]) == []

    def test_the_critic_answers_in_the_rubric_shape(self, temp_db, monkeypatch):
        from llm import providers
        asked = {}

        def script(role, system, user, **kw):
            asked["role"] = role
            asked["payload"] = json.loads(user)
            return json.dumps({"scores": {
                "naturalness": {"score": 4, "reason": "The cobbler's kettle is a habit."},
                "consistency": {"score": 5, "reason": "Nothing crosses the lore."},
                "agreement": {"score": 9, "reason": "Only what was granted."},
                "specificity": {"score": "3", "reason": "Named trades, few objects."},
                "setup": {"score": 2, "reason": "Furniture; nothing owed later."}},
                "contradictions": ["The reply says a stoop; no room is a stoop."]})
        monkeypatch.setattr(providers, "chat_complete", script)
        out = rb.critique(pkgs=[_package()], grant="You may plan rooms.",
                          lore_hits=[{"citation": "lore:1"}], narration="Korin nods.",
                          reply="Prepared.", transcript=[{"tool": "new_package",
                                                          "result": {"uid": "x"}}])
        assert asked["role"] == "utility"
        assert asked["payload"]["grant"] == "You may plan rooms."
        assert out["scores"]["agreement"]["score"] == 5  # clamped
        assert out["scores"]["specificity"]["score"] == 3
        assert out["contradictions"] == ["The reply says a stoop; no room is a stoop."]

    def test_a_shapeless_critic_is_an_error_not_a_verdict(self, temp_db, monkeypatch):
        from llm import providers
        monkeypatch.setattr(providers, "chat_complete",
                            lambda *a, **k: "I think it was fine.")
        out = rb.critique(pkgs=[], grant="g", lore_hits=[], narration="", reply="",
                          transcript=[])
        assert "error" in out and "scores" not in out


class TestTheReport:
    def test_the_report_is_written_as_markdown_and_json(self, tmp_path):
        summary = {"chat": 1, "frame_id": None, "copy": "/tmp/room-bench-x/bench.db",
                   "grant": "You may plan.", "models": {},
                   "planner": {"seconds": 12.3, "out": {"steps": 3, "calls": 5,
                                                        "stopped": None,
                                                        "published": ["plot:x"],
                                                        "reply": "Done."},
                               "calls": [{"tool": "new_package", "seconds": 0.0,
                                          "result": {"uid": "plot:x"}}]},
                   "beat": {"input": "You step.", "seconds": 30.1, "failed": None,
                            "stages": {"narrator": 9.0, "director_resolve": 12.0}},
                   "measures": {"movement": {"status": "planned"}, "player_moved_to": "lane",
                                "planned_rooms": ["lane"], "planned_people": ["Korin"],
                                "rendered_planned_figures": [], "floor_bound": [],
                                "settled_plans": [], "planning_needs_filed": [],
                                "narrator_mentions": ["Korin"], "narration": "Korin nods.",
                                "warnings": {"narrator": ["w"]}, "warning_count": 1,
                                "character_steps": []},
                   "checks": [], "critic": {"scores": {a: {"score": 3, "reason": "r"}
                                                       for a in rb.CRITIC_AXES},
                                            "contradictions": []},
                   "roles": [{"role": "narrator", "model": "m", "calls": 1, "seconds": 9.0}]}
        md, js = rb.write_report(str(tmp_path / "out"), summary)
        text = open(md, encoding="utf-8").read()
        assert "## Measures" in text and "Korin" in text and "## Critic" in text
        assert json.load(open(js))["planner"]["out"]["published"] == ["plot:x"]
