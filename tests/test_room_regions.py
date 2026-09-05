"""Regions: which part of the map a room belongs to (`world/regions.py`).

The class this pins: the engine held three half-answers to "which part of the
map is this" -- `zone` on a room, `structure` on a planned room, a
`region_event` footprint -- and none covered a live room the Director minted.
Chat 115 came to hold a Director-minted lift car beside a planned one with
nothing anywhere saying they were the same part of the map, and the room
index sorted by distance with nothing to group by.

One field, `region`, derived deterministically and never by name: a planned
room's is its structure; a minted room inherits the region of the room it
was reached from, the occupied room deciding a disagreement; an inside
reports its holder's; a zone is folded once; nothing is invented. Carried in
the scene, the registry payload and a frame-scoped registry of what the
regions are; read by the index (grouped), the slice, the briefs and the
contradiction check.
"""
from __future__ import annotations

import copy
import json
import time

import pytest

from core.pipeline_context import ChatData, PipelineContext, TurnData
from persist import commit
from story.room_slice import room_index, room_slice
from story.room_tools import run_tool
from world.regions import (
    REGIONS_KEY, assign_regions, backfill_regions, normalize_region_id,
    region_registry, room_pieces, room_region)
from world.structure import plant_structure

PLAYER = "The Stranger"


def _chat(db, name="Regions"):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                (name, "A harbour town.", time.time()))
    # A canon book: the registry files every open-location room under one.
    bid = db.qi("INSERT INTO lorebooks(name,chat_id) VALUES(?,?)", ("Canon", cid))
    db.qi("UPDATE chats SET lorebook_id=? WHERE id=?", (bid, cid))
    for i in range(3):
        db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
              (cid, i, "", time.time()))
    return cid


def _ctx(cid, *, idx=1, turn_id=2):
    from core.db import q
    book = q("SELECT lorebook_id FROM chats WHERE id=?", (cid,), one=True)
    return PipelineContext(
        chat=ChatData(id=cid, name="Regions", persona_id=None,
                      lorebook_id=book["lorebook_id"] if book else None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=cid, idx=idx, player_input="",
                      created=time.time()),
        cast=[], input="")


def _plant_harbour(cid):
    """A planned harbour district: a quay joined to a warehouse."""
    plant_structure(cid, {"key": "harbour_district", "name": "Harbour District"}, {
        "quay": {"name": "Quay", "purpose": "landing",
                 "adjacent": [{"to": "warehouse", "barrier": "open"}]},
        "warehouse": {"name": "Warehouse", "purpose": "stores",
                      "adjacent": [{"to": "quay", "barrier": "open"}]},
    })


def _harbour_scene():
    """The harbour, live and regioned, with the player on the quay."""
    return {"location": "Harbour", "rooms": {
        "quay": {"name": "Quay", "desc": "Wet stone.", "region": "harbour_district",
                 "adjacent": [{"to": "warehouse", "barrier": "open"}]},
        "warehouse": {"name": "Warehouse", "desc": "Crates.", "region": "harbour_district",
                      "adjacent": [{"to": "quay", "barrier": "open"}]},
    }, "positions": {PLAYER: "quay"}, "entities": {}, "attire": {}}


def _resolve(cid, prev_scene, diff, *, positions=None):
    """One resolved beat through the scene domain: the prepared bundle."""
    from core.db import wset
    wset(cid, "scene", prev_scene)
    ctx = _ctx(cid)
    ctx.director_resolve = {"state_diff": copy.deepcopy(diff)}
    return ctx, commit.prepare_scene_commit(ctx)


# ---------------------------------------------------------------------------
# Derivation
# ---------------------------------------------------------------------------

class TestDerivation:
    def test_a_planned_rooms_region_is_its_structure(self, temp_db):
        cid = _chat(temp_db)
        _plant_harbour(cid)
        from story.scene import get_scene
        scene = get_scene(cid)
        # Seeded from the plan, the rooms already know their part of the map.
        assert scene["rooms"]["quay"]["region"] == "harbour_district"
        ctx = _ctx(cid, idx=0, turn_id=1)
        ctx.director_establish = {"state_diff": {
            "rooms": {"quay": {"name": "Quay", "desc": "Wet stone."}},
            "positions": {PLAYER: "quay"}}}
        committed = commit.prepare_scene_commit(ctx)["scene"]
        assert committed["rooms"]["quay"]["region"] == "harbour_district"
        assert committed["rooms"]["warehouse"]["region"] == "harbour_district"
        # A structure IS a region: the registry names it without storing it.
        assert region_registry(cid, None)["harbour_district"]["name"] == "Harbour District"

    def test_a_minted_room_inherits_the_region_it_was_reached_from(self, temp_db):
        cid = _chat(temp_db)
        _plant_harbour(cid)
        ctx, prepared = _resolve(cid, _harbour_scene(), {
            "rooms": {"customs_house": {
                "name": "Customs House", "desc": "Ledgers.",
                "adjacent": [{"to": "quay", "barrier": "open_door"}]}},
            "positions": {PLAYER: "customs_house"}})
        sc = prepared["scene"]
        assert sc["rooms"]["customs_house"]["region"] == "harbour_district"
        # Two beats on: a room minted off the minted one inherits in turn.
        ctx2, prepared2 = _resolve(cid, sc, {
            "rooms": {"back_office": {
                "name": "Back Office", "desc": "A desk.",
                "adjacent": [{"to": "customs_house", "barrier": "open_door"}]}}})
        assert prepared2["scene"]["rooms"]["back_office"]["region"] == "harbour_district"

    def test_a_chain_minted_in_one_diff_inherits_along_the_chain(self, temp_db):
        cid = _chat(temp_db)
        _plant_harbour(cid)
        _ctx_, prepared = _resolve(cid, _harbour_scene(), {
            "rooms": {
                "alley": {"name": "Alley", "desc": "Narrow.",
                          "adjacent": [{"to": "quay", "barrier": "open"}]},
                "alley_end": {"name": "Alley End", "desc": "A wall.",
                              "adjacent": [{"to": "alley", "barrier": "open"}]}}})
        rooms = prepared["scene"]["rooms"]
        assert rooms["alley"]["region"] == "harbour_district"
        assert rooms["alley_end"]["region"] == "harbour_district"

    def test_when_candidates_disagree_the_occupied_room_wins(self):
        scene = {"rooms": {
            "quay": {"name": "Quay", "region": "harbour",
                     "adjacent": [{"to": "arch", "barrier": "open"}]},
            "temple_steps": {"name": "Steps", "region": "temple_hill",
                             "adjacent": [{"to": "arch", "barrier": "open"}]},
            "arch": {"name": "Arch", "adjacent": []},
        }, "positions": {PLAYER: "quay"}}
        result = assign_regions(scene, structures={}, minted={"arch"}, occupied={"quay"})
        assert scene["rooms"]["arch"]["region"] == "harbour"
        assert result["assigned"] == [("arch", "harbour", "reached from quay")]

    def test_disagreeing_candidates_with_no_occupied_room_leave_it_empty(self):
        scene = {"rooms": {
            "quay": {"name": "Quay", "region": "harbour",
                     "adjacent": [{"to": "arch", "barrier": "open"}]},
            "temple_steps": {"name": "Steps", "region": "temple_hill",
                             "adjacent": [{"to": "arch", "barrier": "open"}]},
            "arch": {"name": "Arch", "adjacent": []},
        }, "positions": {}}
        result = assign_regions(scene, structures={}, minted={"arch"}, occupied=set())
        assert "region" not in scene["rooms"]["arch"]
        assert result["assigned"] == []

    def test_nothing_is_invented(self, temp_db):
        """A minted room joined to no regioned room has no region, and a
        story with no regions at all gets none."""
        cid = _chat(temp_db)
        scene = _harbour_scene()
        for room in scene["rooms"].values():
            room.pop("region")
        _ctx_, prepared = _resolve(cid, scene, {
            "rooms": {"lane": {"name": "Lane", "desc": "Cobbles.",
                               "adjacent": [{"to": "quay", "barrier": "open"}]}}})
        assert not any("region" in r for r in prepared["scene"]["rooms"].values())
        assert prepared["regions"] == {}
        assert region_registry(cid, None) == {}

    def test_an_inside_reports_its_holders_rooms_region(self, temp_db):
        cid = _chat(temp_db)
        scene = _harbour_scene()
        scene["rooms"]["hold"] = {"name": "Hold", "desc": "Dark.", "parent_entity": "barge",
                                  "region": "somewhere_stale"}
        scene["entities"] = {"barge": {"name": "the barge", "kind": "vehicle"}}
        scene["positions"]["barge"] = "quay"
        ctx, prepared = _resolve(cid, scene, {})
        sc = prepared["scene"]
        # No region of its own -- the stale one came off -- and it answers
        # with the quay's, where the barge stands.
        assert "region" not in sc["rooms"]["hold"]
        assert room_region(sc, "hold") == "harbour_district"
        assert any("inside of a body" in w for w in ctx.warnings)
        sc["positions"]["barge"] = "nowhere_regioned"
        sc["rooms"]["nowhere_regioned"] = {"name": "Open water", "adjacent": []}
        assert room_region(sc, "hold") is None
        # Nested: a cabin inside the barge reports through both holders.
        sc["positions"]["barge"] = "quay"
        sc["rooms"]["cabin"] = {"name": "Cabin", "parent_entity": "lockbox"}
        sc["entities"]["lockbox"] = {"name": "lockbox", "kind": "object"}
        sc["positions"]["lockbox"] = "hold"
        assert room_region(sc, "cabin") == "harbour_district"

    def test_a_zone_is_folded_into_a_region_once(self, temp_db):
        cid = _chat(temp_db)
        scene = {"location": "Ship", "rooms": {
            "bridge": {"name": "Bridge", "desc": "Consoles.", "zone": "Starship Beta",
                       "adjacent": [{"to": "corridor", "barrier": "open_door"}]},
            "corridor": {"name": "Corridor", "desc": "Grey.",
                         "adjacent": [{"to": "bridge", "barrier": "open_door"}]},
        }, "positions": {PLAYER: "bridge"}, "entities": {}, "attire": {}}
        ctx, prepared = _resolve(cid, scene, {
            "rooms": {"airlock": {"name": "Airlock", "desc": "Sealed.",
                                  "adjacent": [{"to": "bridge", "barrier": "closed_door"}]}}})
        sc = prepared["scene"]
        assert sc["rooms"]["bridge"]["region"] == "starship_beta"
        # The zone itself stays: it is the frame-split trigger, a different class.
        assert sc["rooms"]["bridge"]["zone"] == "Starship Beta"
        # The fold is named as the zone was written, and the minted airlock
        # inherits it. The corridor was standing before and is not minted, so
        # it is not given one at commit -- inheritance is for what the beat
        # reached, the one-shot backfill is for what stood before.
        assert prepared["regions"] == {"starship_beta": "Starship Beta"}
        assert sc["rooms"]["airlock"]["region"] == "starship_beta"
        assert "region" not in sc["rooms"]["corridor"]
        commit.commit_scene(ctx, "nonce", prepared=prepared)
        assert region_registry(cid, None) == {
            "starship_beta": {"name": "Starship Beta", "brief": ""}}
        # Once: a second commit finds the entry standing and rewrites nothing.
        from core.db import wget
        stored = wget(cid, REGIONS_KEY)
        ctx2, prepared2 = _resolve(cid, sc, {})
        commit.commit_scene(ctx2, "nonce2", prepared=prepared2)
        assert wget(cid, REGIONS_KEY) == stored

    def test_a_declared_region_is_kept_normalized_and_named_as_written(self, temp_db):
        cid = _chat(temp_db)
        _plant_harbour(cid)
        ctx, prepared = _resolve(cid, _harbour_scene(), {
            "rooms": {"shrine": {"name": "Shrine", "desc": "Incense.",
                                 "region": "Temple Hill",
                                 "adjacent": [{"to": "quay", "barrier": "open"}]}}})
        sc = prepared["scene"]
        assert sc["rooms"]["shrine"]["region"] == "temple_hill"
        assert prepared["regions"] == {"temple_hill": "Temple Hill"}
        commit.commit_scene(ctx, "nonce", prepared=prepared)
        assert region_registry(cid, None)["temple_hill"]["name"] == "Temple Hill"

    def test_the_director_may_write_region_and_validation_keeps_it(self):
        from llm.schemas import RoomDef
        assert RoomDef(name="x", region="temple_hill").model_dump()["region"] == "temple_hill"

    def test_a_retired_room_keeps_its_region(self, temp_db):
        cid = _chat(temp_db)
        _plant_harbour(cid)
        scene = _harbour_scene()
        scene["rooms"]["shed"] = {"name": "Shed", "desc": "Tar.", "region": "harbour_district",
                                  "adjacent": [{"to": "quay", "barrier": "open"}]}
        ctx, prepared = _resolve(cid, scene, {})
        commit.commit_scene(ctx, "n1", prepared=prepared)
        row = temp_db.q("SELECT payload FROM room_registry WHERE chat_id=? AND room_uid=?",
                        (cid, "shed"), one=True)
        assert json.loads(row["payload"])["region"] == "harbour_district"
        ctx2, prepared2 = _resolve(cid, prepared["scene"], {"remove_rooms": ["shed"]})
        commit.commit_scene(ctx2, "n2", prepared=prepared2)
        rows = {r["id"]: r for r in room_index(cid, None)}
        assert rows["shed"]["status"] == "retired"
        assert rows["shed"]["region"] == "harbour_district"

    def test_region_ids_are_spelled_like_room_ids(self):
        assert normalize_region_id("Harbour  District!") == "harbour_district"
        # A spelling the room-id fold would empty keeps its own text.
        assert normalize_region_id("  港区 ") == "港区"


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

class TestPersistence:
    def _committed(self, temp_db):
        cid = _chat(temp_db)
        _plant_harbour(cid)
        ctx, prepared = _resolve(cid, _harbour_scene(), {
            "rooms": {"shrine": {"name": "Shrine", "desc": "Incense.",
                                 "region": "Temple Hill",
                                 "adjacent": [{"to": "quay", "barrier": "open"}]}}})
        commit.commit_scene(ctx, "nonce", prepared=prepared)
        return cid

    def _facts(self, db, cid):
        from core.db import wget
        scene = wget(cid, "scene")
        payloads = {r["room_uid"]: json.loads(r["payload"]).get("region")
                    for r in db.q("SELECT room_uid, payload FROM room_registry "
                                  "WHERE chat_id=?", (cid,))}
        return ({rid: r.get("region") for rid, r in scene["rooms"].items()},
                payloads, wget(cid, REGIONS_KEY))

    def test_archive_round_trip(self, temp_db):
        from web import app
        cid = self._committed(temp_db)
        before = self._facts(temp_db, cid)
        assert before[0]["shrine"] == "temple_hill" and before[1]["shrine"] == "temple_hill"
        assert before[2]["items"]["temple_hill"]["name"] == "Temple Hill"
        imported = app.chat_import({"data": app.chat_export(cid)})
        assert self._facts(temp_db, imported["id"]) == before
        assert region_registry(imported["id"], None)["harbour_district"]["name"] \
            == "Harbour District"

    def test_checkpoint_round_trip(self, temp_db):
        from core.db import wget, wset
        from persist.checkpoints import ensure_checkpoint, restore_checkpoint
        cid = self._committed(temp_db)
        before = self._facts(temp_db, cid)
        ensure_checkpoint(cid, 2)
        # The story moves on: the shrine changes region, the registry gains
        # an entry, the payload follows.
        scene = wget(cid, "scene")
        scene["rooms"]["shrine"]["region"] = "elsewhere"
        ctx, prepared = _resolve(cid, scene, {})
        commit.commit_scene(ctx, "n2", prepared=prepared)
        wset(cid, REGIONS_KEY, {"items": {"elsewhere": {"name": "Elsewhere", "brief": ""}}})
        assert self._facts(temp_db, cid) != before
        restore_checkpoint(cid, 2)
        assert self._facts(temp_db, cid) == before

    def test_the_registry_key_is_frame_scoped(self):
        from core.db import FRAME_SCOPED_WORLD_KEYS
        assert REGIONS_KEY in FRAME_SCOPED_WORLD_KEYS


# ---------------------------------------------------------------------------
# Readers
# ---------------------------------------------------------------------------

class TestReaders:
    def _two_regions(self, temp_db):
        cid = _chat(temp_db)
        _plant_harbour(cid)
        plant_structure(cid, {"key": "temple_hill", "name": "Temple Hill"}, {
            "temple_steps": {"name": "Temple Steps", "purpose": "a climb",
                             "adjacent": [{"to": "quay", "barrier": "open"}]},
            "sanctum": {"name": "Sanctum", "purpose": "prayer",
                        "adjacent": [{"to": "temple_steps", "barrier": "closed_door"}]},
        })
        scene = _harbour_scene()
        scene["rooms"]["lane"] = {"name": "Lane", "desc": "Cobbles.",
                                  "adjacent": [{"to": "warehouse", "barrier": "open"}]}
        scene["rooms"]["warehouse"]["adjacent"].append({"to": "lane", "barrier": "open"})
        from core.db import wset
        wset(cid, "scene", scene)
        return cid, scene

    def test_the_index_groups_by_region_the_casts_first(self, temp_db):
        cid, scene = self._two_regions(temp_db)
        rows = room_index(cid, None, scene)
        assert [(r["id"], r["region"], r["hops"]) for r in rows] == [
            # The cast's region first, by hops within it.
            ("quay", "harbour_district", 0), ("warehouse", "harbour_district", 1),
            # Then the temple, a planned region whose nearest room is one hop
            # off the quay, as a block.
            ("temple_steps", "temple_hill", 1), ("sanctum", "temple_hill", 2),
            # The unregioned lane is its own group, ranked by its nearest
            # room -- two hops -- so it follows the temple.
            ("lane", None, 2)]

    def test_the_slice_carries_the_region_and_its_name(self, temp_db):
        cid, scene = self._two_regions(temp_db)
        row = room_slice(cid, None, "quay", scene)
        assert (row["region"], row["region_name"]) == ("harbour_district", "Harbour District")
        planned = room_slice(cid, None, "sanctum", scene)
        assert (planned["region"], planned["region_name"]) == ("temple_hill", "Temple Hill")
        assert planned["planned_stub"]["region"] == {"id": "temple_hill", "name": "Temple Hill"}
        lane = room_slice(cid, None, "lane", scene)
        assert (lane["region"], lane["region_name"]) == (None, None)

    def test_the_planned_briefs_mention_the_region(self, temp_db):
        from world.structure import planned_context, planned_room_brief
        cid, scene = self._two_regions(temp_db)
        assert planned_context(cid, "sanctum")["region"] == "temple_hill"
        brief = planned_room_brief(cid, scene, ["sanctum"])["sanctum"]
        assert brief["region"] == {"id": "temple_hill", "name": "Temple Hill"}

    def test_the_tool_index_carries_the_region(self, temp_db):
        cid, _scene = self._two_regions(temp_db)
        out = run_tool(cid, "inspect_rooms")
        assert out["index"][0]["region"] == "harbour_district"


# ---------------------------------------------------------------------------
# What does not agree with itself
# ---------------------------------------------------------------------------

class TestContradictions:
    def test_a_region_in_pieces_is_a_possible_duplicate(self, temp_db):
        cid = _chat(temp_db)
        _plant_harbour(cid)
        scene = _harbour_scene()
        # A second quay, filed under the harbour, joined to nothing the harbour
        # holds: the shape of chat 115's second lift car.
        scene["rooms"]["quay_2"] = {"name": "Quayside", "desc": "Wet stone.",
                                    "region": "harbour_district", "adjacent": []}
        pieces = room_pieces(cid, scene)
        assert pieces == [{"kind": "region_in_pieces", "region": "harbour_district",
                           "pieces": [["quay", "warehouse"], ["quay_2"]]}]
        from core.db import wset
        wset(cid, "scene", scene)
        found = run_tool(cid, "inspect_contradictions")
        assert pieces[0] in found["dangling"]

    def test_a_region_joined_through_a_wall_or_the_plan_is_whole(self, temp_db):
        cid = _chat(temp_db)
        _plant_harbour(cid)
        scene = _harbour_scene()
        # Joined by a wall edge only: still one place, built on one side of it.
        scene["rooms"]["yard"] = {"name": "Yard", "region": "harbour_district",
                                  "adjacent": [{"to": "warehouse", "barrier": "wall"}]}
        assert room_pieces(cid, scene) == []
        # Joined only through the plan's topology: the plan says it is reached.
        plant_structure(cid, {"key": "harbour_district", "name": "Harbour District"}, {
            "slip": {"name": "Slip", "adjacent": [{"to": "quay", "barrier": "open"}]}})
        scene["rooms"]["slip"] = {"name": "Slip", "region": "harbour_district", "adjacent": []}
        assert room_pieces(cid, scene) == []
        # An inside is a fact about its holder, never a piece of anything.
        scene["rooms"]["hold"] = {"name": "Hold", "parent_entity": "barge", "adjacent": []}
        scene["positions"]["barge"] = "quay"
        assert room_pieces(cid, scene) == []


# ---------------------------------------------------------------------------
# A scene with no regions is exactly as it was
# ---------------------------------------------------------------------------

class TestNoRegions:
    def _scene(self):
        return {"location": "Shelter", "rooms": {
            "lift_car": {"name": "Lift Car", "desc": "Steel.", "parent_entity": "elevator",
                         "adjacent": []},
            "shaft": {"name": "Shaft", "adjacent": [{"to": "corridor", "barrier": "open_door"}]},
            "corridor": {"name": "Corridor",
                         "adjacent": [{"to": "shaft", "barrier": "open_door"},
                                      {"to": "lobby", "barrier": "open_door"}]},
            "lobby": {"name": "Lobby", "adjacent": [{"to": "corridor", "barrier": "open_door"},
                                                    {"to": "vault", "barrier": "locked_door"}]},
            "vault": {"name": "Vault", "adjacent": [{"to": "lobby", "barrier": "locked_door"}]},
        }, "entities": {"elevator": {"name": "the elevator", "kind": "vehicle"}},
            "positions": {PLAYER: "lift_car", "elevator": "shaft"}, "attire": {}}

    def test_the_index_is_ordered_as_before_and_every_region_is_none(self, temp_db):
        cid = _chat(temp_db)
        rows = room_index(cid, None, self._scene())
        assert all(r["region"] is None for r in rows)
        assert [r["id"] for r in rows] == sorted(
            (r["id"] for r in rows),
            key=lambda rid: (next(r["hops"] is None for r in rows if r["id"] == rid),
                             next(r["hops"] or 0 for r in rows if r["id"] == rid), rid))
        assert [r["id"] for r in rows] == ["lift_car", "shaft", "corridor", "lobby", "vault"]

    def test_the_slice_the_pieces_and_the_commit_say_nothing(self, temp_db):
        cid = _chat(temp_db)
        scene = self._scene()
        row = room_slice(cid, None, "corridor", scene)
        assert (row["region"], row["region_name"]) == (None, None)
        assert room_pieces(cid, scene) == []
        untouched = copy.deepcopy(scene)
        assert assign_regions(scene, structures={}, minted={"corridor"},
                              occupied={"lobby"}) == {"assigned": [], "registry": {},
                                                      "dropped": []}
        assert scene == untouched
        ctx, prepared = _resolve(cid, scene, {
            "rooms": {"annex": {"name": "Annex", "adjacent": [{"to": "lobby", "barrier": "open"}]}}})
        assert prepared["regions"] == {}
        assert not any("region" in r for r in prepared["scene"]["rooms"].values())
        assert not any("region" in w for w in ctx.warnings)


# ---------------------------------------------------------------------------
# The one-shot migration
# ---------------------------------------------------------------------------

class TestBackfill:
    def _legacy(self, temp_db):
        """A story from before the field: a planned room in the scene without
        its region, a zoned room, rooms reachable from those, and an island."""
        cid = _chat(temp_db)
        _plant_harbour(cid)
        scene = {"location": "Harbour", "rooms": {
            "quay": {"name": "Quay", "adjacent": [{"to": "warehouse", "barrier": "open"},
                                                   {"to": "lane", "barrier": "open"}]},
            "warehouse": {"name": "Warehouse", "adjacent": [{"to": "quay", "barrier": "open"}]},
            "lane": {"name": "Lane", "adjacent": [{"to": "quay", "barrier": "open"},
                                                   {"to": "yard", "barrier": "closed_door"}]},
            "yard": {"name": "Yard", "adjacent": [{"to": "lane", "barrier": "closed_door"}]},
            "bridge": {"name": "Bridge", "zone": "Starship Beta",
                       "adjacent": [{"to": "galley", "barrier": "open_door"}]},
            "galley": {"name": "Galley", "adjacent": [{"to": "bridge", "barrier": "open_door"}]},
            "island": {"name": "Island", "adjacent": []},
            "hold": {"name": "Hold", "parent_entity": "barge", "adjacent": []},
        }, "positions": {PLAYER: "quay", "barge": "quay"},
            "entities": {"barge": {"name": "barge", "kind": "vehicle"}}, "attire": {}}
        temp_db.wset(cid, "scene", scene)
        return cid

    def test_planned_by_structure_zones_folded_the_rest_inherited_the_island_empty(self, temp_db):
        import sqlite3
        cid = self._legacy(temp_db)
        temp_db.close_connection()
        c = sqlite3.connect(temp_db.DB)
        c.row_factory = sqlite3.Row
        counts = backfill_regions(c)
        c.commit()
        c.close()
        assert counts == {"scenes": 1, "rooms": 8, "regioned": 7, "empty": 1}
        scene = temp_db.wget(cid, "scene")
        regions = {rid: r.get("region") for rid, r in scene["rooms"].items()}
        assert regions == {
            "quay": "harbour_district", "warehouse": "harbour_district",
            "lane": "harbour_district", "yard": "harbour_district",
            "bridge": "starship_beta", "galley": "starship_beta",
            "island": None, "hold": None}
        assert room_region(scene, "hold") == "harbour_district"
        assert temp_db.wget(cid, REGIONS_KEY)["items"] == {
            "starship_beta": {"name": "Starship Beta", "brief": ""}}

    def test_init_runs_it_on_the_version_bump_and_never_again(self, temp_db):
        from core import db
        cid = self._legacy(temp_db)
        db.qi("INSERT INTO schema_meta(key,value) VALUES('version','35') "
              "ON CONFLICT(key) DO UPDATE SET value=excluded.value")
        db.close_connection()
        db.init()
        assert temp_db.wget(cid, "scene")["rooms"]["yard"]["region"] == "harbour_district"
        assert int(db.q("SELECT value FROM schema_meta WHERE key='version'",
                        one=True)["value"]) == db.SCHEMA_VERSION
        # Past the bump, a room standing without a region is left alone.
        scene = temp_db.wget(cid, "scene")
        scene["rooms"]["island"]["adjacent"] = [{"to": "quay", "barrier": "open"}]
        temp_db.wset(cid, "scene", scene)
        db.close_connection()
        db.init()
        assert "region" not in temp_db.wget(cid, "scene")["rooms"]["island"]


# ---------------------------------------------------------------------------
# The prompt says the class, in both packs
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lang", ["en", "ja"])
def test_the_spatial_hand_is_told_the_class_in_one_sentence(lang):
    import os
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "language_packs", lang, "cards", "system_prompts", "specialists",
                        "spatial", "chunks", "rooms.txt")
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    assert text.count("`region`") == 2, "one sentence: set it, or leave it unset"
    assert "region?" in text.split("\n")[-2] or "region?" in text
