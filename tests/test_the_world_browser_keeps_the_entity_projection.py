"""A thing created, edited or deleted in the World Browser is created, edited
or deleted in `world_entities` too.

Audit 2026-11-01 (web_routes_extensions F4 and persist_scene_entities F3,
CONFIRMED): `_write_scene` reconciled the `room_registry` projection and
never the `world_entities` one, so a thing deleted on the map kept its row
forever (a "must not exist" fixed point on it stayed violated, since paradox
reads row presence), a thing created there had none until some beat's diff
happened to name it, and an edited `kind` or `name` stayed on the old value.
Measured read-only on the play database the same day: 85 of 1,208 scene
entities across 25 chats had no row. The table is a projection of the scene
blob (AGENTS.md Phase 3a: every scene writer owes the pair), and it is
chat-global while a scene is one era's, so a write touches exactly the
records it changed -- never a row it did not.
"""

from __future__ import annotations

from tests.test_world_routes import client, story  # noqa: F401 - fixtures


def _row(db, cid, entity_id):
    return db.q("SELECT kind, name, payload FROM world_entities "
                "WHERE chat_id=? AND entity_id=?", (cid, entity_id), one=True)


def test_create_edit_and_delete_keep_the_row_in_step_with_the_blob(
        client, story, temp_db):
    cid = story["chat_id"]
    made = client.post(f"/api/chats/{cid}/rooms/kitchen/entities",
                       json={"name": "Coil of rope", "kind": "tool",
                             "description": "hemp, thirty feet"})
    assert made.status_code == 200, made.text
    eid = made.json()["id"]

    row = _row(temp_db, cid, eid)
    assert row is not None
    assert (row["kind"], row["name"]) == ("tool", "Coil of rope")

    edited = client.patch(f"/api/chats/{cid}/rooms/kitchen/entities/{eid}",
                          json={"kind": "climbing gear",
                                "description": "knotted every yard"})
    assert edited.status_code == 200, edited.text
    row = _row(temp_db, cid, eid)
    assert row["kind"] == "climbing gear"
    assert "knotted every yard" in row["payload"]

    gone = client.delete(f"/api/chats/{cid}/rooms/kitchen/entities/{eid}")
    assert gone.status_code == 200, gone.text
    assert _row(temp_db, cid, eid) is None


def test_a_write_touches_no_row_it_did_not_change(client, story, temp_db):
    cid = story["chat_id"]
    # The fixture's scene holds `tardis` and `oak_table` with no rows; an
    # unrelated edit is not the place to project them (another era's scene
    # may hold the same ids).
    made = client.post(f"/api/chats/{cid}/rooms/kitchen/entities",
                       json={"name": "Lantern"})
    assert made.status_code == 200, made.text

    assert _row(temp_db, cid, "tardis") is None
    assert _row(temp_db, cid, "oak_table") is None
