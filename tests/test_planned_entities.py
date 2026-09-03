"""Planned entities and planning needs (`world/planned_entities.py`): the
PLAN tier's ledger for people and things, its view into the Director's
payload, the settle of a render back onto the plan, the reservation the
identity floor honours, and the typed need a surface-only mint files.
"""
from __future__ import annotations

import json
import time

import pytest

from core.pipeline_context import ChatData, PipelineContext, TurnData
from world.planned_entities import (add_planned_entity, body_plan_uid,
                                    plan_uid, planned_entities,
                                    plans_in_view, reserved_plans,
                                    settle_rendered_plans)
from world.planning_needs import (PLANNING_NEEDS_CAP, close_planning_need,
                                  drain_planning_needs, file_planning_need,
                                  fill_planning_need, open_planning_needs,
                                  planning_needs, schedule_planning_needs)

PLAYER = "Wren Ashby"


def _chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Plans", "", time.time()))


def _ctx(db, cid, turn_idx=3, director_resolve=None, scene=None):
    if scene is not None:
        db.wset(cid, "scene", scene)
    turn_id = db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, turn_idx, "", time.time()))
    return PipelineContext(
        chat=ChatData(id=cid, name="Plans", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=cid, idx=turn_idx, player_input="",
                      created=time.time()),
        cast=[], input="", director_resolve=director_resolve or {})


def _scene(player_room="quay"):
    return {"location": "Port", "rooms": {
        "quay": {"name": "Quay", "adjacent": [{"to": "warehouse", "barrier": "open_door"}]},
        "warehouse": {"name": "Warehouse", "adjacent": [{"to": "quay", "barrier": "open_door"}]},
    }, "positions": {PLAYER: player_room}, "entities": {}, "attire": {}}


def _plan(name="Captain Eadric Vale", where="warehouse", kind="person", **extra):
    entry = {"kind": kind, "name": name, "role": "harbourmaster",
             "aliases": ["the harbourmaster"],
             "brief": {"purpose": "Keeps the tally of every hull that berths.",
                       "truths": "Owes the reeve a debt he has not spoken of.",
                       "where": where}}
    entry.update(extra)
    return entry


# ---------------------------------------------------------------------------
# The ledger
# ---------------------------------------------------------------------------

class TestTheLedger:
    def test_a_plan_is_filed_once_and_read_back_whole(self, temp_db):
        cid = _chat(temp_db)
        plan = add_planned_entity(cid, _plan(), turn_idx=2)
        assert plan["uid"] == plan_uid("person", "Captain Eadric Vale")
        stored = planned_entities(cid)
        assert stored[plan["uid"]]["brief"]["where"] == "warehouse"
        assert stored[plan["uid"]]["aliases"] == ["the harbourmaster"]
        assert stored[plan["uid"]]["filed_turn"] == 2
        # Filing the same kind and name again updates in place.
        again = add_planned_entity(cid, _plan(role="dockmaster"))
        assert again["uid"] == plan["uid"]
        assert len(planned_entities(cid)) == 1
        assert planned_entities(cid)[plan["uid"]]["role"] == "dockmaster"

    def test_a_charter_body_and_an_authored_plan_share_one_field(self):
        assert body_plan_uid("ford_inn", "b1") == "charter:ford_inn/b1"
        assert plan_uid("thing", "Sealed Letter").startswith("plan:thing:sealed_letter:")

    def test_the_view_lists_plans_standing_in_the_rooms_and_no_others(self, temp_db):
        cid = _chat(temp_db)
        add_planned_entity(cid, _plan())
        add_planned_entity(cid, _plan(name="Old Sel", where="quay"))
        rows = plans_in_view(cid, {"warehouse"})
        assert [r["name"] for r in rows] == ["Captain Eadric Vale"]
        row = rows[0]
        assert row["plan"] == plan_uid("person", "Captain Eadric Vale")
        assert row["room"] == "warehouse" and row["charter"] == "" and row["body"] == ""
        assert row["brief"]["purpose"].startswith("Keeps the tally")
        assert row["aliases"] == ["the harbourmaster"]
        assert plans_in_view(cid, set()) == []

    def test_a_rendered_plan_leaves_the_view_and_the_reservation(self, temp_db):
        cid = _chat(temp_db)
        plan = add_planned_entity(cid, _plan())
        assert reserved_plans(cid)[0]["reserved"] is True
        settle_rendered_plans(cid, [{"plan": plan["uid"], "entity_id": "vale",
                                     "render": "A grey man with a ledger.",
                                     "turn": 4}])
        assert plans_in_view(cid, {"warehouse"}) == []
        assert reserved_plans(cid) == []
        assert planned_entities(cid)[plan["uid"]]["rendered"]["render"] == "A grey man with a ledger."

    def test_the_reservation_excludes_the_rooms_the_view_already_covers(self, temp_db):
        cid = _chat(temp_db)
        add_planned_entity(cid, _plan())
        add_planned_entity(cid, _plan(name="Old Sel", where="quay"))
        names = {r["name"] for r in reserved_plans(cid, exclude_rooms={"warehouse"})}
        assert names == {"Old Sel"}


class TestARenderSettlesOnce:
    def test_a_second_render_is_neither_settled_nor_refused(self, temp_db):
        cid = _chat(temp_db)
        plan = add_planned_entity(cid, _plan())
        first = settle_rendered_plans(cid, [{"plan": plan["uid"], "render": "Grey."}])
        assert first == [{"plan": plan["uid"], "settled": "Grey."}]
        second = settle_rendered_plans(cid, [{"plan": plan["uid"], "render": "Red."}])
        assert second == []
        assert planned_entities(cid)[plan["uid"]]["rendered"]["render"] == "Grey."

    def test_a_render_contradicting_a_dealt_axis_is_refused(self, temp_db):
        from world.charter_surface import AXES, default_looks
        cid = _chat(temp_db)
        looks = default_looks()
        axis = AXES[0]
        dealt, other = looks[axis][0], looks[axis][1]
        plan = add_planned_entity(cid, _plan(surface={axis: dealt}))
        out = settle_rendered_plans(cid, [{"plan": plan["uid"],
                                           "render": "A %s figure." % other}])
        assert out == [{"plan": plan["uid"], "refused": axis}]
        assert "rendered" not in planned_entities(cid)[plan["uid"]]

    def test_only_authored_plans_settle_here(self, temp_db):
        cid = _chat(temp_db)
        assert settle_rendered_plans(cid, [{"plan": "charter:inn/b1", "render": "x"}]) == []


# ---------------------------------------------------------------------------
# The floor: a planned identity is reserved
# ---------------------------------------------------------------------------

class TestAPlannedIdentityIsReserved:
    def _floor(self):
        from agents.director import _bind_minted_entities_to_present_figures
        return _bind_minted_entities_to_present_figures

    def _rows(self, temp_db):
        cid = _chat(temp_db)
        add_planned_entity(cid, _plan())                       # warehouse
        add_planned_entity(cid, _plan(name="Sealed Letter", kind="thing",
                                      where="quay", role="",
                                      aliases=["the letter"]))
        return cid

    def test_a_mint_naming_a_plan_anywhere_is_a_render_of_it(self, temp_db):
        cid = self._rows(temp_db)
        figures = plans_in_view(cid, {"quay"}) + reserved_plans(cid, exclude_rooms={"quay"})
        sd = {"entities": {"vale": {"name": "Eadric Vale", "kind": "person",
                                    "description": "A grey man."}},
              "positions": {"vale": "quay"}}
        bound = self._floor()({}, sd, figures, fallback_room="quay")
        assert len(bound) == 1 and bound[0]["by"] == "name"
        assert bound[0]["plan"] == plan_uid("person", "Captain Eadric Vale")
        ent = sd["entities"]["vale"]
        assert ent["name"] == "Captain Eadric Vale"
        assert ent["plan_ref"] == {"uid": bound[0]["plan"]}
        assert "charter_ref" not in ent
        assert "Eadric Vale" in ent["aliases"]

    def test_an_alias_reserves_the_plan_too(self, temp_db):
        cid = self._rows(temp_db)
        figures = reserved_plans(cid)
        sd = {"entities": {"hm": {"name": "The Harbourmaster", "kind": "person"}},
              "positions": {}}
        bound = self._floor()({}, sd, figures, fallback_room="quay")
        assert bound and bound[0]["bound_to"] == "Captain Eadric Vale"

    def test_a_role_reaches_only_the_plans_own_room(self, temp_db):
        cid = self._rows(temp_db)
        figures = reserved_plans(cid)  # the harbourmaster stands in the warehouse
        sd = {"entities": {"hm": {"name": "a dockmaster", "kind": "person"}},
              "positions": {"hm": "quay"}}
        # No name match, and the plan is not in this room: nothing binds.
        assert self._floor()({}, sd, figures, fallback_room="quay") == []
        # In its own room, offered as a figure there, the role binds.
        in_view = plans_in_view(cid, {"warehouse"})
        sd = {"entities": {"hm": {"name": "the harbourmaster's clerk", "kind": "person"}},
              "positions": {"hm": "warehouse"}}
        assert self._floor()({}, sd, in_view, fallback_room="warehouse") == []
        sd = {"entities": {"hm": {"name": "the port's harbourmaster", "kind": "person"}},
              "positions": {"hm": "warehouse"}}
        bound = self._floor()({}, sd, in_view, fallback_room="warehouse")
        assert bound and bound[0]["by"] == "role"

    def test_a_minted_thing_binds_to_a_planned_thing_by_name_only(self, temp_db):
        cid = self._rows(temp_db)
        figures = plans_in_view(cid, {"quay"})
        sd = {"entities": {"letter": {"name": "the letter", "kind": "object",
                                      "portable": True}},
              "positions": {"letter": "quay"}}
        bound = self._floor()({}, sd, figures, fallback_room="quay")
        assert bound and bound[0]["bound_to"] == "Sealed Letter"
        assert sd["entities"]["letter"]["plan_ref"]["uid"] == plan_uid("thing", "Sealed Letter")
        # A thing never binds by role, and a person never binds to a thing.
        sd = {"entities": {"crate": {"name": "a crate", "kind": "object", "portable": True}},
              "positions": {"crate": "quay"}}
        assert self._floor()({}, sd, figures, fallback_room="quay") == []
        sd = {"entities": {"p": {"name": "Sealed Letter", "kind": "person"}},
              "positions": {"p": "quay"}}
        assert self._floor()({}, sd, figures, fallback_room="quay") == []

    def test_a_charter_body_binding_is_unchanged(self, temp_db):
        figures = [{"name": "Tam Ashwell", "role": "innkeeper",
                    "posts": ["innkeeper"], "room": "quay",
                    "charter": "ford_inn", "body": "i1",
                    "plan": body_plan_uid("ford_inn", "i1")}]
        sd = {"entities": {"inn": {"name": "the innkeeper", "kind": "person"}},
              "positions": {"inn": "quay"}}
        bound = self._floor()({}, sd, figures, fallback_room="quay")
        assert bound[0]["by"] == "role"
        ent = sd["entities"]["inn"]
        assert ent["charter_ref"] == {"charter": "ford_inn", "body": "i1"}
        assert ent["plan_ref"] == {"uid": "charter:ford_inn/i1"}


# ---------------------------------------------------------------------------
# Payloads carry the plans in view
# ---------------------------------------------------------------------------

class TestThePayloadCarriesPlans:
    def test_figures_in_view_join_bodies_and_plans(self, temp_db):
        from agents.director import _figures_in_view, _present_figure_rows
        cid = _chat(temp_db)
        add_planned_entity(cid, _plan())
        add_planned_entity(cid, _plan(name="Old Sel", where="quay"))
        ctx = _ctx(temp_db, cid, scene=_scene())
        figures = _figures_in_view(ctx, {"warehouse"}, reserved=True)
        names = [(f["name"], bool(f.get("reserved"))) for f in figures]
        assert ("Captain Eadric Vale", False) in names
        assert ("Old Sel", True) in names
        rows = _present_figure_rows(figures)
        assert [r["name"] for r in rows] == ["Captain Eadric Vale"]
        assert rows[0]["plan"] == plan_uid("person", "Captain Eadric Vale")
        assert rows[0]["brief"]["truths"].startswith("Owes")
        assert "kind" not in rows[0]

    def test_a_planned_thing_shows_its_kind(self, temp_db):
        from agents.director import _present_figure_rows
        cid = _chat(temp_db)
        add_planned_entity(cid, _plan(name="Sealed Letter", kind="thing",
                                      where="quay", role=""))
        rows = _present_figure_rows(plans_in_view(cid, {"quay"}))
        assert rows[0]["kind"] == "thing"

    def test_a_story_with_no_plans_lists_nobody(self, temp_db):
        from agents.director import _figures_in_view
        cid = _chat(temp_db)
        ctx = _ctx(temp_db, cid, scene=_scene())
        assert _figures_in_view(ctx, {"quay"}, reserved=True) == []
        assert _figures_in_view(ctx, set()) == []


# ---------------------------------------------------------------------------
# Planning needs
# ---------------------------------------------------------------------------

class TestPlanningNeeds:
    def test_a_need_is_filed_once_per_identity(self, temp_db):
        cid = _chat(temp_db)
        first, fresh = file_planning_need(
            cid, {"kind": "person", "surface": {"name": "Dock Hand", "room": "quay",
                                                "description": "A wiry hand."}},
            turn_idx=3)
        assert fresh and first["status"] == "open" and first["filed_turn"] == 3
        again, fresh = file_planning_need(
            cid, {"kind": "person", "surface": {"name": "dock hand", "room": "hold"}})
        assert not fresh and again["uid"] == first["uid"]
        assert len(planning_needs(cid)) == 1

    def test_a_filled_need_records_what_filled_it(self, temp_db):
        cid = _chat(temp_db)
        need, _ = file_planning_need(cid, {"kind": "person", "surface": {"name": "Dock Hand"}})
        filled = fill_planning_need(cid, need["uid"], {"ref": {"charter": "households", "body": "x"}}, turn_idx=4)
        assert filled["status"] == "filled" and filled["filled_turn"] == 4
        assert open_planning_needs(cid) == []
        # Filing the same identity again returns the filled record.
        again, fresh = file_planning_need(cid, {"kind": "person", "surface": {"name": "Dock Hand"}})
        assert not fresh and again["status"] == "filled"

    def test_a_room_need_and_a_thing_need_stay_open_for_the_room(self, temp_db):
        cid = _chat(temp_db)
        file_planning_need(cid, {"kind": "room", "surface": {"room": "house_c", "name": "a dwelling"}})
        file_planning_need(cid, {"kind": "thing", "surface": {"name": "the sealed letter"}})
        out = drain_planning_needs(cid)
        assert out == {"filled": [], "open": 2}
        kinds = {n["kind"] for n in open_planning_needs(cid)}
        assert kinds == {"room", "thing"}

    def test_the_drain_fills_a_person_need_the_town_can_place(self, temp_db):
        from world.charter_runtime import registry_for
        cid = _chat(temp_db)
        need, _ = file_planning_need(cid, {"kind": "person", "surface": {"name": "Dock Hand", "room": "quay"}})
        out = drain_planning_needs(cid)
        assert out["filled"][0]["uid"] == need["uid"]
        assert out["filled"][0]["how"] == "minted_households"
        assert "households" in registry_for(cid)["items"]
        assert open_planning_needs(cid) == []

    def test_past_the_cap_the_oldest_open_need_is_closed_as_stale(self, temp_db):
        cid = _chat(temp_db)
        for n in range(PLANNING_NEEDS_CAP + 1):
            file_planning_need(cid, {"kind": "thing", "surface": {"name": "thing %d" % n}})
        needs = planning_needs(cid)
        assert len(open_planning_needs(cid)) == PLANNING_NEEDS_CAP
        stale = [n for n in needs if n["status"] == "closed"]
        assert len(stale) == 1 and stale[0]["surface"]["name"] == "thing 0"
        assert "stale" in stale[0]["closed_reason"]

    def test_a_closed_need_may_be_filed_again(self, temp_db):
        cid = _chat(temp_db)
        need, _ = file_planning_need(cid, {"kind": "thing", "surface": {"name": "the letter"}})
        close_planning_need(cid, need["uid"], "the story moved on")
        again, fresh = file_planning_need(cid, {"kind": "thing", "surface": {"name": "the letter"}})
        assert fresh and again["uid"] == need["uid"]

    def test_the_job_runs_only_when_something_is_open(self, temp_db):
        from core import jobs
        cid = _chat(temp_db)
        ctx = _ctx(temp_db, cid)
        assert schedule_planning_needs(ctx) is None
        file_planning_need(cid, {"kind": "person", "surface": {"name": "Dock Hand", "room": "quay"}})
        job = schedule_planning_needs(ctx)
        assert job is not None
        deadline = time.time() + 10.0
        while job.state in ("pending", "running") and time.time() < deadline:
            time.sleep(0.02)
        assert job.state == "done", (job.state, job.error)
        assert job.result["filled"]
        assert open_planning_needs(cid) == []
        jobs.drain(timeout=1.0)


# ---------------------------------------------------------------------------
# The commit: a surface-only mint files a need and the town answers it
# ---------------------------------------------------------------------------

def _resolve_with_person(name, room, description, kind="person"):
    return {
        "resolved_event": "%s looks up from the rope." % name,
        "dialogue_log": [{"speaker": name, "exact_quote": "Aye?"}],
        "state_diff": {
            "entities": {"dock_hand": {"name": name, "kind": kind,
                                       "description": description}},
            "positions": {name: room},
        },
    }


class TestTheCommitFilesTheNeedAndTheTownAnswers:
    def test_a_person_with_no_plan_is_enrolled_and_the_director_told(self, temp_db):
        from persist.commit import track_background_presences
        from world.charter_runtime import registry_for
        cid = _chat(temp_db)
        ctx = _ctx(temp_db, cid, director_resolve=_resolve_with_person(
            "Dock Hand", "quay", "A wiry hand with rope burns."), scene=_scene())
        track_background_presences(ctx, nonce=0)
        needs = planning_needs(cid)
        person = [n for n in needs if n["kind"] == "person"]
        assert len(person) == 1 and person[0]["status"] == "filled"
        assert person[0]["surface"]["description"] == "A wiry hand with rope burns."
        assert person[0]["surface"]["room"] == "quay"
        # A households charter minted for a story with no town owes the
        # newcomer a dwelling: a room-need, open for the room.
        assert [n["kind"] for n in open_planning_needs(cid)] == ["room"]
        ref = person[0]["fill"]["ref"]
        presences = temp_db.wget(cid, "background_presences", {})
        record = next(r for r in presences.values() if r.get("name") == "Dock Hand"
                      or "Dock Hand" in json.dumps(r))
        assert ref in record["charter_refs"]
        body = registry_for(cid)["items"][ref["charter"]]["state"]["bodies"][ref["body"]]
        assert body["surface"]["rendered"] == "A wiry hand with rope burns."
        assert "ambient" not in registry_for(cid)["items"]
        assert any("no plan behind them" in m for m in ctx.engine_feedback)

    def test_a_device_files_nothing(self, temp_db):
        from persist.commit import track_background_presences
        cid = _chat(temp_db)
        scene = _scene()
        scene["entities"]["fixture"] = {"name": "Suppression Fixture",
                                        "kind": "device",
                                        "description": "A ceiling-mounted fixture."}
        ctx = _ctx(temp_db, cid, director_resolve=_resolve_with_person(
            "Suppression Fixture", "quay", "A ceiling-mounted fixture.",
            kind="device"), scene=scene)
        track_background_presences(ctx, nonce=0)
        assert planning_needs(cid) == []

    def test_a_render_of_a_bound_plan_settles_at_commit(self, temp_db):
        from persist.commit import track_background_presences
        cid = _chat(temp_db)
        plan = add_planned_entity(cid, _plan(where="quay"))
        dr = _resolve_with_person("Captain Eadric Vale", "quay",
                                  "A grey man with a ledger under one arm.")
        dr["state_diff"]["entities"]["dock_hand"]["plan_ref"] = {"uid": plan["uid"]}
        ctx = _ctx(temp_db, cid, director_resolve=dr, scene=_scene())
        track_background_presences(ctx, nonce=0)
        stored = planned_entities(cid)[plan["uid"]]
        assert stored["rendered"]["render"].startswith("A grey man")
        assert stored["rendered"]["entity_id"] == "dock_hand"
        # A plan the beat rendered is not ALSO a planning need.
        assert planning_needs(cid) == []


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def test_both_ledgers_survive_archive_and_checkpoint(temp_db):
    from persist.checkpoints import ensure_checkpoint, restore_checkpoint
    from web import app
    cid = _chat(temp_db)
    temp_db.wset(cid, "scene", _scene())
    temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
               (cid, 0, "", time.time()))
    plan = add_planned_entity(cid, _plan())
    file_planning_need(cid, {"kind": "thing", "surface": {"name": "the letter"}})
    ensure_checkpoint(cid, 1)
    settle_rendered_plans(cid, [{"plan": plan["uid"], "render": "Grey."}])
    exported = app.chat_export(cid)
    assert "planned_entities" in exported["world"] and "planning_needs" in exported["world"]
    imported = app.chat_import({"data": exported})
    assert planned_entities(imported["id"])[plan["uid"]]["rendered"]["render"] == "Grey."
    assert open_planning_needs(imported["id"])[0]["surface"]["name"] == "the letter"
    restore_checkpoint(cid, 1)
    assert "rendered" not in planned_entities(cid)[plan["uid"]]
