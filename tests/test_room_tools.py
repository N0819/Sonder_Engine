"""The authoring facade (`story/room_tools.py`): one table an agent can be
handed as tools, every read over an engine reader, every write through a
plot package, no SQL and no module names anywhere in the arguments.
"""
from __future__ import annotations

import json
import time

import pytest

from story.room_tools import (
    SEARCH_K_CAP, TOOL_INDEX, TOOL_RESULT_CHARS, TOOLS, ToolError, run_tool,
    tool_manifest)

PLAYER = "Wren Ashby"


def _story(db):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Facade", "A port at dusk.", time.time()))
    bid = db.qi("INSERT INTO lorebooks(name,chat_id) VALUES(?,?)", ("Canon", cid))
    db.qi("INSERT INTO chat_lorebooks(chat_id,lorebook_id) VALUES(?,?)", (cid, bid))
    db.qi("UPDATE chats SET lorebook_id=? WHERE id=?", (bid, cid))
    db.wset(cid, "scene", {"location": "Port", "rooms": {
        "quay": {"name": "Quay", "desc": "Wet stone.",
                 "adjacent": [{"to": "warehouse", "barrier": "open_door"}]},
        "warehouse": {"name": "Warehouse", "desc": "Crates.",
                      "adjacent": [{"to": "quay", "barrier": "open_door"},
                                   {"to": "loft", "barrier": "locked_door"}]},
        "loft": {"name": "Loft", "desc": "Dust.",
                 "adjacent": [{"to": "warehouse", "barrier": "locked_door"}]},
    }, "positions": {PLAYER: "quay"}, "entities": {}, "attire": {}})
    for i in range(3):
        db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
              (cid, i, "", time.time()))
    return cid, bid


# ---------------------------------------------------------------------------
# The table
# ---------------------------------------------------------------------------

class TestTheTable:
    def test_every_tool_is_a_name_a_paragraph_a_schema_and_a_handler(self):
        names = [t["name"] for t in TOOLS]
        assert len(names) == len(set(names))
        for tool in TOOLS:
            assert tool["description"].strip() and len(tool["description"]) > 40
            assert tool["args"]["type"] == "object"
            assert tool["args"]["additionalProperties"] is False
            assert callable(tool["handler"])
            # No argument anywhere takes SQL, a path or a module.
            for arg in tool["args"]["properties"]:
                assert not any(w in arg for w in ("sql", "query_sql", "path",
                                                   "module", "table"))

    def test_the_manifest_hides_host_only_tools_by_default(self):
        names = {t["name"] for t in tool_manifest()}
        assert "retire_package" not in names
        assert "read_package" in names
        full = {t["name"]: t for t in tool_manifest(include_host_only=True)}
        assert full["retire_package"]["host_only"] is True
        assert full["prepare_package"]["long"] is True
        assert full["read_package"]["host_only_args"] == ["reveal"]
        assert "handler" not in full["search_lore"]

    def test_every_write_tool_names_a_package(self):
        writes = ("edit_package", "draft_operation", "remove_operation",
                  "preview_package", "validate_package", "prepare_package",
                  "publish_package", "resolve_package", "retire_package")
        for name in writes:
            assert "uid" in TOOL_INDEX[name]["args"]["required"], name


# ---------------------------------------------------------------------------
# The one call site
# ---------------------------------------------------------------------------

class TestRunTool:
    def test_arguments_are_checked_against_the_schema(self, temp_db):
        cid, _ = _story(temp_db)
        with pytest.raises(ToolError, match="no tool"):
            run_tool(cid, "drop_table")
        with pytest.raises(ToolError, match="requires query"):
            run_tool(cid, "search_lore", {})
        with pytest.raises(ToolError, match="takes no argument sql"):
            run_tool(cid, "search_lore", {"query": "x", "sql": "DELETE"})
        with pytest.raises(ToolError, match="must be an? integer"):
            run_tool(cid, "search_lore", {"query": "x", "k": "many"})
        with pytest.raises(ToolError, match="must be an? integer"):
            run_tool(cid, "search_lore", {"query": "x", "k": True})

    def test_host_only_tools_and_arguments_are_refused_without_host(self, temp_db):
        cid, _ = _story(temp_db)
        pkg = run_tool(cid, "new_package", {"title": "T", "spoiler_policy": "sealed"})
        with pytest.raises(ToolError, match="host action"):
            run_tool(cid, "retire_package", {"uid": pkg["uid"]})
        with pytest.raises(ToolError, match="host action"):
            run_tool(cid, "read_package", {"uid": pkg["uid"], "reveal": True})
        assert run_tool(cid, "read_package", {"uid": pkg["uid"]})["sealed"]
        assert run_tool(cid, "read_package", {"uid": pkg["uid"], "reveal": True},
                        host=True)["title"] == "T"
        assert run_tool(cid, "retire_package", {"uid": pkg["uid"]},
                        host=True)["status"] == "retired"

    def test_a_seam_refusal_is_returned_not_raised(self, temp_db):
        cid, _ = _story(temp_db)
        out = run_tool(cid, "publish_package", {"uid": "plot:nobody",
                                                 "expected_revision": 1})
        assert out == {"refused": "no package 'plot:nobody'"}

    def test_a_result_past_the_ceiling_is_truncated(self, temp_db, monkeypatch):
        cid, _ = _story(temp_db)
        big = {"rows": ["x" * 100] * (TOOL_RESULT_CHARS // 50)}
        monkeypatch.setitem(TOOL_INDEX["inspect_clock"], "handler",
                            lambda cid_, frame_id: big)
        out = run_tool(cid, "inspect_clock")
        assert out["truncated"] and len(out["text"]) == TOOL_RESULT_CHARS


# ---------------------------------------------------------------------------
# Read tools over a fixture world
# ---------------------------------------------------------------------------

class TestReadTools:
    def test_lore_is_searched_scanned_and_read_with_citations(self, temp_db, monkeypatch):
        from mind.memory import add_lore
        cid, bid = _story(temp_db)
        other = temp_db.qi("INSERT INTO lorebooks(name,chat_id) VALUES(?,?)",
                           ("Elsewhere", None))
        eid = add_lore(bid, "drowned bell", "The bell went under in the wet year.",
                       category="event", title="The Drowned Bell",
                       source_notes="imported_canon by host", embedding=[0.0] * 4)
        foreign = add_lore(other, "secret", "Not this story's.", embedding=[0.0] * 4)
        monkeypatch.setattr(
            "mind.memory.search_lore",
            lambda ids, query, k=6, exclude_categories=None: [{
                "id": eid, "entry_uid": "u", "book_id": bid, "keys": "drowned bell",
                "content": "The bell went under in the wet year.",
                "category": "event", "locked": 0, "title": "The Drowned Bell",
                "_k": k}])
        hits = run_tool(cid, "search_lore", {"query": "bell", "k": 99})["hits"]
        assert hits[0]["citation"] == "lore:%d" % eid
        assert hits[0]["excerpt"].startswith("The bell")
        assert run_tool(cid, "search_lore", {"query": "bell",
                                             "categories": ["myth"]})["hits"] == []
        full = run_tool(cid, "read_lore", {"entry_id": eid})
        assert full["content"].endswith("wet year.") and full["provenance"] == \
            "imported_canon by host"
        with pytest.raises(ToolError, match="not attached"):
            run_tool(cid, "read_lore", {"entry_id": foreign})
        page = run_tool(cid, "scan_lore", {"limit": 1})
        assert [e["id"] for e in page["entries"]] == [eid]
        assert page["next_cursor"] is None
        with pytest.raises(ToolError, match="not attached"):
            run_tool(cid, "scan_lore", {"book_id": other})

    def test_rooms_routes_and_the_plan_topology(self, temp_db):
        from world.structure import plant_structure
        cid, _ = _story(temp_db)
        plant_structure(cid, {"key": "chapel", "name": "Chapel"}, {
            "chapel_nave": {"name": "Nave", "adjacent": [{"to": "loft", "barrier": "open"}]}})
        rooms = run_tool(cid, "inspect_rooms")
        assert {r["id"] for r in rooms["rooms"]} == {"quay", "warehouse", "loft"}
        quay = next(r for r in rooms["rooms"] if r["id"] == "quay")
        assert quay["occupants"] == [PLAYER]
        assert [p["id"] for p in rooms["planned_only"]] == ["chapel_nave"]
        route = run_tool(cid, "inspect_route", {"from_room": "quay", "to_room": "warehouse"})
        assert route["path"] == ["quay", "warehouse"] and route["hops"] == 1
        # A locked door is not walked; the plan's edge is.
        blocked = run_tool(cid, "inspect_route", {"from_room": "quay", "to_room": "loft"})
        assert blocked["hops"] is None and "warehouse" in blocked["reachable"]
        planned = run_tool(cid, "inspect_route", {"from_room": "loft", "to_room": "chapel_nave"})
        assert planned["hops"] == 1
        with pytest.raises(ToolError, match="exists nowhere"):
            run_tool(cid, "inspect_route", {"from_room": "moon", "to_room": "quay"})
        structures = run_tool(cid, "inspect_structures")
        assert "chapel" in structures["structures"]
        assert structures["planned_rooms"] == ["chapel_nave"]

    def test_reserved_identities_plans_needs_clock_and_packages(self, temp_db):
        from world.planned_entities import add_planned_entity
        from world.planning_needs import file_planning_need
        cid, _ = _story(temp_db)
        char_id = temp_db.qi("INSERT INTO characters(name,sheet,created) VALUES(?,?,?)",
                             ("Mara Quill", "{}", time.time()))
        temp_db.qi("INSERT INTO chat_chars(chat_id,char_id) VALUES(?,?)", (cid, char_id))
        add_planned_entity(cid, {"kind": "person", "name": "Old Sel",
                                 "aliases": ["the netmender"],
                                 "brief": {"where": "quay"}})
        file_planning_need(cid, {"kind": "thing", "surface": {"name": "the rope"}})
        temp_db.wset(cid, "simulation_clock", {"elapsed_seconds": 3600.0,
                                               "hour_of_day": 19.0,
                                               "day_length_hours": 24.0})
        ids = run_tool(cid, "inspect_reserved_identities")
        assert [c["name"] for c in ids["characters"]] == ["Mara Quill"]
        assert ids["plans"][0]["aliases"] == ["the netmender"]
        assert ids["charter_bodies"] == []
        assert run_tool(cid, "inspect_plans", {"kind": "thing"})["plans"] == []
        assert run_tool(cid, "inspect_plans")["plans"][0]["name"] == "Old Sel"
        needs = run_tool(cid, "inspect_needs")["needs"]
        assert [n["subject"] for n in needs] == ["the rope"]
        clock = run_tool(cid, "inspect_clock")
        from world.day_cycle import phase_of_hour
        assert clock["turn_idx"] == 2 and clock["phase"] == phase_of_hour(19.0)
        assert clock["hour_of_day"] == 19.0
        run_tool(cid, "new_package", {"title": "Bell"})
        listed = run_tool(cid, "inspect_packages", {"status": "draft"})["packages"]
        assert listed[0]["title"] == "Bell" and listed[0]["status"] == "draft"

    def test_events_and_contradictions(self, temp_db):
        from story.authored_events import mint_authored_events
        from world.planned_entities import add_planned_entity
        from world.structure import plant_structure
        cid, _ = _story(temp_db)
        temp_db.qi("INSERT INTO events(chat_id,turn_id,content) VALUES(?,?,?)",
                   (cid, None, "Wren walked the quay."))
        mint_authored_events(cid, 2, [{"summary": "the bell rings", "due_in_turns": 2}],
                             source="writers_room")
        events = run_tool(cid, "inspect_events", {"n": 5})
        assert events["recent"][0]["content"] == "Wren walked the quay."
        assert events["pending"][0]["summary"] == "the bell rings"
        assert events["pending"][0]["source"] == "writers_room"
        plant_structure(cid, {"key": "chapel", "name": "Chapel"}, {
            "chapel_nave": {"name": "Nave", "adjacent": [{"to": "crypt"}]}})
        add_planned_entity(cid, {"kind": "person", "name": "Nobody",
                                 "brief": {"where": "gone_room"}})
        found = run_tool(cid, "inspect_contradictions")
        kinds = {(d["kind"], d.get("to") or d.get("where")) for d in found["dangling"]}
        assert ("planned_exit_to_nowhere", "crypt") in kinds
        assert ("plan_in_no_room", "gone_room") in kinds
        assert isinstance(found["registry"], list)


# ---------------------------------------------------------------------------
# Write tools -- the whole loop through the facade
# ---------------------------------------------------------------------------

def test_the_room_authors_a_package_through_the_facade_alone(temp_db):
    from world.planned_entities import planned_entities
    cid, _ = _story(temp_db)
    pkg = run_tool(cid, "new_package", {
        "title": "The Bell Without a Ringer", "premise": "Somebody rang it.",
        "authority": {"may_create_people": True}})
    uid = pkg["uid"]
    run_tool(cid, "edit_package", {"uid": uid, "fields": {
        "truths": [{"id": "truth_1", "text": "The verger rang it."}],
        "evidence": [{"text": "a wet rope", "origin": "the verger", "location": "quay",
                      "bears_on": ["truth_1"], "admission_path": "seen on the quay"}]}})
    drafted = run_tool(cid, "draft_operation", {"uid": uid, "operation": {
        "op": "plan_entity", "name": "Verger Hale", "role": "verger",
        "brief": {"purpose": "Keeps the chapel.", "truths": "Rang the bell.",
                  "where": "quay"}}})
    assert drafted["operations"] == ["plan_entity"]
    refused = run_tool(cid, "draft_operation", {"uid": uid, "operation": {
        "op": "write_memory", "who": "Mara Quill", "text": "The verger did it."}})
    assert "not one the room may perform" in refused["refused"]
    preview = run_tool(cid, "preview_package", {"uid": uid})
    assert preview["errors"] == [] and preview["changes"][0]["kind"] == "plan_filed"
    verdict = run_tool(cid, "validate_package", {"uid": uid})
    assert verdict["ok"]
    stale = run_tool(cid, "publish_package", {"uid": uid, "expected_revision": 1})
    assert "revision" in stale["refused"]
    out = run_tool(cid, "publish_package", {"uid": uid,
                                            "expected_revision": verdict["at_revision"]})
    assert out["applied"][0]["op"] == "plan_entity"
    assert [p["name"] for p in planned_entities(cid).values()] == ["Verger Hale"]
    assert run_tool(cid, "read_package", {"uid": uid})["status"] == "published"
    assert run_tool(cid, "resolve_package", {"uid": uid, "note": "done"})["status"] == "resolved"
