"""One reader of the world's rooms (`story/room_slice.py`), and the two
readers that now call it: `inspect_rooms` (`story/room_tools.py`) and the
frontier (`story/room_frontier.py`).

The defect this pins: the frontier told the Story Planner the player was in
`room_elevator_interior` while `inspect_rooms` listed that room only under
`containment` (it carries `parent_entity`) and never as a room, so the
Writers' Room in chat 115 planned a second lift car beside the one the cast
stood in. Two readers deriving "what rooms are there" separately is the
class; the index and the slice are the fix, and the frontier counts over the
same graph the index does.
"""
from __future__ import annotations

import json
import time

import pytest

from story import room_frontier as rf
from story.room_slice import (
    DESCRIPTION_CHARS, attire_summary, room_hops, room_index, room_slice,
    room_slices)
from story.room_tools import TOOL_RESULT_CHARS, fit_result, run_tool

#: The chat has no persona, so the player's name is the default one.
PLAYER = "The Stranger"


def _scene():
    return {"location": "Shelter", "rooms": {
        # The lift car is the inside of a body, `elevator`, that stands in
        # the shaft. Its own declared edge is not a way anywhere.
        "lift_car": {"name": "Lift Car", "desc": "Brushed steel.",
                     "parent_entity": "elevator",
                     "adjacent": [{"to": "lobby", "barrier": "open_door"}]},
        "shaft": {"name": "Shaft", "desc": "Cables.",
                  "adjacent": [{"to": "corridor", "barrier": "open_door"}]},
        "corridor": {"name": "Corridor", "desc": "Concrete. " * 200,
                     "adjacent": [{"to": "shaft", "barrier": "open_door"},
                                  {"to": "lobby", "barrier": "open_door", "dir": "n"}],
                     "anchors": {"crate": {"desc": "A crate."}}},
        "lobby": {"name": "Lobby", "desc": "Dust.",
                  "adjacent": [{"to": "corridor", "barrier": "open_door"},
                               {"to": "vault", "barrier": "locked_door"}]},
        "vault": {"name": "Vault", "desc": "Sealed.",
                  "adjacent": [{"to": "lobby", "barrier": "locked_door"}]},
    }, "entities": {
        "elevator": {"name": "the elevator", "kind": "vehicle"},
        "crate": {"name": "A crate", "kind": "object",
                  "plan_ref": {"uid": "plan:thing:crate:1"}},
        "Mara": {"name": "Mara", "kind": "person"},
    }, "positions": {PLAYER: "lift_car", "elevator": "shaft", "Mara": "corridor"},
        "stations": {"Mara": {"at": "crate", "near": []}},
        "attire": {"Mara": {"wearing": ["coat"], "state": ["coat open"],
                            "regions": {"torso": {"garments": [{"name": "coat"}]}}}}}


def _story(db, scene=None):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Shelter", "Underground.", time.time()))
    db.wset(cid, "scene", scene or _scene())
    tid = None
    for i in range(3):
        tid = db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
                    (cid, i, "", time.time()))
    # The plan: an annex off the lobby, and a store beyond the annex.
    from world.structure import plant_structure
    plant_structure(cid, {"key": "annex", "name": "Annex"}, {
        "annex_hall": {"name": "Annex Hall", "purpose": "a way through",
                       "adjacent": [{"to": "lobby", "barrier": "open"}]},
        "annex_store": {"name": "Annex Store", "purpose": "stores",
                        "adjacent": [{"to": "annex_hall"}]},
    })
    # A room the story once had and retired: its id is spent.
    db.qi("INSERT INTO room_registry(chat_id,room_uid,name,payload,retired_turn_id) "
          "VALUES(?,?,?,?,?)", (cid, "old_boiler", "Old Boiler Room", "{}", tid))
    return cid


# ---------------------------------------------------------------------------
# The index
# ---------------------------------------------------------------------------

class TestTheIndex:
    def test_every_room_the_story_knows_with_its_status_holder_and_hops(self, temp_db):
        cid = _story(temp_db)
        rows = room_index(cid, None)
        by_id = {r["id"]: r for r in rows}
        assert set(rows[0]) == {"id", "name", "status", "holder", "region", "hops"}
        assert {r["status"] for r in rows} == {"live", "planned", "retired"}
        # Cast rooms first, at 0: the corridor (Mara) and the lift car (the
        # player, inside the elevator).
        assert [(r["id"], r["hops"]) for r in rows[:2]] == [("corridor", 0), ("lift_car", 0)]
        assert by_id["lift_car"]["holder"] == "elevator"
        assert by_id["lift_car"]["name"] == "Lift Car"
        # Hops count through the holder: out of the car into the shaft is
        # one; the shaft is also one from the corridor, the lobby one, the
        # planned annex two, its store three.
        assert by_id["shaft"]["hops"] == 1 and by_id["lobby"]["hops"] == 1
        assert by_id["annex_hall"] == {"id": "annex_hall", "name": "Annex Hall",
                                       "status": "planned", "holder": None,
                                       "region": "annex", "hops": 2}
        assert by_id["annex_store"]["hops"] == 3
        # A CLOSED DOOR IS A HOP, NOT A WALL. `normalize_barrier` folds a
        # locked door onto `closed_door`, and a hop count answers what the
        # story can REACH rather than what a body may step through this beat,
        # so the vault behind the shaft's locked door is two hops out.
        # Counted over `passable_neighbors`, a house of shut doors read as a
        # house of unreachable rooms and the Room's own map put most of it
        # beyond the frontier (PX15, masque run, 2026-09-05).
        assert by_id["vault"]["hops"] == 2
        assert by_id["old_boiler"] == {"id": "old_boiler", "name": "Old Boiler Room",
                                       "status": "retired", "holder": None,
                                       "region": None, "hops": None}
        # Grouped by region: the shelter's rooms (no region) hold the cast and
        # come first, the retired row last among them; the annex is a region
        # of its own and follows as a block.
        assert [r["id"] for r in rows] == ["corridor", "lift_car", "lobby", "shaft",
                                           "vault", "old_boiler",
                                           "annex_hall", "annex_store"]
        hops = [r["hops"] for r in rows if r["hops"] is not None]
        assert hops == sorted(hops)

    def test_an_inside_is_joined_to_its_holder_and_nothing_else(self, temp_db):
        """The car declares an edge to the lobby; the graph ignores it. A
        body's inside is where the world put a body, not a way anywhere."""
        cid = _story(temp_db)
        hops = room_hops(cid, temp_db.wget(cid, "scene"), ["lift_car"])
        assert hops["shaft"] == 1 and hops["corridor"] == 2 and hops["lobby"] == 3

    def test_a_scene_passed_in_is_the_one_read(self, temp_db):
        cid = _story(temp_db)
        scene = _scene()
        scene["positions"] = {PLAYER: "vault"}
        rows = room_index(cid, None, scene)
        assert rows[0] == {"id": "vault", "name": "Vault", "status": "live",
                           "holder": None, "region": None, "hops": 0}


# ---------------------------------------------------------------------------
# The slice
# ---------------------------------------------------------------------------

class TestTheSlice:
    def test_the_shape_of_a_live_room(self, temp_db):
        cid = _story(temp_db)
        row = room_slice(cid, None, "corridor")
        assert set(row) == {"id", "name", "status", "holder", "region", "region_name",
                            "description", "exits", "occupants", "things",
                            "planned_stub", "plan_here"}
        assert (row["id"], row["name"], row["status"], row["holder"]) == (
            "corridor", "Corridor", "live", None)
        assert len(row["description"]) <= DESCRIPTION_CHARS
        assert {e["to"]: (e["barrier"], e["dir"], e["status"]) for e in row["exits"]} == {
            "shaft": ("open_door", None, "live"), "lobby": ("open_door", "n", "live")}
        # Station and attire ride as stored.
        assert row["occupants"] == [{"name": "Mara", "station": {"at": "crate", "near": []},
                                     "attire": _scene()["attire"]["Mara"]}]
        assert row["things"] == [{"id": "crate", "name": "A crate", "kind": "object",
                                  "plan_ref": "plan:thing:crate:1"}]
        assert row["planned_stub"] is None
        assert row["plan_here"] == {"planned_entities": [], "needs": [], "package_ops": []}

    def test_an_inside_carries_its_holder(self, temp_db):
        cid = _story(temp_db)
        row = room_slice(cid, None, "lift_car")
        assert row["holder"] == "elevator"
        assert [o["name"] for o in row["occupants"]] == [PLAYER]
        assert row["occupants"][0]["station"] is None and row["occupants"][0]["attire"] is None

    def test_a_planned_room_carries_the_plans_brief_and_its_exits(self, temp_db):
        cid = _story(temp_db)
        row = room_slice(cid, None, "annex_hall")
        assert row["status"] == "planned" and row["description"] == ""
        assert row["planned_stub"]["purpose"] == "a way through"
        assert {e["to"]: e["status"] for e in row["exits"]} == {"lobby": "live"}
        store = room_slice(cid, None, "annex_store")
        assert {e["to"]: e["status"] for e in store["exits"]} == {"annex_hall": "planned"}

    def test_a_retired_room_is_a_spent_id(self, temp_db):
        cid = _story(temp_db)
        row = room_slice(cid, None, "old_boiler")
        assert row["status"] == "retired" and row["exits"] == [] and row["occupants"] == []

    def test_an_unknown_id_is_none_and_skipped(self, temp_db):
        cid = _story(temp_db)
        assert room_slice(cid, None, "nowhere") is None
        assert [r["id"] for r in room_slices(cid, None, ["nowhere", "lobby"])] == ["lobby"]

    def test_plan_here_is_what_the_author_layer_claims_for_the_room(self, temp_db):
        from story.plot_packages import draft_operation, new_package
        from world.planned_entities import add_planned_entity
        from world.planning_needs import file_planning_need
        cid = _story(temp_db)
        add_planned_entity(cid, {"kind": "thing", "name": "a lantern",
                                 "brief": {"where": "lobby"}})
        add_planned_entity(cid, {"kind": "person", "name": "Odile",
                                 "brief": {"where": "annex_hall"}})
        need, _ = file_planning_need(cid, {"kind": "room", "subject": "lobby",
                                           "reason": "location_query_unmatched"})
        stranger, _ = file_planning_need(cid, {"kind": "person",
                                               "surface": {"name": "a guard", "room": "lobby"}})
        pkg = new_package(cid, title="Bills")
        draft_operation(cid, pkg["uid"], {"op": "post_artifact", "room": "lobby",
                                          "description": "a notice"})
        draft_operation(cid, pkg["uid"], {"op": "post_artifact", "room": "shaft",
                                          "description": "a warning"})
        sealed = new_package(cid, title="Secret", spoiler_policy="sealed")
        draft_operation(cid, sealed["uid"], {"op": "post_artifact", "room": "lobby",
                                             "description": "a hidden mark"})
        here = room_slice(cid, None, "lobby")["plan_here"]
        assert [(p["kind"], p["name"], p["rendered"]) for p in here["planned_entities"]] == [
            ("thing", "a lantern", False)]
        assert {n["uid"] for n in here["needs"]} == {need["uid"], stranger["uid"]}
        # The open package's operation on this room, by index; the sealed
        # package's is what `read_package reveal` is for.
        assert here["package_ops"] == [{"package": pkg["uid"], "title": "Bills",
                                        "status": "draft", "index": 0, "op": "post_artifact"}]
        assert room_slice(cid, None, "shaft")["plan_here"]["package_ops"][0]["index"] == 1

    def test_attire_summary_is_the_ledgers_own_summary(self):
        assert attire_summary(_scene()["attire"]["Mara"]) == {
            "wearing": ["coat"], "state": ["coat open"]}
        assert attire_summary(None) is None


# ---------------------------------------------------------------------------
# The tool
# ---------------------------------------------------------------------------

class TestInspectRooms:
    def test_no_arguments_is_the_index_and_the_neighbourhood(self, temp_db):
        cid = _story(temp_db)
        out = run_tool(cid, "inspect_rooms")
        assert set(out) == {"location", "index", "rooms"}
        assert out["index"] == room_index(cid, None)
        # Within FRONTIER_DEPTH_HOPS of the cast, planned stubs included;
        # the store at three hops and the retired room are index-only. The
        # vault is two hops through a locked door, which is a door (PX15).
        assert {r["id"] for r in out["rooms"]} == {
            "corridor", "lift_car", "shaft", "lobby", "annex_hall", "vault"}
        assert all(r["hops"] is not None and r["hops"] <= rf.FRONTIER_DEPTH_HOPS
                   for r in out["index"] if r["id"] in {s["id"] for s in out["rooms"]})
        # The tool carries the ledger's summary, not the region table.
        corridor = next(r for r in out["rooms"] if r["id"] == "corridor")
        assert corridor["occupants"][0]["attire"] == {"wearing": ["coat"],
                                                      "state": ["coat open"]}

    def test_room_ids_opens_any_status(self, temp_db):
        cid = _story(temp_db)
        out = run_tool(cid, "inspect_rooms",
                       {"room_ids": ["old_boiler", "annex_store", "vault", "nowhere"]})
        assert "index" not in out
        assert [(r["id"], r["status"]) for r in out["rooms"]] == [
            ("old_boiler", "retired"), ("annex_store", "planned"), ("vault", "live")]
        assert out["unknown"] == ["nowhere"]

    def test_the_tool_takes_no_include_planned(self, temp_db):
        from story.room_tools import ToolError
        cid = _story(temp_db)
        with pytest.raises(ToolError, match="takes no argument include_planned"):
            run_tool(cid, "inspect_rooms", {"include_planned": True})


# ---------------------------------------------------------------------------
# The cap
# ---------------------------------------------------------------------------

class TestFitResult:
    def test_under_the_cap_is_untouched(self):
        small = {"rows": [1, 2, 3]}
        assert fit_result(small, 100) is small

    def test_over_the_cap_drops_trailing_items_and_stays_valid_json(self):
        big = {"index": [{"id": "r%02d" % i, "hops": i} for i in range(40)],
               "rooms": [{"id": "r%02d" % i, "description": "x" * 400} for i in range(6)]}
        original = json.dumps(big)
        out = fit_result(big, 2400)
        encoded = json.dumps(out)
        assert len(encoded) <= 2400 < len(original)
        assert json.loads(encoded) == out
        assert out["truncated"] is True and out["dropped"] > 0
        # Trailing items go first from the list that costs most -- the
        # slices, farthest first -- and the index stays whole.
        assert out["index"] == big["index"]
        assert out["rooms"] == big["rooms"][:len(out["rooms"])]
        assert out["dropped"] == 6 - len(out["rooms"])
        # The original is not mutated.
        assert len(big["rooms"]) == 6 and "truncated" not in big

    def test_when_no_list_has_an_item_left_whole_keys_go(self):
        out = fit_result({"text": "y" * 500, "note": "z" * 50, "rows": []}, 120)
        assert json.dumps(out).__len__() <= 120
        assert "text" not in out and out["note"] == "z" * 50
        assert out["dropped"] >= 1

    def test_never_longer_than_the_original(self):
        for cap in (40, 200, 1000, 5000):
            big = {"rows": ["x" * 100] * 80}
            assert len(json.dumps(fit_result(big, cap))) <= len(json.dumps(big))

    def test_the_counted_cut_is_the_re_encoded_cut(self):
        """`fit_result` composes each container's encoded length from its
        parts instead of re-serializing the whole result once per dropped
        item (review 2026-09-07, C21: 22.4 s to cut 2,942 rows down to the
        cap, 0.14 s after; `inspect_charters` on the bench copy of chat 114,
        8.4 ms to 2.9 ms). The arithmetic is the claim, so it is checked
        against the encoder it replaced, over the shapes it has to get right
        -- unicode, escapes, nested containers, empty lists, non-string
        values.
        """
        import random

        def _length(value):
            return len(json.dumps(value, ensure_ascii=False, default=str))

        def re_encoded_cut(result, cap):
            """What it did before: measure by encoding, every time."""
            if not isinstance(result, dict):
                return result
            if _length(result) <= cap:
                return result
            out = json.loads(json.dumps(result, ensure_ascii=False, default=str))
            out["truncated"] = True
            out["dropped"] = 0
            while _length(out) > cap:
                lists = [(k, _length(v)) for k, v in out.items()
                         if isinstance(v, list) and v]
                if lists:
                    out[max(lists, key=lambda kv: kv[1])[0]].pop()
                else:
                    keys = [(k, _length(v)) for k, v in out.items()
                            if k not in ("truncated", "dropped")]
                    if not keys:
                        break
                    out.pop(max(keys, key=lambda kv: kv[1])[0])
                out["dropped"] += 1
            return out

        random.seed(11)
        alphabet = "abc \u00e9\u65e5\\\""
        shapes = [{"rows": [{"i": i, "text": "x" * 180} for i in range(60)]},
                  {"only": ["\u00e9" * 30] * 12},
                  {"a": [], "b": "z" * 400, "c": {"deep": [1, 2, [3, {"d": 4}]]}},
                  {"n": 12, "f": 3.5, "t": True, "none": None,
                   "rows": [["a", "b"], ["c"]]}]
        for _ in range(60):
            shape = {}
            for k in range(random.randint(1, 5)):
                shape["k%d" % k] = [
                    "".join(random.choice(alphabet)
                            for _ in range(random.randint(0, 30)))
                    for _ in range(random.randint(0, 25))]
            shapes.append(shape)
        for shape in shapes:
            for cap in (12, 80, 300, 1500, 12_000):
                assert (json.dumps(fit_result(shape, cap))
                        == json.dumps(re_encoded_cut(shape, cap))), (shape, cap)

    def test_the_run_tool_wrapper_is_the_same_cut(self, temp_db, monkeypatch):
        from story.room_tools import TOOL_INDEX
        cid = _story(temp_db)
        big = {"rows": ["x" * 100] * (TOOL_RESULT_CHARS // 50)}
        monkeypatch.setitem(TOOL_INDEX["inspect_clock"], "handler",
                            lambda cid_, frame_id: big)
        out = run_tool(cid, "inspect_clock")
        assert out == fit_result(big, TOOL_RESULT_CHARS)
        assert len(json.dumps(out)) <= TOOL_RESULT_CHARS


# ---------------------------------------------------------------------------
# The frontier agrees with the index
# ---------------------------------------------------------------------------

class TestTheFrontierAgrees:
    def test_the_players_room_is_the_room_they_stand_in_and_its_holder_is_named(self, temp_db):
        cid = _story(temp_db)
        report = rf.frontier_report(cid, None)
        assert report["player_room"] == "lift_car"
        assert report["player_holder"] == "elevator"
        index = {r["id"]: r for r in run_tool(cid, "inspect_rooms")["index"]}
        assert index["lift_car"]["holder"] == "elevator" and index["lift_car"]["hops"] == 0

    def test_reachable_counts_out_through_the_holders_room(self, temp_db):
        cid = _story(temp_db)
        scene = temp_db.wget(cid, "scene")
        reachable, stubs = rf.rooms_ahead(cid, scene, "lift_car")
        # One hop out is the shaft; two is the corridor. The car's own
        # declared edge to the lobby is not walked, so the lobby is three
        # away and not ahead. Nothing is dropped silently: the car is the
        # start, and the start is never in its own `reachable`.
        assert reachable == ["corridor", "shaft"] and stubs == []
        hops = room_hops(cid, scene, ["lift_car"])
        assert reachable == sorted(r for r, n in hops.items() if 0 < n <= rf.FRONTIER_DEPTH_HOPS)
        report = rf.frontier_report(cid, None)
        assert report["reachable"] == reachable

    def test_another_bodys_inside_is_counted_through_and_never_listed(self, temp_db):
        cid = _story(temp_db)
        scene = temp_db.wget(cid, "scene")
        reachable, stubs = rf.rooms_ahead(cid, scene, "shaft")
        assert "lift_car" not in reachable
        assert reachable == ["corridor", "lobby"] and stubs == []
        # One hop deeper and the plan's annex is ahead, as a stub -- and so is
        # the vault, through the lobby's locked door, because a locked door is
        # a state of a door and not a kind of wall (PX15).
        reachable, stubs = rf.rooms_ahead(cid, scene, "shaft", depth=3)
        assert "lift_car" not in reachable
        assert reachable == ["annex_hall", "corridor", "lobby", "vault"] \
            and stubs == ["annex_hall"]
