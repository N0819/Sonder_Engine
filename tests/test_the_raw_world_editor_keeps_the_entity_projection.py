"""The Raw JSON world editor keeps `world_entities` in step with the scene it writes.

`world_entities` is a projection of the scene's `entities` blob, and AGENTS.md
asks every scene writer to keep both projections -- `room_registry` and this
one. `world_put` reconciled the registry and never this table, so a thing
deleted in the editor kept its row (paradox reads ROW PRESENCE for a fixed
point), a thing created there had none, and an edited kind stayed on the old
value (audit 2026-11-01, web_routes_extensions F4 / persist_scene_entities F3:
85 of 1,208 scene entities across 25 chats had no row on the play database).

And the scenes it reconciles against are read INSIDE the transaction that
rewrites them: read before it, a write landing between the two was
reconciled against a scene that no longer existed.
"""
from __future__ import annotations

import time


def _rows(db, cid):
    return {r["entity_id"]: (r["kind"], r["name"])
            for r in db.q("SELECT entity_id,kind,name FROM world_entities WHERE chat_id=?",
                          (cid,))}


def test_a_scene_written_by_hand_moves_the_entity_rows_with_it(temp_db):
    from web import app

    db = temp_db
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Story", "", time.time()))
    scene = {"location": "Hall", "rooms": {"hall": {"name": "Hall"}}, "positions": {},
             "entities": {"lamp": {"kind": "object", "name": "brass lamp"},
                          "chest": {"kind": "object", "name": "oak chest"}}}
    app.world_put(cid, {"scene": scene})
    assert _rows(db, cid) == {"lamp": ("object", "brass lamp"),
                              "chest": ("object", "oak chest")}

    edited = {**scene, "entities": {"lamp": {"kind": "fixture", "name": "brass lamp"},
                                    "rope": {"kind": "object", "name": "coil of rope"}}}
    app.world_put(cid, {"scene": edited})
    assert _rows(db, cid) == {"lamp": ("fixture", "brass lamp"),
                              "rope": ("object", "coil of rope")}


def test_the_scenes_are_read_inside_the_rewrite():
    import inspect
    from web import app

    source = inspect.getsource(app.world_put)
    assert source.index("with transaction():") < source.index("old_scenes = {")
