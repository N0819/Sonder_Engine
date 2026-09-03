"""Local drama, the nudge toolkit, firing clocks and region events
(`story/plot_packages.py` Phase C kinds, `world/charter_surgery.py`,
`world/region_events.py`).

THE CLASS. Every kind authors a circumstance that arrives -- a body comes,
is sent, is told, an institution's numbers move, a place is damaged -- and
lands through a seam the world already has, under a grant the player made
in words. The Director rules what happens when the player meets it; no kind
writes the player's conduct or a mind. A package clock is the fuse.
"""
from __future__ import annotations

import json
import time

import pytest

from story.plot_packages import (
    OPERATIONS, OPERATION_FIELDS, activate_due_packages, authority_errors,
    draft_operation, edit_package, fire_due_clocks, get_package, new_package,
    package_requirements, preview_package, publish_package, validate_package)

PLAYER = "Wren Ashby"


def _body(name, place, post="", **extra):
    out = {"name": name, "place": place, "berth": place, "competence": {},
           "available": True, "home_post": post}
    out.update(extra)
    return out


def _registry():
    return {"items": {"hall": {"state": {
        "key": "hall", "priority": [], "clock_hours": 10.0,
        "upkeeps": {"court": {"place": "hall", "level": 0.9},
                    "stores": {"place": "warehouse", "level": 0.9}},
        "posts": {"reeve": {"place": "hall", "serves": ["court"], "requires": {},
                            "reports_to": "reeve"},
                  "clerk": {"place": "warehouse", "serves": ["stores"],
                            "requires": {}, "reports_to": "reeve"}},
        "bodies": {"r1": _body("Halin Nook", "hall", "reeve"),
                   "c1": _body("Osric Fell", "warehouse", "clerk"),
                   "w1": _body("Bran Gate", "lane"),
                   "w2": _body("Tam Ashwell", "lane")},
        "watch": {"reeve": "r1", "clerk": "c1"},
        "economy": {"goods": {"grain": {"label": "grain"}},
                    "stocks": {"hall": {"grain": 10.0}}},
    }}}}


def _scene():
    def room(name, *exits):
        return {"name": name, "desc": name + ".",
                "adjacent": [{"to": e, "barrier": "open_door"} for e in exits]}
    return {"location": "Port", "rooms": {
        "quay": room("Quay", "warehouse"),
        "warehouse": room("Warehouse", "quay", "lane"),
        "lane": room("Lane", "warehouse", "hall"),
        "hall": room("Hall", "lane"),
        # The inside of a body: where the world put somebody.
        "inside_mara": {"name": "inside Mara", "desc": "Dark.",
                        "parent_entity": "Mara", "adjacent": [{"to": "quay"}]},
    }, "positions": {PLAYER: "quay", "Mara": "quay", "Pip": "inside_mara"},
        "entities": {"Mara": {"name": "Mara"}}, "attire": {}}


def _story(db, *, turns=3):
    from world.charter_runtime import save_registry
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Drama", "A port at dusk.", time.time()))
    db.wset(cid, "scene", _scene())
    db.wset(cid, "simulation_clock", {"elapsed_seconds": 0.0})
    save_registry(cid, _registry())
    ids = [db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
                 (cid, i, "", time.time())) for i in range(turns)]
    return cid, ids


def _pkg(cid, ops=(), *, created_by="writers_room", **fields):
    head = {k: fields.pop(k) for k in ("spoiler_policy", "authority", "scope")
            if k in fields}
    pkg = new_package(cid, title="The Morning After", premise="p",
                      created_by=created_by, **head)
    if fields:
        edit_package(cid, pkg["uid"], fields)
    for op in ops:
        draft_operation(cid, pkg["uid"], op)
    return pkg["uid"]


def _rev(cid, uid):
    return get_package(cid, uid)["revision"]


def _charter(cid):
    from world.charter_runtime import registry_for
    return registry_for(cid)["items"]["hall"]["state"]


def _publish(cid, uid):
    validate_package(cid, uid)
    return publish_package(cid, uid, expected_revision=_rev(cid, uid))


# ---------------------------------------------------------------------------
# The table
# ---------------------------------------------------------------------------

def test_every_kind_has_fields_and_a_seam():
    assert set(OPERATION_FIELDS) == set(OPERATIONS)
    for kind in ("arrival", "errand", "incident", "summons", "scheduled_consequence",
                 "move_body", "assign_post", "plant_claim", "adjust_stock",
                 "arm_trigger", "charter_shock", "region_event"):
        assert kind in OPERATIONS and OPERATIONS[kind]["seam"]
    from story.room_tools import TOOL_INDEX
    for kind in OPERATIONS:
        assert kind in TOOL_INDEX["draft_operation"]["description"]


class TestShapes:
    def test_each_kind_refuses_what_it_cannot_do_without(self, temp_db):
        cid, _ = _story(temp_db)
        uid = _pkg(cid)
        for op, why in [
            ({"op": "arrival", "room": "quay"}, "who arrives"),
            ({"op": "arrival", "who": "Osric Fell"}, "the room"),
            ({"op": "errand", "charter": "hall", "body": "c1"}, "where the body"),
            ({"op": "incident", "room": "quay"}, "what happens"),
            ({"op": "summons", "charter": "hall", "post": "reeve"}, "whom it calls"),
            ({"op": "scheduled_consequence", "summary": "x"}, "clock it"),
            ({"op": "move_body", "body": "c1", "room": "quay"}, "names the charter"),
            ({"op": "region_event", "footprint": {"rooms": ["quay"]}}, "kind of change"),
            ({"op": "region_event", "label": "fire", "footprint": {}}, "footprint names"),
            ({"op": "region_event", "label": "fire", "footprint": {"rooms": ["quay"]},
              "profile": {"mode": "sideways"}}, "mode is one of"),
            ({"op": "incident", "room": "quay", "summary": "s", "shock": 4}, "0..1"),
        ]:
            with pytest.raises(ValueError, match=why):
                draft_operation(cid, uid, op)


# ---------------------------------------------------------------------------
# Local drama lands through the seams
# ---------------------------------------------------------------------------

class TestLocalDrama:
    def test_arrival_errand_incident_summons_and_a_placed_letter_land(self, temp_db):
        from story.artifacts import standing_artifacts
        from story.authored_events import due_authored_events
        from world.planned_entities import add_planned_entity, planned_entities
        cid, _ = _story(temp_db)
        add_planned_entity(cid, {"kind": "person", "name": "Verger Hale",
                                 "brief": {"where": "hall"}})
        uid = _pkg(cid, authority={"may_schedule_harm": True}, ops=[
            {"op": "arrival", "who": "hall/c1", "room": "quay", "carrying": "a writ"},
            {"op": "arrival", "who": "Verger Hale", "room": "lane"},
            {"op": "errand", "charter": "hall", "body": "r1", "to": "quay",
             "purpose": "to see the tide"},
            {"op": "incident", "room": "warehouse", "summary": "a stack of crates falls",
             "shock": 0.4, "harms": [{"charter": "hall", "body": "w1", "outcome": "hurt"}]},
            {"op": "summons", "charter": "hall", "post": "reeve", "target": "Tam Ashwell",
             "place": "hall", "terms": "answer for the crates"},
            {"op": "post_artifact", "room": "quay", "description": "a letter under the door",
             "text": "Come at dawn."},
        ])
        preview = preview_package(cid, uid)
        assert preview["errors"] == [], preview["errors"]
        assert [c["kind"] for c in preview["changes"]] == [
            "arrival", "arrival", "errand", "incident", "summons", "artifact_posted"]
        out = _publish(cid, uid)
        assert all(a["result"] for a in out["applied"])
        hall = _charter(cid)
        # The clerk was moved by the author's hand, and the hand is recorded.
        assert hall["bodies"]["c1"]["place"] == "quay"
        assert [a["op"] for a in hall["authored"]][:1] == ["move_body"]
        assert hall["authored"][0]["by"].startswith("writers_room:plot:")
        # The plan now stands in the lane.
        assert planned_entities(cid)[list(planned_entities(cid))[0]]["brief"]["where"] == "lane"
        # The reeve walks: a route, not a teleport, with the errand kept.
        assert hall["bodies"]["r1"]["walk"]["target"] == "quay"
        assert hall["bodies"]["r1"]["errand"]["purpose"] == "to see the tide"
        assert hall["bodies"]["r1"]["place"] == "hall"
        # The incident shocked the upkeep served in the warehouse and hurt w1
        # through the harm model, which the institution will witness.
        shocks = [r for r in hall["interventions"] if r["op"] == "upkeep_shock"]
        assert shocks and shocks[0]["upkeep"] == "stores" and shocks[0]["delta"] == -0.4
        assert hall["bodies"]["w1"]["condition"] == "hurt"
        assert any(e["kind"] == "harm_done" and e["subject"] == "w1"
                   for e in hall["carried_events"])
        # The summons is a commitment from the reeve toward Tam.
        (commitment,) = hall["commitments"].values()
        assert commitment["kind"] == "summons" and commitment["promisor"] == "r1"
        assert commitment["beneficiary"] == "Tam Ashwell" and commitment["state"] == "proposed"
        # Each circumstance is a notice the Director renders next beat.
        due = sorted(d["summary"] for d in due_authored_events(cid, 3))
        assert any("Osric Fell arrives at quay, carrying a writ" == s for s in due)
        assert any("Verger Hale arrives at lane" == s for s in due)
        assert any("crates falls" in s for s in due)
        assert any("Tam Ashwell is summoned to hall by the reeve" in s for s in due)
        assert standing_artifacts(cid)[0]["text"] == "Come at dawn."

    def test_what_the_world_does_not_hold_is_refused_at_preview(self, temp_db):
        cid, _ = _story(temp_db)
        uid = _pkg(cid, authority={"may_schedule_harm": True}, ops=[
            {"op": "arrival", "who": "Nobody Known", "room": "quay"},
            {"op": "arrival", "who": "hall/c1", "room": "nowhere"},
            {"op": "errand", "charter": "hall", "body": "zz", "to": "quay"},
            {"op": "summons", "charter": "hall", "post": "mayor", "target": "Tam Ashwell"},
            {"op": "summons", "charter": "hall", "post": "reeve", "target": "A Stranger"},
            {"op": "incident", "room": "lane", "summary": "a scuffle",
             "harms": [{"charter": "hall", "body": "nobody"}]},
        ])
        errors = preview_package(cid, uid)["errors"]
        assert any("nobody the world holds matches" in e for e in errors)
        assert any("exists nowhere" in e for e in errors)
        assert any("holds no body 'zz'" in e for e in errors)
        assert any("has no post 'mayor'" in e for e in errors)
        assert any("whom the world does not hold" in e for e in errors)
        assert any("holds no body 'nobody'" in e for e in errors)
        # A shock nobody serves is a warning, not an error.
        uid2 = _pkg(cid, ops=[{"op": "incident", "room": "quay", "summary": "gulls"}])
        result = preview_package(cid, uid2)
        assert result["errors"] == [] and any("shocks nobody" in w for w in result["warnings"])

    def test_the_dead_are_not_moved(self, temp_db):
        from world.charter_runtime import registry_for_update, save_registry
        cid, _ = _story(temp_db)
        reg = registry_for_update(cid)
        reg["items"]["hall"]["state"]["bodies"]["w1"]["condition"] = "dead"
        save_registry(cid, reg)
        uid = _pkg(cid, ops=[{"op": "move_body", "charter": "hall", "body": "w1",
                              "room": "quay"}])
        assert any("does not move the dead" in e for e in preview_package(cid, uid)["errors"])


# ---------------------------------------------------------------------------
# The nudge toolkit
# ---------------------------------------------------------------------------

class TestSurgery:
    def test_the_six_surgeries_move_facts_and_are_recorded(self, temp_db):
        cid, _ = _story(temp_db)
        uid = _pkg(cid, ops=[
            {"op": "move_body", "charter": "hall", "body": "w1", "room": "hall", "berth": True},
            {"op": "assign_post", "charter": "hall", "body": "w1", "post": "clerk"},
            {"op": "plant_claim", "charter": "hall", "body": "r1",
             "text": "the tide will take the lower quay tonight", "told_by": "a fisher"},
            {"op": "adjust_stock", "charter": "hall", "holder": "hall", "good": "grain",
             "delta": -4},
            {"op": "arm_trigger", "charter": "hall", "rule": {
                "id": "crates_open_a_quarrel", "on": "event:incident",
                "then": [{"op": "open_practice", "kind": "quarrel", "a": "nearby",
                          "b": "subject"}]}},
            {"op": "charter_shock", "charter": "hall", "intervention": {
                "op": "need_shock", "body": "r1", "need": "rest", "delta": -0.3}},
        ])
        preview = preview_package(cid, uid)
        # The need shock names a need the body does not keep: refused on
        # the intervention module's terms at the window, not here.
        assert preview["errors"] == [], preview["errors"]
        _publish(cid, uid)
        hall = _charter(cid)
        w1 = hall["bodies"]["w1"]
        assert w1["place"] == "hall" and w1["berth"] == "hall"
        assert hall["watch"]["clerk"] == "w1" and w1["home_post"] == "clerk"
        claim = next(iter(hall["minds"]["r1"].values()))
        assert claim["provenance"] == "authored" and claim["heard_from"] == "a fisher"
        assert claim["claim_text"].startswith("the tide")
        assert hall["economy"]["stocks"]["hall"]["grain"] == 6.0
        assert any(r["id"] == "crates_open_a_quarrel" for r in hall["triggers"])
        assert any(r["op"] == "need_shock" for r in hall["interventions"])
        assert [a["op"] for a in hall["authored"]] == [
            "move_body", "assign_post", "plant_claim", "adjust_stock",
            "arm_trigger", "charter_shock"]

    def test_a_surgery_refuses_on_its_own_terms(self, temp_db):
        cid, _ = _story(temp_db)
        uid = _pkg(cid, ops=[
            {"op": "adjust_stock", "charter": "hall", "holder": "hall", "good": "silk",
             "delta": 1},
            {"op": "plant_claim", "charter": "hall", "body": "r1", "text": "x"},
            {"op": "arm_trigger", "charter": "hall", "rule": {"on": "weather:rain",
                                                             "then": []}},
            {"op": "charter_shock", "charter": "hall", "intervention": {"op": "smite"}},
            {"op": "assign_post", "charter": "nowhere", "body": "r1", "post": "reeve"},
        ])
        errors = preview_package(cid, uid)["errors"]
        assert any("stocks no good 'silk'" in e for e in errors)
        assert any("names who told them" in e for e in errors)
        assert any("unknown change kind" in e for e in errors)
        assert any("unknown intervention op" in e for e in errors)
        assert any("no charter 'nowhere'" in e for e in errors)
        # A hurt body's post survives; a dead one's does not.
        assert "condition" in _charter(cid)["bodies"]["r1"]

    def test_a_planner_package_needs_each_capability_by_name(self, temp_db):
        from story.mandates import grant_mandate
        cid, _ = _story(temp_db)
        uid = _pkg(cid, created_by="story_planner", ops=[
            {"op": "arrival", "who": "hall/c1", "room": "quay"},
            {"op": "plant_claim", "charter": "hall", "body": "r1", "text": "t",
             "told_by": "a fisher"},
            {"op": "region_event", "label": "flood", "footprint": {"rooms": ["quay"]},
             "profile": {"intensity": 0.3}, "effects": {"destroy": False}},
        ])
        pkg = get_package(cid, uid)
        assert package_requirements(pkg) == ["arrival", "plant_claim", "region_events"]
        (refused,) = authority_errors(cid, None, pkg)
        assert "arrival, plant_claim, region_events" in refused
        grant_mandate(cid, None, text="You may have people arrive and tell them things.",
                      capabilities=["arrival", "plant_claim"])
        (refused,) = authority_errors(cid, None, get_package(cid, uid))
        assert "region_events" in refused and "arrival" not in refused
        grant_mandate(cid, None, text="Flood the quay if you must.",
                      capabilities=["region_events"])
        assert authority_errors(cid, None, get_package(cid, uid)) == []


# ---------------------------------------------------------------------------
# Clocks fire
# ---------------------------------------------------------------------------

class TestClocks:
    def test_a_due_clock_lands_what_rode_it_and_a_rewind_unfires(self, temp_db):
        from persist.checkpoints import ensure_checkpoint, restore_checkpoint
        from story.authored_events import due_authored_events
        cid, turn_ids = _story(temp_db)
        ensure_checkpoint(cid, 2)
        uid = _pkg(cid, clocks=[{"id": "clock_inquest", "label": "the inquest",
                                 "due_turns": 2}], ops=[
            {"op": "scheduled_consequence", "clock": "clock_inquest",
             "summary": "the inquest opens", "room": "hall"},
            {"op": "arrival", "who": "hall/c1", "room": "hall", "clock": "clock_inquest"},
            {"op": "post_artifact", "room": "quay", "description": "a notice of inquest",
             "clock": "clock_inquest"},
            {"op": "move_body", "charter": "hall", "body": "w1", "room": "hall"},
        ])
        out = _publish(cid, uid)
        # Riding the clock: deferred at publish; the plain surgery landed.
        assert [a["result"] for a in out["applied"]][:3] == [
            {"deferred": "clock_inquest"}] * 3
        assert _charter(cid)["bodies"]["w1"]["place"] == "hall"
        assert _charter(cid)["bodies"]["c1"]["place"] == "warehouse"
        assert due_authored_events(cid, 3) == []
        # Not due yet: published at turn 2, due_turns 2 -> turn 4.
        assert fire_due_clocks(cid, 3)["fired"] == []
        fired = fire_due_clocks(cid, 4, turn_id=turn_ids[-1])
        assert fired["fired"] == [(uid, "clock_inquest")]
        pkg = get_package(cid, uid)
        assert pkg["clocks"][0]["fired_turn"] == 4
        assert all(op.get("applied") for op in pkg["operations"])
        assert [h["action"] for h in pkg["provenance"]["history"]][-1] == "clock_fired"
        assert _charter(cid)["bodies"]["c1"]["place"] == "hall"
        assert sorted(d["summary"] for d in due_authored_events(cid, 5)) == [
            "Osric Fell arrives at hall", "the inquest opens (at hall)"]
        from story.artifacts import standing_artifacts
        assert standing_artifacts(cid)[0]["description"] == "a notice of inquest"
        # Firing twice lands nothing twice.
        assert fire_due_clocks(cid, 5)["fired"] == []
        # A rewind past the fire: the world row restores the clock unfired
        # and the world unaffected, and the clock fires again when due.
        restore_checkpoint(cid, 2)
        assert get_package(cid, uid) is None or get_package(cid, uid)["status"] == "draft"
        assert _charter(cid)["bodies"]["c1"]["place"] == "warehouse"
        assert due_authored_events(cid, 5) == []

    def test_a_clock_is_due_by_story_hours_too(self, temp_db):
        cid, _ = _story(temp_db)
        uid = _pkg(cid, clocks=[{"id": "clock_tide", "label": "the tide",
                                 "due_story_hours": 6}], ops=[
            {"op": "scheduled_consequence", "clock": "clock_tide",
             "summary": "the tide takes the lower quay"}])
        _publish(cid, uid)
        assert fire_due_clocks(cid, 3, elapsed=5 * 3600.0)["fired"] == []
        assert fire_due_clocks(cid, 3, elapsed=6 * 3600.0)["fired"] == [(uid, "clock_tide")]

    def test_a_world_that_moved_under_the_fuse_refuses_the_operation(self, temp_db):
        from world.charter_runtime import registry_for_update, save_registry
        cid, turn_ids = _story(temp_db)
        uid = _pkg(cid, clocks=[{"id": "clock_x", "label": "x", "due_turns": 1}], ops=[
            {"op": "arrival", "who": "hall/c1", "room": "hall", "clock": "clock_x"},
            {"op": "scheduled_consequence", "clock": "clock_x", "summary": "bells"}])
        _publish(cid, uid)
        reg = registry_for_update(cid)
        reg["items"]["hall"]["state"]["bodies"]["c1"]["condition"] = "dead"
        save_registry(cid, reg)
        fire_due_clocks(cid, 3, turn_id=turn_ids[-1])
        pkg = get_package(cid, uid)
        arrival, bells = pkg["operations"]
        assert arrival.get("applied") is None and "does not move the dead" in \
            arrival["refused"]["errors"][0]
        assert bells["applied"]["notice"] == 1
        assert any(h["action"] == "operation_refused" for h in pkg["provenance"]["history"])

    def test_a_clock_whose_mandate_was_withdrawn_does_not_fire(self, temp_db):
        from story.mandates import _key, grant_mandate
        cid, _ = _story(temp_db)
        row = grant_mandate(cid, None, text="Ring bells when you like.",
                            capabilities=["scheduled_consequence"])
        uid = _pkg(cid, created_by="story_planner",
                   clocks=[{"id": "clock_b", "label": "b", "due_turns": 1}],
                   ops=[{"op": "scheduled_consequence", "clock": "clock_b",
                         "summary": "bells"}])
        _publish(cid, uid)
        # The panel's revoke flips the row; here by hand on the same row.
        rows = temp_db.wget(cid, _key(), [])
        for r in rows:
            if r["uid"] == row["uid"]:
                r["status"], r["revoked_turn"] = "revoked", 2
        temp_db.wset(cid, _key(), rows)
        assert fire_due_clocks(cid, 3)["fired"] == []
        pkg = get_package(cid, uid)
        assert pkg["clocks"][0]["refused_turn"] == 3
        assert any(h["action"] == "clock_refused" for h in pkg["provenance"]["history"])

    def test_a_clock_an_operation_names_must_exist(self, temp_db):
        cid, _ = _story(temp_db)
        uid = _pkg(cid, ops=[{"op": "scheduled_consequence", "clock": "clock_none",
                              "summary": "x"}])
        assert any("no clock of this package" in e for e in preview_package(cid, uid)["errors"])


# ---------------------------------------------------------------------------
# Region events
# ---------------------------------------------------------------------------

class TestRegionEvents:
    def test_at_once_damages_shocks_harms_and_leaves_evidence(self, temp_db):
        from story.artifacts import standing_artifacts
        from story.authored_events import due_authored_events
        cid, turn_ids = _story(temp_db)
        uid = _pkg(cid, authority={"may_schedule_harm": True}, ops=[{
            "op": "region_event", "label": "a fire along the warehouses",
            "footprint": {"epicentre": "warehouse", "radius_hops": 1},
            "profile": {"mode": "at_once", "intensity": 0.5},
            "effects": {"damage": "burning", "shock": 0.5,
                        "harm": {"outcome": "hurt", "fraction": 0.5},
                        "artifacts": ["charred timbers"], "news": "fire in the warehouses"},
        }])
        preview = preview_package(cid, uid)
        assert preview["errors"] == [], preview["errors"]
        (change,) = preview["changes"]
        assert change["rooms"] == ["warehouse", "lane", "quay"] and change["waves"] == 1
        assert "inside_mara" not in change["rooms"]
        out = _publish(cid, uid)
        first = out["applied"][0]["result"]["first"]
        assert sorted(first["damaged"]) == ["lane", "quay", "warehouse"] and first["ruined"] == []
        scene = temp_db.wget(cid, "scene")
        assert scene["rooms"]["warehouse"]["hazard"]["state"] == "burning"
        assert "hazard" not in scene["rooms"]["hall"]
        hall = _charter(cid)
        shocks = [r for r in hall["interventions"] if r["op"] == "upkeep_shock"]
        assert [s["upkeep"] for s in shocks] == ["stores"] and shocks[0]["delta"] == -0.25
        # Harm is by the harm model and bounded by the quota; who is hurt is
        # a stable draw, so the report is the same on every run.
        assert len(first["harmed"]) <= 2
        assert standing_artifacts(cid)[0]["description"] == "charred timbers"
        assert [d["summary"] for d in due_authored_events(cid, 3)] == ["fire in the warehouses"]

    def test_ruin_retires_the_room_and_displaces_who_slept_there(self, temp_db):
        cid, turn_ids = _story(temp_db)
        temp_db.qi("INSERT INTO room_registry(chat_id,room_uid,name) VALUES(?,?,?)",
                   (cid, "warehouse", "Warehouse"))
        uid = _pkg(cid, authority={"may_schedule_harm": True},
                   clocks=[{"id": "clock_q", "label": "quake", "due_turns": 1}], ops=[{
            "op": "region_event", "label": "the quake", "clock": "clock_q",
            "footprint": {"rooms": ["warehouse"]},
            "profile": {"mode": "at_once", "intensity": 1.0},
            "effects": {"destroy": True, "harm": {"outcome": "missing", "fraction": 0.0}},
        }])
        _publish(cid, uid)
        fire_due_clocks(cid, 3, turn_id=turn_ids[-1])
        scene = temp_db.wget(cid, "scene")
        assert scene["rooms"]["warehouse"]["ruined"] is True
        assert scene["rooms"]["warehouse"]["hazard"]["state"] == "ruined"
        row = temp_db.q("SELECT retired_turn_id FROM room_registry WHERE chat_id=? "
                        "AND room_uid='warehouse'", (cid,), one=True)
        assert row["retired_turn_id"] == turn_ids[-1]
        hall = _charter(cid)
        # The clerk slept in the warehouse; the berth is gone, so they are
        # rehoused at a standing workplace of their institution.
        assert hall["bodies"]["c1"]["berth"] == "hall"
        assert hall["bodies"]["c1"]["place"] == "hall"

    def test_a_front_advances_by_rings_as_story_hours_pass(self, temp_db):
        cid, turn_ids = _story(temp_db)
        uid = _pkg(cid, ops=[{
            "op": "region_event", "label": "the flood",
            "footprint": {"epicentre": "quay", "radius_hops": 2},
            "profile": {"mode": "front", "intensity": 0.4, "rate_rooms_per_hour": 1.0},
            "effects": {"damage": "flooded", "shock": 0.0, "destroy": False,
                        "displace": False},
        }])
        out = _publish(cid, uid)
        result = out["applied"][0]["result"]
        assert result["waves_done"] == 1 and result["waves_pending"] == 2
        scene = temp_db.wget(cid, "scene")
        assert "hazard" in scene["rooms"]["quay"] and "hazard" not in scene["rooms"]["warehouse"]
        assert fire_due_clocks(cid, 3, elapsed=1800.0)["waves"] == 0
        assert fire_due_clocks(cid, 3, elapsed=3600.0)["waves"] == 1
        scene = temp_db.wget(cid, "scene")
        assert scene["rooms"]["warehouse"]["hazard"]["state"] == "flooded"
        assert "hazard" not in scene["rooms"]["lane"]
        assert fire_due_clocks(cid, 4, elapsed=7200.0)["waves"] == 1
        assert "hazard" in temp_db.wget(cid, "scene")["rooms"]["lane"]
        assert get_package(cid, uid)["operations"][0]["waves"] == []

    def test_harm_is_an_act_the_player_grants(self, temp_db):
        from story.mandates import grant_mandate
        cid, _ = _story(temp_db)
        # The host's own package: the authority flag gates it.
        uid = _pkg(cid, ops=[{
            "op": "region_event", "label": "the quake", "footprint": {"rooms": ["quay"]},
            "profile": {"intensity": 1.0}}])
        assert any("does not permit scheduling harm" in e
                   for e in preview_package(cid, uid)["errors"])
        # A Planner package: the grant, by name, both for the region and the harm.
        uid2 = _pkg(cid, created_by="story_planner", authority={"may_schedule_harm": True},
                    ops=[{"op": "region_event", "label": "the quake",
                          "footprint": {"rooms": ["quay"]}, "profile": {"intensity": 1.0}}])
        assert package_requirements(get_package(cid, uid2)) == ["region_events", "schedule_harm"]
        grant_mandate(cid, None, text="Quakes, yes.", capabilities=["region_events"])
        (refused,) = authority_errors(cid, None, get_package(cid, uid2))
        assert "schedule_harm" in refused
        # And a Planner package with nothing that can hurt asks for nothing
        # of the kind: the default budget for harm is zero and stays zero.
        uid3 = _pkg(cid, created_by="story_planner", ops=[{
            "op": "region_event", "label": "a fog", "footprint": {"rooms": ["quay"]},
            "profile": {"intensity": 0.2}, "effects": {"destroy": False}}])
        assert package_requirements(get_package(cid, uid3)) == ["region_events"]

    def test_the_footprint_is_capped_and_never_inside_a_body(self, temp_db):
        from world.region_events import REGION_FOOTPRINT_CAP, REGION_RADIUS_CAP
        cid, _ = _story(temp_db)
        uid = _pkg(cid, ops=[{"op": "region_event", "label": "x",
                              "footprint": {"rooms": ["inside_mara", "quay"]},
                              "profile": {"intensity": 0.2}, "effects": {"destroy": False}}])
        (change,) = preview_package(cid, uid)["changes"]
        assert change["rooms"] == ["quay"]
        with pytest.raises(ValueError, match="radius_hops"):
            draft_operation(cid, uid, {"op": "region_event", "label": "x",
                                       "footprint": {"epicentre": "quay",
                                                     "radius_hops": REGION_RADIUS_CAP + 1}})
        assert REGION_FOOTPRINT_CAP == 64


# ---------------------------------------------------------------------------
# Containment is the Director's
# ---------------------------------------------------------------------------

class TestContainment:
    def test_a_plan_cannot_exit_to_or_from_the_inside_of_a_body(self, temp_db):
        cid, _ = _story(temp_db)
        uid = _pkg(cid, ops=[
            {"op": "plan_rooms", "structure": {"key": "s", "name": "S"},
             "rooms": {"cellar": {"name": "Cellar", "adjacent": [{"to": "inside_mara"}]}}},
            {"op": "plan_rooms", "structure": {"key": "s", "name": "S"},
             "rooms": {"inside_mara": {"name": "x", "adjacent": [{"to": "quay"}]}}},
            {"op": "arrival", "who": "hall/c1", "room": "inside_mara"},
        ])
        errors = preview_package(cid, uid)["errors"]
        assert sum("inside of a body" in e for e in errors) == 3
        assert any("not a place a plan can hold" in e for e in errors)


# ---------------------------------------------------------------------------
# The author layer holds
# ---------------------------------------------------------------------------

def test_no_new_kind_writes_a_mind(temp_db):
    """Every Phase C kind lands, a clock fires, waves advance -- and no
    character's state, memory, known ledger, relationship or scrubbed view
    changes. A charter body's head takes a claim it was TOLD; that is a
    channel, not a write."""
    from story.scene import recent_events_for_observer
    cid, turn_ids = _story(temp_db)
    char_id = temp_db.qi("INSERT INTO characters(name,sheet,created) VALUES(?,?,?)",
                         ("Mara Quill", json.dumps({"name": "Mara Quill"}), time.time()))
    temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
               (cid, char_id, "active", json.dumps({"mood": "calm"})))
    temp_db.qi("INSERT INTO memories(chat_id,char_id,turn_idx,kind,content) "
               "VALUES(?,?,?,?,?)", (cid, char_id, 1, "episodic", "The tide came in."))

    def snapshot():
        return {
            "chars": [dict(r) for r in temp_db.q(
                "SELECT char_id, status, state, sheet FROM chat_chars WHERE chat_id=?", (cid,))],
            "memories": [dict(r) for r in temp_db.q(
                "SELECT char_id, turn_idx, kind, content FROM memories WHERE chat_id=?", (cid,))],
            "known": temp_db.wget(cid, "known", {}),
            "relationships": [dict(r) for r in temp_db.q(
                "SELECT key, value FROM world WHERE chat_id=? AND key LIKE 'relationships:%'",
                (cid,))],
            "view": recent_events_for_observer(cid, "Mara Quill", n=5, frame_id=None),
        }
    before = snapshot()
    uid = _pkg(cid, authority={"may_schedule_harm": True},
               truths=[{"text": "The reeve set the fire."}],
               clocks=[{"id": "clock_f", "label": "f", "due_turns": 1}], ops=[
        {"op": "arrival", "who": "hall/c1", "room": "quay"},
        {"op": "errand", "charter": "hall", "body": "r1", "to": "quay"},
        {"op": "incident", "room": "warehouse", "summary": "crates fall", "shock": 0.2},
        {"op": "summons", "charter": "hall", "post": "reeve", "target": "Tam Ashwell"},
        {"op": "plant_claim", "charter": "hall", "body": "w1", "text": "the reeve set the fire",
         "told_by": "a drunk"},
        {"op": "adjust_stock", "charter": "hall", "holder": "hall", "good": "grain", "delta": 1},
        {"op": "scheduled_consequence", "clock": "clock_f", "summary": "smoke over the quay"},
        {"op": "region_event", "label": "the fire", "footprint": {"rooms": ["warehouse"]},
         "profile": {"intensity": 0.6}, "effects": {"destroy": False,
                                                    "harm": {"outcome": "hurt", "fraction": 0.5}}},
    ])
    validate_package(cid, uid)
    publish_package(cid, uid, expected_revision=_rev(cid, uid))
    activate_due_packages(cid, 3)
    fire_due_clocks(cid, 3, turn_id=turn_ids[-1])
    assert snapshot() == before
    haystack = json.dumps([dict(r) for r in temp_db.q(
        "SELECT content FROM events WHERE chat_id=?", (cid,))])
    haystack += json.dumps(temp_db.wget(cid, "scene"))
    assert "reeve set the fire" not in haystack.casefold()
