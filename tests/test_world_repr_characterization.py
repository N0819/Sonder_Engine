"""Characterization suite for the physical-world representations
(movement/space Phase 3a consolidation safety net).

Pins the CURRENT observable behavior of every spatial reader and of the
persistence round-trips, as golden assertions, so the Phase-3a
single-source-of-truth consolidation can prove itself behavior-preserving:

- pure spatial readers over the scene blob: `spatial_rel`,
  `visible_adjacent_rooms`, `nearby_rooms`, `room_of`, `character_room`,
  `hear_level`, `ambient_scope`, `containment_chain` (these are the whole
  deterministic substrate perception's room views are built from);
- `merge_scene_with_diff` (room-edge-preserving merges, removals,
  derived dock edges);
- commit's scene write: the persisted blob is byte-identical to the
  prepared scene, and the room_registry / world_entities projections are
  written beside it in the same commit;
- persistence round-trips: checkpoint snapshot -> restore is
  byte-identical on the full world dump; export -> import and branch
  reproduce the same canonical world modulo the documented id remaps
  (entity ids regenerated on branch, book/turn ids renumbered).

Every assertion here was captured against the pre-consolidation code and
must stay green, unchanged, through the consolidation. If one of these
expectations has to change, that is a behavior delta to report, not to
silently absorb.
"""

from __future__ import annotations

import copy
import json
import time

import commit
from agents.common import character_room
from checkpoints import ensure_checkpoint, restore_checkpoint
from pipeline_context import ChatData, PipelineContext, TurnData
from spatial import (
    ambient_scope,
    containment_chain,
    hear_level,
    merge_scene_with_diff,
    nearby_rooms,
    room_of,
    spatial_rel,
    visible_adjacent_rooms,
)

# ---------------------------------------------------------------------------
# Fixture scene: a manor plus a docked vehicle with two interior rooms.
# ---------------------------------------------------------------------------

def _scene():
    return {
        "location": "Old Manor", "time": "evening", "description": "d",
        "rooms": {
            "kitchen": {"name": "Kitchen", "desc": "A rustic kitchen.",
                        "notes": "Warm fireplace.",
                        "adjacent": [
                            {"to": "hallway", "barrier": "open", "distance": "near"},
                            {"to": "cellar", "barrier": "closed_door", "distance": "near"},
                        ]},
            "hallway": {"name": "Hallway", "desc": "A dim hallway.",
                        "notes": "Dusty portraits.",
                        "adjacent": [
                            {"to": "study", "barrier": "closed_door", "distance": "near"},
                        ]},
            "study": {"name": "Study", "desc": "A cluttered study.",
                      "notes": "Old paper.",
                      "adjacent": [
                          {"to": "hallway", "barrier": "closed_door", "distance": "near"},
                      ]},
            "cellar": {"name": "Cellar", "desc": "A damp cellar.", "notes": "Musty.",
                       "adjacent": [
                           {"to": "kitchen", "barrier": "closed_door", "distance": "near"},
                       ]},
            "garden": {"name": "Garden", "desc": "Overgrown.", "notes": "Night air.",
                       "adjacent": [
                           # Alias vocabulary on purpose: normalized on merge,
                           # tolerated raw by every reader.
                           {"to": "kitchen", "barrier": "archway", "distance": "near"},
                       ]},
            "bridge": {"name": "Bridge", "parent_entity": "ship_a",
                       "desc": "The ship bridge.", "notes": "Consoles.",
                       "adjacent": [
                           {"to": "cargo_hold", "barrier": "open_door", "distance": "near"},
                       ]},
            "cargo_hold": {"name": "Cargo Hold", "parent_entity": "ship_a",
                           "desc": "Crates.", "notes": "Crates.", "dock_exit": True,
                           "adjacent": [
                               {"to": "bridge", "barrier": "open_door", "distance": "near"},
                               {"to": "garden", "barrier": "open_door", "distance": "near"},
                           ]},
        },
        "positions": {
            "Alice": "kitchen", "Bob": "hallway", "The Stranger": "kitchen",
            "ship_a": "garden", "tenth_doctor": "cargo_hold",
        },
        "entities": {
            "ship_a": {"name": "The Aurora", "kind": "vehicle",
                       "aliases": ["Aurora"],
                       "interior_rooms": ["bridge", "cargo_hold"],
                       "state": {}},
        },
        "overlays": {}, "attire": {},
    }

# ---------------------------------------------------------------------------
# 1. Pure spatial readers (the deterministic substrate of perception's
#    room views): exact golden outputs.
# ---------------------------------------------------------------------------

class TestSpatialReaders:
    def test_spatial_rel_goldens(self):
        sc = _scene()
        assert spatial_rel(sc, "kitchen", "kitchen") == {
            "same_room": True, "barrier": "open", "distance": "same"}
        assert spatial_rel(sc, "kitchen", "hallway") == {
            "same_room": False, "barrier": "open", "distance": "near"}
        # Edge declared from one side only resolves in both directions.
        assert spatial_rel(sc, "hallway", "kitchen") == {
            "same_room": False, "barrier": "open", "distance": "near"}
        assert spatial_rel(sc, "kitchen", "cellar") == {
            "same_room": False, "barrier": "closed_door", "distance": "near"}
        # No connecting edge at all.
        assert spatial_rel(sc, "study", "garden") == {
            "same_room": False, "barrier": "separated", "distance": "far"}
        # Missing room.
        assert spatial_rel(sc, None, "kitchen") == {
            "same_room": False, "barrier": "unknown", "distance": "remote",
            "note": "no known spatial channel between these entities"}
        # Raw alias barrier ("archway") normalizes to open on read.
        assert spatial_rel(sc, "garden", "kitchen") == {
            "same_room": False, "barrier": "open", "distance": "near"}

    def test_room_of_matching_goldens(self):
        sc = _scene()
        assert room_of(sc, "Alice") == "kitchen"
        assert room_of(sc, "alice") == "kitchen"          # case-insensitive
        assert room_of(sc, "ALICE!") == "kitchen"         # alnum-normalized
        assert room_of(sc, "nobody") is None

    def test_character_room_resolves_uid_and_alias(self):
        sc = _scene()
        sheet = {"identity": {"name": "The Doctor", "uid": "tenth_doctor",
                              "aliases": ["the Doctor"]}}
        assert character_room(sc, sheet) == "cargo_hold"
        assert character_room(sc, {"identity": {"name": "Alice"}}) == "kitchen"
        assert character_room(sc, {"identity": {"name": "Nobody"}}) is None

    def test_nearby_rooms_hop_goldens(self):
        sc = _scene()
        assert sorted(nearby_rooms(sc, ["kitchen"], hops=1)) == [
            "cellar", "garden", "hallway", "kitchen"]
        assert sorted(nearby_rooms(sc, ["kitchen"], hops=2)) == [
            "cargo_hold", "cellar", "garden", "hallway", "kitchen", "study"]

    def test_visible_adjacent_rooms_goldens(self):
        sc = _scene()
        # Forward open edge + reverse open edge (garden's archway back in).
        assert visible_adjacent_rooms(sc, "kitchen") == [
            {"room_id": "hallway", "room_name": "Hallway", "barrier": "open",
             "description": "Dusty portraits."},
            {"room_id": "garden", "room_name": "Garden", "barrier": "open",
             "description": "Night air."},
        ]
        # Reverse visibility into a docked vehicle's open hold.
        assert visible_adjacent_rooms(sc, "garden") == [
            {"room_id": "kitchen", "room_name": "Kitchen", "barrier": "open",
             "description": "Warm fireplace."},
            {"room_id": "cargo_hold", "room_name": "Cargo Hold",
             "barrier": "open_door", "description": "Crates."},
        ]

    def test_hear_level_goldens(self):
        cases = [("open", "normal", "full"), ("open", "mutter", "fragment"),
                 ("closed_door", "normal", "fragment"),
                 ("closed_door", "shout", "full"),
                 ("wall", "shout", "fragment"), ("wall", "normal", "none")]
        for barrier, volume, expected in cases:
            rel = {"same_room": False, "barrier": barrier, "distance": "near"}
            assert hear_level(rel, volume) == expected, (barrier, volume)

    def test_ambient_scope_and_containment_goldens(self):
        sc = _scene()
        rooms, open_to_world = ambient_scope(sc, "kitchen")
        assert sorted(rooms) == ["bridge", "cargo_hold", "garden", "hallway",
                                 "kitchen"]
        assert open_to_world is True
        rooms, open_to_world = ambient_scope(sc, "bridge")
        assert sorted(rooms) == ["bridge", "cargo_hold", "garden", "hallway",
                                 "kitchen"]
        assert open_to_world is True
        assert containment_chain(sc, "bridge") == [
            {"room": "bridge", "entity": "ship_a"},
            {"room": "garden", "entity": None},
        ]

# ---------------------------------------------------------------------------
# 2. merge_scene_with_diff: golden merge results, including derived dock
#    edges (the one scene mutation every consumer must agree on).
# ---------------------------------------------------------------------------

class TestMergeSceneWithDiff:
    def test_room_merge_preserves_unmentioned_edges(self):
        diff = {
            "rooms": {
                "hallway": {"adjacent": [
                    {"to": "garden", "barrier": "open", "distance": "far"}]},
                "attic": {"name": "Attic", "desc": "Dust.", "adjacent": [
                    {"to": "hallway", "barrier": "locked door",
                     "distance": "near"}]},
            },
            "positions": {"Bob": "attic"},
            "entities": {"lantern": {"name": "Brass Lantern", "kind": "object"}},
            "remove_adjacent": [{"room": "kitchen", "to": "cellar"}],
        }
        original = _scene()
        pristine = copy.deepcopy(original)
        merged = merge_scene_with_diff(original, diff)
        # The input scene is never mutated by a merge.
        assert original == pristine
        # Redeclaring hallway with ONE edge keeps the edge it didn't mention.
        assert merged["rooms"]["hallway"]["adjacent"] == [
            {"to": "study", "barrier": "closed_door", "distance": "near"},
            {"to": "garden", "barrier": "open", "distance": "far"},
        ]
        # New room lands whole; its alias barrier is normalized.
        assert merged["rooms"]["attic"] == {
            "name": "Attic", "desc": "Dust.",
            "adjacent": [{"to": "hallway", "barrier": "closed_door",
                          "distance": "near"}],
        }
        assert merged["rooms"]["kitchen"]["adjacent"] == [
            {"to": "hallway", "barrier": "open", "distance": "near"}]
        assert merged["positions"]["Bob"] == "attic"
        assert sorted(merged["entities"]) == ["lantern", "ship_a"]

    def test_remove_entity_scrubs_positions_by_id_name_and_alias(self):
        merged = merge_scene_with_diff(_scene(), {"remove_entities": ["ship_a"]})
        assert sorted(merged["positions"]) == [
            "Alice", "Bob", "The Stranger", "tenth_doctor"]
        assert "ship_a" not in merged["entities"]

    def test_occupied_room_removal_is_refused(self):
        merged = merge_scene_with_diff(
            _scene(), {"remove_rooms": ["kitchen", "study"]})
        # kitchen is occupied (Alice) -> kept; study is empty -> removed.
        assert sorted(merged["rooms"]) == [
            "bridge", "cargo_hold", "cellar", "garden", "hallway", "kitchen"]

    def test_sealed_transit_derives_dock_edges(self):
        sc = _scene()
        sc["entities"]["ship_a"]["state"] = {
            "transit": {"phase": "sealed", "route_room": ""}}
        merged = merge_scene_with_diff(sc, {})
        # Exterior doorway severed; interior edge kept; stale reverse edge
        # from the plain world room into the interior stripped.
        assert merged["rooms"]["cargo_hold"]["adjacent"] == [
            {"to": "bridge", "barrier": "open_door", "distance": "near"}]
        assert merged["rooms"]["garden"]["adjacent"] == [
            {"to": "kitchen", "barrier": "open", "distance": "near"}]
        rooms, open_to_world = ambient_scope(merged, "bridge")
        assert sorted(rooms) == ["bridge", "cargo_hold"]
        assert open_to_world is False

# ---------------------------------------------------------------------------
# 3. Commit's scene write: blob persisted byte-identical to the prepared
#    scene, with the room_registry / world_entities projections written
#    beside it in the same commit.
# ---------------------------------------------------------------------------

def _make_chat(db, scene, *, with_ship_book=True):
    chat_id = db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Story", "", time.time()),
    )
    canon = db.qi(
        "INSERT INTO lorebooks(name,chat_id,book_type) VALUES(?,?,?)",
        ("Canon", chat_id, "general"),
    )
    db.qi("UPDATE chats SET lorebook_id=? WHERE id=?", (canon, chat_id))
    ship_book = None
    if with_ship_book:
        ship_book = db.qi(
            "INSERT INTO lorebooks(name,chat_id,book_type,anchor_entity_id,"
            "parent_id) VALUES(?,?,?,?,?)",
            ("The Aurora", chat_id, "vehicle", "ship_a", canon),
        )
    if scene is not None:
        db.wset(chat_id, "scene", scene)
    return {"chat_id": chat_id, "canon": canon, "ship_book": ship_book}


def _make_ctx(db, ids, diff, *, turn_idx=1, establish=None):
    turn_id = db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (ids["chat_id"], turn_idx, "do", time.time()),
    )
    ctx = PipelineContext(
        chat=ChatData(id=ids["chat_id"], name="Story", persona_id=None,
                      lorebook_id=ids["canon"], scenario="",
                      created=time.time()),
        turn=TurnData(id=turn_id, chat_id=ids["chat_id"], idx=turn_idx,
                      player_input="do", created=time.time()),
        cast=[], input="do",
    )
    if establish is not None:
        ctx.director_establish = establish
    else:
        ctx.director_resolve = {
            "resolved_event": "beat", "dialogue_log": [], "state_diff": diff,
        }
    return ctx


def _commit_beat(ctx):
    """The world-representation slice of commit_all, in commit_all's order."""
    prepared = commit.prepare_scene_commit(ctx)
    commit.commit_transit_sweep(ctx, 0, prepared=prepared)
    commit.commit_scene(ctx, 0, prepared=prepared)
    commit.commit_world_entities(ctx, 0, prepared=prepared)
    return prepared


def _dumps(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


class TestCommitSceneWrite:
    def test_persisted_blob_is_byte_identical_to_prepared_scene(self, temp_db):
        ids = _make_chat(temp_db, _scene())
        diff = {
            "rooms": {"attic": {"name": "Attic", "desc": "Dust.", "adjacent": [
                {"to": "hallway", "barrier": "closed_door",
                 "distance": "near"}]}},
            "positions": {"Bob": "attic"},
            "entities": {"lantern": {"name": "Brass Lantern",
                                     "kind": "object"}},
            "overlays": {"Alice": ["dusty"]},
            "attire": {"Alice": {"add": ["woolen shawl"]}},
        }
        ctx = _make_ctx(temp_db, ids, diff)
        prepared = _commit_beat(ctx)

        persisted = temp_db.wget(ids["chat_id"], "scene", None)
        assert _dumps(persisted) == _dumps(prepared["scene"])
        assert persisted["positions"]["Bob"] == "attic"
        assert persisted["rooms"]["attic"]["name"] == "Attic"
        assert persisted["overlays"]["Alice"] == ["dusty"]
        assert persisted["attire"]["Alice"]["wearing"] == ["woolen shawl"]

    def test_registry_and_entities_projections_written_with_scene(self, temp_db):
        ids = _make_chat(temp_db, _scene())
        ctx = _make_ctx(temp_db, ids, {
            "rooms": {"attic": {"name": "Attic", "desc": "Dust.",
                                "adjacent": []}},
            "entities": {"lantern": {"name": "Brass Lantern",
                                     "kind": "object"}},
        })
        _commit_beat(ctx)

        rows = {r["room_uid"]: dict(r) for r in temp_db.q(
            "SELECT * FROM room_registry WHERE chat_id=?", (ids["chat_id"],))}
        # Every live scene room registered under its owning book; all live.
        assert sorted(rows) == ["attic", "bridge", "cargo_hold", "cellar",
                                "garden", "hallway", "kitchen", "study"]
        assert all(r["retired_turn_id"] is None for r in rows.values())
        assert rows["bridge"]["owning_book_id"] == ids["ship_book"]
        assert rows["bridge"]["parent_entity"] == "ship_a"
        assert rows["attic"]["owning_book_id"] == ids["canon"]
        assert rows["attic"]["parent_entity"] is None
        assert rows["kitchen"]["name"] == "Kitchen"
        assert json.loads(rows["kitchen"]["aliases"]) == ["Kitchen", "kitchen"]

        ents = {r["entity_id"]: dict(r) for r in temp_db.q(
            "SELECT * FROM world_entities WHERE chat_id=?", (ids["chat_id"],))}
        # The diff-touched entity lands in the normalized projection.
        assert "lantern" in ents
        assert ents["lantern"]["kind"] == "object"
        assert ents["lantern"]["name"] == "Brass Lantern"
        assert ents["lantern"]["created_turn_id"] == ctx.turn.id

    def test_room_removal_retires_registry_row_and_drops_blob_room(self, temp_db):
        ids = _make_chat(temp_db, _scene())
        _commit_beat(_make_ctx(temp_db, ids, {}))          # register baseline
        ctx = _make_ctx(temp_db, ids, {"remove_rooms": ["study"]}, turn_idx=2)
        _commit_beat(ctx)

        sc = temp_db.wget(ids["chat_id"], "scene", {})
        assert "study" not in sc["rooms"]
        row = temp_db.q(
            "SELECT retired_turn_id FROM room_registry WHERE chat_id=? AND "
            "room_uid='study'", (ids["chat_id"],), one=True)
        assert row["retired_turn_id"] == ctx.turn.id

    def test_opening_establish_commit_registers_rooms_and_entities(self, temp_db):
        ids = _make_chat(temp_db, None)
        establish = {
            "location": "Old Manor", "time": "evening",
            "scene_description": "An old manor at dusk.",
            "state_diff": {
                "rooms": {
                    "kitchen": {"name": "Kitchen", "desc": "Rustic.",
                                "adjacent": []},
                    "bridge": {"name": "Bridge", "parent_entity": "ship_a",
                               "adjacent": []},
                },
                "positions": {"The Stranger": "kitchen", "ship_a": "kitchen"},
                "entities": {"ship_a": {"name": "The Aurora",
                                        "kind": "vehicle",
                                        "interior_rooms": ["bridge"],
                                        "state": {}}},
            },
        }
        ctx = _make_ctx(temp_db, ids, None, turn_idx=0, establish=establish)
        _commit_beat(ctx)

        sc = temp_db.wget(ids["chat_id"], "scene", {})
        assert sc["location"] == "Old Manor"
        assert sorted(sc["rooms"]) == ["bridge", "kitchen"]
        rows = {r["room_uid"]: dict(r) for r in temp_db.q(
            "SELECT * FROM room_registry WHERE chat_id=?", (ids["chat_id"],))}
        assert sorted(rows) == ["bridge", "kitchen"]
        assert rows["bridge"]["owning_book_id"] == ids["ship_book"]
        ents = [r["entity_id"] for r in temp_db.q(
            "SELECT entity_id FROM world_entities WHERE chat_id=?",
            (ids["chat_id"],))]
        assert ents == ["ship_a"]

# ---------------------------------------------------------------------------
# 4. Persistence round-trips.
# ---------------------------------------------------------------------------

_WORLD_TABLES = ("world_entities", "world_placements", "world_conditions",
                 "scheduled_events", "room_registry",
                 "fiction_worlds", "fiction_locations")


def _world_dump(db, chat_id):
    """Byte-comparable dump of every physical-world representation plus the
    whole world KV for one chat (same-chat comparisons: ids verbatim)."""
    dump = {"world": {
        w["key"]: json.loads(w["value"])
        for w in db.q("SELECT * FROM world WHERE chat_id=?", (chat_id,))
    }}
    for tbl in _WORLD_TABLES:
        rows = [dict(r) for r in db.q(
            f"SELECT * FROM {tbl} WHERE chat_id=?", (chat_id,))]
        for r in rows:
            r.pop("chat_id", None)
        dump[tbl] = sorted(rows, key=_dumps)
    return _dumps(dump)


def _replace_ids(obj, mapping):
    if isinstance(obj, str):
        return mapping.get(obj, obj)
    if isinstance(obj, dict):
        return {
            (mapping.get(k, k) if isinstance(k, str) else k):
                _replace_ids(v, mapping)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_replace_ids(item, mapping) for item in obj]
    return obj


def _canonical_world(db, chat_id):
    """Id-insensitive canonical form of the physical world: entity ids ->
    display names, book ids -> book names, turn ids -> turn idx. What
    export->import and branch must reproduce exactly."""
    ent_names = {}
    for r in db.q("SELECT entity_id, name FROM world_entities WHERE chat_id=?",
                  (chat_id,)):
        ent_names[r["entity_id"]] = r["name"] or r["entity_id"]
    turn_idx = {r["id"]: r["idx"] for r in db.q(
        "SELECT id, idx FROM turns WHERE chat_id=?", (chat_id,))}
    book_names = {r["id"]: r["name"] for r in db.q(
        "SELECT id, name FROM lorebooks WHERE chat_id=?", (chat_id,))}

    scene = _replace_ids(db.wget(chat_id, "scene", {}) or {}, ent_names)

    entities = sorted((
        {"name": r["name"], "kind": r["kind"], "subtype": r["subtype"],
         "payload": _replace_ids(json.loads(r["payload"] or "{}"), ent_names),
         "created_turn_idx": turn_idx.get(r["created_turn_id"]),
         "retired_turn_idx": turn_idx.get(r["retired_turn_id"])}
        for r in db.q("SELECT * FROM world_entities WHERE chat_id=?",
                      (chat_id,))), key=_dumps)
    registry = sorted((
        {"room_uid": r["room_uid"],
         "owning_book": book_names.get(r["owning_book_id"]),
         "parent_entity": ent_names.get(r["parent_entity"],
                                        r["parent_entity"]),
         "name": r["name"], "aliases": json.loads(r["aliases"] or "[]"),
         "payload": json.loads(r["payload"] or "{}"),
         "created_turn_idx": turn_idx.get(r["created_turn_id"]),
         "retired_turn_idx": turn_idx.get(r["retired_turn_id"])}
        for r in db.q("SELECT * FROM room_registry WHERE chat_id=?",
                      (chat_id,))), key=_dumps)
    def _condition_payload(raw):
        payload = _replace_ids(json.loads(raw or "{}"), ent_names)
        if isinstance(payload, dict):
            # The row's own (regenerated-on-branch) id, echoed into the
            # payload -- id-insensitive like the dropped column itself.
            payload.pop("condition_id", None)
        return payload

    conditions = sorted((
        {"subject": ent_names.get(r["subject_id"], r["subject_id"]),
         "kind": r["kind"], "started_at": r["started_at"],
         "expires_at": r["expires_at"], "next_tick": r["next_tick"],
         "payload": _condition_payload(r["payload"]),
         "active": r["active"]}
        for r in db.q("SELECT * FROM world_conditions WHERE chat_id=?",
                      (chat_id,))), key=_dumps)
    scheduled = sorted((
        {"kind": r["kind"], "due_at": r["due_at"], "status": r["status"],
         "location_id": ent_names.get(r["location_id"], r["location_id"]),
         "payload": _replace_ids(json.loads(r["payload"] or "{}"), ent_names)}
        for r in db.q("SELECT * FROM scheduled_events WHERE chat_id=?",
                      (chat_id,))), key=_dumps)
    placements = sorted((
        {"subject": ent_names.get(r["subject_id"], r["subject_id"]),
         "relation": r["relation"],
         "container": ent_names.get(r["container_id"], r["container_id"]),
         "detail": json.loads(r["detail"] or "{}")}
        for r in db.q("SELECT * FROM world_placements WHERE chat_id=?",
                      (chat_id,))), key=_dumps)

    return _dumps({"scene": scene, "world_entities": entities,
                   "room_registry": registry, "world_conditions": conditions,
                   "scheduled_events": scheduled,
                   "world_placements": placements})


def _build_rich_chat(db):
    """A chat with two committed beats: registered rooms under two books, a
    normalized entity row, a scheduled transit arrival, and a condition."""
    ids = _make_chat(db, _scene())
    db.wset(ids["chat_id"], "simulation_clock",
            {"elapsed_seconds": 100.0, "display": "now"})
    db.wset(ids["chat_id"], "lore_cache", [])
    _commit_beat(_make_ctx(db, ids, {
        "entities": {"ship_a": {"name": "The Aurora", "kind": "vehicle",
                                "aliases": ["Aurora"],
                                "interior_rooms": ["bridge", "cargo_hold"],
                                "state": {}}},
    }))
    _commit_beat(_make_ctx(db, ids, {
        "positions": {"Alice": "garden"},
        "entities": {"ship_a": {"name": "The Aurora", "kind": "vehicle",
                                "aliases": ["Aurora"],
                                "interior_rooms": ["bridge", "cargo_hold"],
                                "state": {"transit": {
                                    "phase": "in_transit", "hatch": "closed",
                                    "eta_seconds": 900,
                                    "destination_room": "garden"}}}},
        "conditions": {"storm": [{"condition_id": "storm", "subject_id": "garden",
                                  "kind": "weather",
                                  "started_at_seconds": 100.0,
                                  "expires_at_seconds": 5000.0}]},
    }, turn_idx=2))
    return ids


class TestPersistenceRoundTrips:
    def test_checkpoint_restore_is_byte_identical(self, temp_db):
        ids = _build_rich_chat(temp_db)
        cid = ids["chat_id"]
        ensure_checkpoint(cid, 3)
        before = _world_dump(temp_db, cid)

        # Mutate every representation, then restore.
        sc = temp_db.wget(cid, "scene", {})
        sc["rooms"]["shed"] = {"name": "Shed", "adjacent": []}
        sc["positions"]["Alice"] = "shed"
        del sc["rooms"]["study"]
        temp_db.wset(cid, "scene", sc)
        temp_db.qi("INSERT INTO room_registry(chat_id,room_uid,owning_book_id,"
                   "name,aliases,payload) VALUES(?,?,?,?,?,?)",
                   (cid, "shed", ids["canon"], "Shed", "[]", "{}"))
        temp_db.qi("UPDATE room_registry SET retired_turn_id="
                   "(SELECT MIN(id) FROM turns WHERE chat_id=?) "
                   "WHERE chat_id=? AND room_uid='study'", (cid, cid))
        temp_db.qi("INSERT INTO world_entities(entity_id,chat_id,kind,subtype,"
                   "name,payload) VALUES(?,?,?,?,?,?)",
                   ("crate", cid, "object", "", "Crate", "{}"))
        temp_db.qi("UPDATE scheduled_events SET status='fired' WHERE chat_id=?",
                   (cid,))
        temp_db.qi("UPDATE world_conditions SET active=0 WHERE chat_id=?",
                   (cid,))
        assert _world_dump(temp_db, cid) != before

        restore_checkpoint(cid, 3)
        assert _world_dump(temp_db, cid) == before

    def test_export_import_reproduces_canonical_world(self, temp_db):
        import app
        ids = _build_rich_chat(temp_db)
        source = _canonical_world(temp_db, ids["chat_id"])

        exported = app.chat_export(ids["chat_id"])
        exported = json.loads(json.dumps(exported))   # wire round-trip
        imported = app.chat_import({"data": exported})

        assert _canonical_world(temp_db, imported["id"]) == source
        # And the imported scene blob itself is byte-identical (import keeps
        # entity ids verbatim).
        assert _dumps(temp_db.wget(imported["id"], "scene", None)) == \
            _dumps(temp_db.wget(ids["chat_id"], "scene", None))

    def test_branch_reproduces_canonical_world(self, temp_db):
        import app
        ids = _build_rich_chat(temp_db)
        cid = ids["chat_id"]
        source = _canonical_world(temp_db, cid)
        source_raw = _world_dump(temp_db, cid)
        last_turn = temp_db.q(
            "SELECT id FROM turns WHERE chat_id=? ORDER BY idx DESC LIMIT 1",
            (cid,), one=True)

        branched = app.turn_branch(last_turn["id"])

        # Branch regenerates entity ids; the canonical (name-keyed) world
        # must survive that remap exactly.
        assert _canonical_world(temp_db, branched["id"]) == source
        # And branching must leave the source chat's world untouched.
        assert _world_dump(temp_db, cid) == source_raw
