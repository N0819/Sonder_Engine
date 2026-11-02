"""An archive moved to another install keeps every character id it holds.

`characters.id` is the INSTALL's integer. An import re-creates each character
under whatever id the importing install hands out, and every place the old
number is stored must be rewritten through the import's map -- or it names
whoever holds that number here. Measured (audit 2026-11-01, persistence F3):
Mora was character 1 at the source and 6 after the import, her stance graph
stayed under the world key `relationships:1`, and `get_relationships(.., 6)`
read nothing about Hal while the remapped ledger still held why she distrusts
him. The same class held a Charter body's binding and seat token, a couple
map's cast and the keyed history records, in the live world and in every
checkpoint the archive carried.

The rule: one table names every place a character's row id lives in world
state (`chat_archive.remap_world_character_ids`), and both the live world and
each checkpoint go through it; an id that does not map is DROPPED, never kept,
because the same number means a different person here.
"""

from __future__ import annotations

import json
import time

from tests.helpers import remove_scratch_db, scratch_db_path


def _char(db, name, uid):
    return db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        (name, json.dumps({"identity": {"name": name}}), "{}", time.time(), uid))


def _source_story(db):
    """Install A: Mora (id 1) with a stance, a Charter binding, a couple map
    and a keyed history record; a checkpoint holding the same world."""
    from core.db import wset
    from mind.memory import apply_relationship_updates
    from persist.checkpoints import ensure_checkpoint

    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Mill", "", time.time()))
    mora = _char(db, "Mora", "uid_mora")
    db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
          "VALUES(?,?,'active','{}')", (cid, mora))
    left = db.qi("INSERT INTO frames(chat_id,label,ordinal,kind,created) "
                 "VALUES(?,?,?,?,?)", (cid, "Left", 1, "spatial", time.time()))
    right = db.qi("INSERT INTO frames(chat_id,label,ordinal,kind,created) "
                  "VALUES(?,?,?,?,?)", (cid, "Right", 2, "spatial", time.time()))
    call = db.qi("INSERT INTO frames(chat_id,label,ordinal,kind,created) "
                 "VALUES(?,?,?,?,?)", (cid, "Call", 3, "couple", time.time()))
    apply_relationship_updates(cid, mora, 3, [{
        "target_entity": "Hal", "trust_delta": -0.4,
        "trigger_event_ids": ["ev:x"], "reason": "he lied about the sacks"}])
    # A number no character in the archive answers to: a stance that must
    # not land on whoever holds 99 in the importing install.
    wset(cid, "relationships:99", {"Hal": {"target_name": "Hal", "trust": 0.9}})
    wset(cid, "charters", {"items": {"inn": {"state": {
        "bodies": {"b1": {"name": "Mora", "resident_seed_id": f"character:{mora}"}},
        "bindings": {"b1": {"char_id": mora, "entity_id": "", "name": "Mora",
                            "promoted_turn": 0}}}}}})
    wset(cid, "character_history_routes", {str(mora): {
        "mode": "charter", "seed_id": f"character:{mora}"}})
    wset(cid, f"couple:{call}", {
        "members": [left, right], "home": left, "personas": {},
        "cast": {"a": [mora, 99], "b": []}})
    db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
          (cid, 0, "begin", time.time()))
    ensure_checkpoint(cid, 1)
    return cid, mora


def _held_ids(world, new_mora):
    """What the imported world says about Mora, by the five spellings."""
    relationships = sorted(k for k in world if k.startswith("relationships:"))
    charter = world["charters"]["items"]["inn"]["state"]
    couple = next(v for k, v in world.items() if k.startswith("couple:"))
    return {
        "relationships": relationships,
        "binding": charter["bindings"]["b1"]["char_id"],
        "seat": charter["bodies"]["b1"]["resident_seed_id"],
        "routes": sorted(world["character_history_routes"]),
        "route_seed": world["character_history_routes"].get(str(new_mora), {}).get("seed_id"),
        "cast": couple["cast"],
    }


def test_an_import_rekeys_every_character_id_in_the_world_and_its_checkpoints(temp_db):
    from core import db
    from mind.memory import get_relationships
    from web import app

    cid, mora = _source_story(temp_db)
    archive = json.loads(json.dumps(app.chat_export(cid)))

    other = scratch_db_path()
    try:
        db.configure(other)
        db.init()
        # The importing install already holds characters, so Mora's id moves.
        for i in range(5):
            _char(db, f"Other {i}", f"uid_other_{i}")
        new_cid = app.chat_import({"data": archive})["id"]
        new_mora = db.q("SELECT char_id FROM chat_chars WHERE chat_id=?",
                        (new_cid,), one=True)["char_id"]
        assert new_mora != mora, "the fixture must move the id to mean anything"

        live = {r["key"]: json.loads(r["value"]) for r in db.q(
            "SELECT key, value FROM world WHERE chat_id=?", (new_cid,))}
        expected = {
            "relationships": [f"relationships:{new_mora}"],
            "binding": new_mora,
            "seat": f"character:{new_mora}",
            "routes": [str(new_mora)],
            "route_seed": f"character:{new_mora}",
            "cast": {"a": [new_mora], "b": []},
        }
        assert _held_ids(live, new_mora) == expected
        assert get_relationships(new_cid, new_mora).get("Hal") is not None, (
            "the stance graph is read back under the character's new id")

        blob = json.loads(db.q("SELECT blob FROM checkpoints WHERE chat_id=? "
                               "AND turn_idx=1", (new_cid,), one=True)["blob"])
        assert _held_ids(blob["world"], new_mora) == expected, (
            "a checkpoint is restored whole, so it must say the same")
    finally:
        db.close_connection()
        remove_scratch_db(other)


def test_the_table_drops_an_unmapped_id_wherever_it_sits_and_leaves_what_is_no_id():
    from persist.chat_archive import remap_world_character_ids

    world = {
        "greeting_minds": {"minds": {"mora": {"resolved": "character:1"},
                                     "player": {"resolved": "player"}}},
        "plans": [{"char_id": 1, "goal": "the mill"},
                  {"char_id": -1, "goal": "a sentinel is no id"},
                  {"char_id": 2, "goal": "a stranger's"}],
        "featured": {"character:1": {"post": "miller"}, "character:2": {"post": "?"}},
        "targets": ["character:1", "character:2", "character:player", "the miller"],
    }
    remap_world_character_ids(world, {1: 6})
    assert world["greeting_minds"]["minds"]["mora"]["resolved"] == "character:6"
    assert world["greeting_minds"]["minds"]["player"]["resolved"] == "player"
    assert [p["char_id"] for p in world["plans"]] == [6, -1, None]
    assert world["featured"] == {"character:6": {"post": "miller"}}
    assert world["targets"] == ["character:6", "character:player", "the miller"]


def test_a_same_install_branch_passes_no_map_and_nothing_moves():
    from persist.chat_archive import remap_world_character_ids

    world = {"relationships:1": {"Hal": {}}, "x": {"char_id": 1}}
    assert remap_world_character_ids(world, None) == {
        "relationships:1": {"Hal": {}}, "x": {"char_id": 1}}
