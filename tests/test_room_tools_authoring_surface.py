"""What the Writers' Room can SAY, and what its own diagnostics report.

Four findings from the 2026-09-05 campaign, all of the same shape: a fact the
engine holds a field for that the Room had no way to write, or a diagnostic
that answered nothing about the world it was looking at.

* PR12 (rush run): asked to make the ovens audible two floors down, the Room
  answered that the simulation had no acoustic engine, then corrected itself
  exactly right -- the gap was in the authoring schema. `plan_entity` had no
  `sound_source`, so the roar went into the entity's `truths` prose, where no
  field reads it.
* PX23 (masque run): the Room authored a whole compact of secrets, correctly
  and helpfully, and nothing in it said which facts the player's own character
  may act on. There was no `known_by` on a truth.
* PX24 (masque run): "build me what lies beyond the servants' passage" minted
  a grant of five capabilities with `limits: {}` and `expires_turn: null`.
  `mandates` has stated since 2026-09-04 that a grant may name the ask it
  answers and lapse with it -- and nothing passed one.
* PX19 (masque run): `region_patch(cid, "the working wing", {...})` answered
  `{"id": "the_working_wing", "name": "the_working_wing"}`. The human phrase
  became the id and then the id became the name.
* PM10/PM11/PS6 (multitude and solitude runs): `request_location` reported
  success with `rooms: []`, and `inspect_contradictions` found nothing while
  eleven duplicate rooms stood in the registry.
"""

from __future__ import annotations

import time

import pytest

from story.plot_packages import (draft_operation, get_package, new_package,
                                 preview_package, validate_package)
from story.room_tools import run_tool

PLAYER = "Wren Ashby"


def _story(db, *, turns=3):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Surface", "A residence at night.", time.time()))
    db.wset(cid, "scene", {"location": "Residence", "rooms": {
        "reception": {"name": "Reception Room", "desc": "Lamps and glass.",
                      "adjacent": [{"to": "gallery", "barrier": "open_door"},
                                   {"to": "study", "barrier": "closed_door"}]},
        "gallery": {"name": "Gallery", "desc": "Portraits.",
                    "adjacent": [{"to": "reception", "barrier": "open_door"}]},
        "study": {"name": "Study", "desc": "A lacquer cabinet.",
                  "adjacent": [{"to": "reception", "barrier": "closed_door"}]},
    }, "positions": {PLAYER: "reception"}, "entities": {}, "attire": {}})
    # A registered cast member, so `_world_snapshot`'s `occupied` has somebody
    # in it: "a room a cast member occupies" is what the reach and arrival
    # warnings are about.
    char = db.qi("INSERT INTO characters(name,sheet,created) VALUES(?,?,?)",
                 (PLAYER, "{}", time.time()))
    db.qi("INSERT INTO chat_chars(chat_id,char_id) VALUES(?,?)", (cid, char))
    for i in range(turns):
        db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
              "VALUES(?,?,?,?)", (cid, i, "", time.time()))
    return cid


# ---------------------------------------------------------------------------
# PR12 -- a planned thing can say what it emits
# ---------------------------------------------------------------------------

class TestAPlannedThingCanBeASource:
    def test_a_planned_oven_carries_its_roar(self, temp_db):
        cid = _story(temp_db)
        uid = new_package(cid, title="The Bakery Below")["uid"]
        draft_operation(cid, uid, {
            "op": "plan_entity", "kind": "thing", "name": "the great oven",
            "brief": {"purpose": "bread for the district", "where": "study"},
            "sound_source": "catastrophic", "light_source": "lit",
            "light_shape": "cone", "light_height": "waist",
            "steadiness": "flickering"})
        op = get_package(cid, uid)["operations"][0]
        assert op["sources"] == {"sound_source": "catastrophic",
                                 "light_source": "lit",
                                 "light_shape": "cone",
                                 "light_height": "waist",
                                 "steadiness": "flickering"}
        change = preview_package(cid, uid)["changes"][0]
        assert change["sources"]["sound_source"] == "catastrophic"

    def test_a_value_the_world_cannot_read_is_absent_not_fatal(self, temp_db):
        """Fail-open, as a plan's geometry is: the preview is where a host
        sees that a measurement did not survive."""
        cid = _story(temp_db)
        uid = new_package(cid, title="The Bakery Below")["uid"]
        draft_operation(cid, uid, {
            "op": "plan_entity", "kind": "thing", "name": "the great oven",
            "brief": {"where": "study"}, "sound_source": "very very loud"})
        assert get_package(cid, uid)["operations"][0]["sources"] == {}

    def test_the_field_reaches_the_filed_plan_and_the_directors_figure(
            self, temp_db):
        from story.plot_packages import _apply_plan_entity
        from world.planned_entities import plan_figure, planned_entities

        cid = _story(temp_db)
        uid = new_package(cid, title="The Bakery Below")["uid"]
        draft_operation(cid, uid, {
            "op": "plan_entity", "kind": "thing", "name": "the great oven",
            "brief": {"where": "study"}, "sound_source": "catastrophic"})
        op = get_package(cid, uid)["operations"][0]
        _apply_plan_entity(cid, None, op, 1)
        plan = next(iter(planned_entities(cid).values()))
        assert plan["sources"] == {"sound_source": "catastrophic"}
        assert plan_figure(plan)["sources"]["sound_source"] == "catastrophic"

    def test_the_schema_the_model_reads_names_the_fields(self):
        """"Did not know the field existed" was half the finding: the Room
        drafts against `OPERATION_FIELDS`, so a field absent there is a field
        that does not exist."""
        from story.plot_packages import OPERATION_FIELDS

        fields = OPERATION_FIELDS["plan_entity"]
        for name in ("light_source?", "light_shape?", "light_height?",
                     "steadiness?", "sound_source?"):
            assert name in fields
        assert "catastrophic" in fields["sound_source?"]


# ---------------------------------------------------------------------------
# PX23 -- whose knowledge a truth is
# ---------------------------------------------------------------------------

class TestATruthCanNameItsAudience:
    def test_an_audience_of_nobody_is_the_default(self, temp_db):
        """A truth with no `known_by` is author knowledge: true of the world
        and inside nobody. That is what every truth was, silently."""
        cid = _story(temp_db)
        from story.plot_packages import edit_package

        uid = new_package(cid, title="Halvane's Compact")["uid"]
        edit_package(cid, uid, {"truths": [
            {"text": "The customs reserves were diverted through false writs."}]})
        assert validate_package(cid, uid)["ok"]
        assert "known_by" not in get_package(cid, uid)["truths"][0]

    def test_the_player_is_a_member_of_the_vocabulary(self, temp_db):
        from story.plot_packages import TRUTH_AUDIENCE_PLAYER, edit_package

        cid = _story(temp_db)
        uid = new_package(cid, title="Halvane's Compact")["uid"]
        edit_package(cid, uid, {"truths": [
            {"text": "Ivo entered disguised as a wine factor.",
             "known_by": [TRUTH_AUDIENCE_PLAYER]}]})
        assert validate_package(cid, uid)["ok"]

    def test_a_name_the_world_holds_nobody_of_is_refused(self, temp_db):
        from story.plot_packages import edit_package

        cid = _story(temp_db)
        uid = new_package(cid, title="Halvane's Compact")["uid"]
        edit_package(cid, uid, {"truths": [
            {"text": "The bond sits in the cabinet.",
             "known_by": ["Nobody At All"]}]})
        report = validate_package(cid, uid)
        assert not report["ok"]
        assert any("known_by" in e for e in report["errors"])

    def test_an_authored_plan_is_somebody_the_world_holds(self, temp_db):
        from story.plot_packages import edit_package
        from world.planned_entities import add_planned_entity

        cid = _story(temp_db)
        add_planned_entity(cid, {"kind": "person", "name": "Ivo Sarn"})
        uid = new_package(cid, title="Halvane's Compact")["uid"]
        edit_package(cid, uid, {"truths": [
            {"text": "The bond sits in the cabinet.",
             "known_by": ["Ivo Sarn"]}]})
        assert validate_package(cid, uid)["ok"]

    def test_the_room_is_told_the_field_exists(self):
        from story.room_tools import TOOL_INDEX

        assert "known_by" in TOOL_INDEX["edit_package"]["description"]


# ---------------------------------------------------------------------------
# PX24 -- a grant lapses with the ask that earned it
# ---------------------------------------------------------------------------

class TestAGrantNamesTheAskThatEarnedIt:
    def test_the_planner_passes_the_request_through(self, temp_db):
        from agents.story_planner import _apply_grants
        from story.mandates import active_mandates

        cid = _story(temp_db)
        uid = new_package(cid, title="Beyond the Servants' Passage")["uid"]
        rows, notes = _apply_grants(cid, None, [{
            "text": "Build me what lies beyond the servants' passage.",
            "capabilities": ["plan_rooms"],
            "request": {"uid": uid, "text": "the rooms beyond the passage"},
        }], 3)
        assert not notes and rows
        assert rows[0]["request"]["uid"] == uid
        assert rows[0]["request"]["kind"] == "package"
        assert len(active_mandates(cid, None)) == 1

    def test_it_ends_when_the_package_it_answers_does(self, temp_db):
        from agents.story_planner import _apply_grants
        from story.mandates import active_mandates, expire_mandates
        from story.plot_packages import retire_package

        cid = _story(temp_db)
        uid = new_package(cid, title="Beyond the Servants' Passage")["uid"]
        _apply_grants(cid, None, [{
            "text": "Build me what lies beyond the servants' passage.",
            "capabilities": ["plan_rooms"],
            "request": {"uid": uid},
        }], 3)
        retire_package(cid, uid, note="withdrawn")
        expire_mandates(cid, None, 4)
        assert active_mandates(cid, None) == []

    def test_a_grant_with_no_request_still_stands(self, temp_db):
        """A grant the player made standing is standing; the request is what
        the Room may now SAY, not a new default."""
        from agents.story_planner import _apply_grants
        from story.mandates import active_mandates

        cid = _story(temp_db)
        _apply_grants(cid, None, [{
            "text": "You may plan rooms for this story whenever you like.",
            "capabilities": ["plan_rooms"]}], 3)
        assert len(active_mandates(cid, None)) == 1

    def test_the_room_is_told_it_can_say_it(self):
        from llm.prompts import get_prompt

        assert '"request"' in get_prompt("story_planner")


# ---------------------------------------------------------------------------
# PX19 -- a region keeps the phrase it was entered under
# ---------------------------------------------------------------------------

class TestARegionKeepsItsName:
    def test_a_human_phrase_does_not_become_the_display_name(self, temp_db):
        from web.world_routes import region_patch

        cid = _story(temp_db)
        row = region_patch(cid, "the working wing",
                           {"look": "Scrubbed deal and lamp-black."})
        assert row["id"] == "the_working_wing"
        assert row["name"] == "the working wing"

    def test_a_standing_name_is_never_overwritten(self, temp_db):
        from web.world_routes import region_patch

        cid = _story(temp_db)
        region_patch(cid, "the working wing", {"name": "The Working Wing"})
        row = region_patch(cid, "the_working_wing", {"look": "Lamp-black."})
        assert row["name"] == "The Working Wing"


# ---------------------------------------------------------------------------
# PM10 / PM11 / PS6 -- the diagnostics answer about the world in front of them
# ---------------------------------------------------------------------------

class TestTheGenerationReportSaysWhatLanded:
    def test_it_reads_the_shape_generate_lived_location_returns(
            self, temp_db, monkeypatch):
        """`generate_lived_location` returns the town's NAME under `town`, the
        room COUNT under `rooms` and the charter keys as a list. This read
        `result["town"]` as a dict, so every field fell back to empty and a
        generation that planted eleven rooms and fourteen bodies reported
        `{"rooms": [], "charters": []}` with no warning."""
        from story.plot_packages import _prepare_request_location
        from world import charter_runtime

        monkeypatch.setattr(charter_runtime, "generate_lived_location",
                            lambda cid, request, frame_id=None: {
                                "ok": True, "town": "Vaunt's Yard Waterfront",
                                "structure": {"key": "vaunts_yard_waterfront"},
                                "rooms": 11, "bound_rooms": ["yard"],
                                "charters": ["waterfront"],
                                "warnings": ["waterfront: no body of this "
                                             "institution stands in a room the "
                                             "story holds"]})
        out = _prepare_request_location(_story(temp_db), None,
                                        {"request": {"brief": "a yard"}})
        assert out["summary"] == "Vaunt's Yard Waterfront"
        assert out["rooms"] == 11
        assert out["bound_rooms"] == ["yard"]
        assert out["charters"] == ["waterfront"]
        assert out["warnings"] and "no body" in out["warnings"][0]


class TestTheContradictionToolFindsThem:
    def test_two_rooms_that_answer_to_one_spelling(self, temp_db):
        """PM11: with eleven `vaunts_yard_waterfront_2_*` rooms standing
        beside their originals, the tool answered `structure: []`,
        `dangling: []`, `layout: []`."""
        from world.structure import plant_structure

        cid = _story(temp_db)
        plant_structure(cid, {"key": "yardside", "name": "Yardside"},
                        {"yard": {"name": "Yard"}})
        plant_structure(cid, {"key": "yardside_2", "name": "Yardside 2"},
                        {"yardside_2_yard": {"name": "Yard"}})
        rows = run_tool(cid, "inspect_contradictions")["dangling"]
        alike = [r for r in rows if r["kind"] == "rooms_named_alike"]
        assert alike and alike[0]["rooms"] == ["yard", "yardside_2_yard"]

    def test_a_structure_no_live_room_can_be_walked_to(self, temp_db):
        from world.structure import plant_structure

        cid = _story(temp_db)
        plant_structure(cid, {"key": "waterfront", "name": "Waterfront"},
                        {"rope_walk": {"name": "Rope Walk",
                                       "adjacent": [{"to": "wharf_apron"}]},
                         "wharf_apron": {"name": "Wharf Apron",
                                         "adjacent": [{"to": "rope_walk"}]}})
        rows = run_tool(cid, "inspect_contradictions")["dangling"]
        out = [r for r in rows if r["kind"] == "structure_out_of_reach"]
        assert out and out[0]["structure"] == "waterfront"

    def test_a_structure_hanging_off_a_live_room_is_in_reach(self, temp_db):
        from world.structure import plant_structure

        cid = _story(temp_db)
        plant_structure(cid, {"key": "waterfront", "name": "Waterfront"},
                        {"rope_walk": {"name": "Rope Walk",
                                       "adjacent": [{"to": "gallery"}]}})
        rows = run_tool(cid, "inspect_contradictions")["dangling"]
        assert not [r for r in rows if r["kind"] == "structure_out_of_reach"]

    def test_a_paired_layout_contradiction_is_reported_once(self):
        """PS6: the lint walks a pair from each end, so the one overlap it saw
        was reported twice, once per ordering."""
        from story.room_tools import _one_row_per_contradiction

        rows = _one_row_per_contradiction([
            {"kind": "rooms_overlap_when_placed",
             "rooms": ["upper_terrace_settlement", "upper_terrace_rim"],
             "via": "middle_terrace_pans"},
            {"kind": "rooms_overlap_when_placed",
             "rooms": ["upper_terrace_rim", "upper_terrace_settlement"],
             "via": "middle_terrace_pans"},
            {"kind": "wall_overfull", "room": "a"},
        ])
        assert [r["kind"] for r in rows] == ["rooms_overlap_when_placed",
                                             "wall_overfull"]


class TestAnArrivalNobodyIsThereToMeet:
    """PQ13, quiet run 2026-09-05. The caller from Clough's Steading arrived
    on the far side of a closed front door in a room neither character
    entered. The knock stood in the engine's event record for three turns,
    reached no narrator prose, and was marked stale. Nothing here is wrong --
    a planned arrival in an empty room may be exactly the point -- so the
    preview says it at the moment a host can still put somebody there."""

    def test_an_arrival_at_an_empty_room_warns(self, temp_db):
        from world.planned_entities import add_planned_entity

        cid = _story(temp_db)
        add_planned_entity(cid, {"kind": "person", "name": "Jem Clough"})
        uid = new_package(cid, title="A Caller")["uid"]
        draft_operation(cid, uid, {"op": "arrival", "who": "Jem Clough",
                                   "room": "study"})
        report = preview_package(cid, uid)
        assert any("no body occupies" in w for w in report["warnings"])

    def test_an_arrival_where_the_cast_stands_does_not(self, temp_db):
        from world.planned_entities import add_planned_entity

        cid = _story(temp_db)
        add_planned_entity(cid, {"kind": "person", "name": "Jem Clough"})
        uid = new_package(cid, title="A Caller")["uid"]
        draft_operation(cid, uid, {"op": "arrival", "who": "Jem Clough",
                                   "room": "reception"})
        report = preview_package(cid, uid)
        assert not any("no body occupies" in w for w in report["warnings"])


class TestTheReachWarningWalksDoors:
    """PX15's other half: the Room warned on its own good package -- "no route
    joins ... to any room a cast member occupies" -- about rooms that were one
    closed door away, because the walk was over `passable_neighbors`."""

    def test_a_room_behind_a_closed_door_is_reachable(self, temp_db):
        cid = _story(temp_db)
        uid = new_package(cid, title="The Steward's Office")["uid"]
        draft_operation(cid, uid, {
            "op": "plan_rooms",
            "structure": {"key": "working_wing", "name": "The Working Wing"},
            "rooms": {"stewards_office": {
                "name": "Steward's Office", "purpose": "accounts",
                "adjacent": [{"to": "study"}]}}})
        report = preview_package(cid, uid)
        assert not any("cannot reach this" in w for w in report["warnings"]), \
            report["warnings"]
