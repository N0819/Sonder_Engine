"""A doorway's description, edited in the World Browser, is written -- onto
the passage record and both edges -- and clearing it removes it.

Audit 2026-11-01 (web_routes_extensions F14, CONFIRMED by snippet):
`DOORWAY_FIELDS` has accepted `desc` since 4e4d102e (the owner's 2026-10-12
ask: "doors should have a description and material type field") and the
browser sends it, but `_apply_doorway_fields` wrote only `name` and
`material`: a PATCH of `{desc, material}` saved the material, answered
"Saved.", and re-rendered the old text. `desc` is one of the passage's own
fields (`spatial_barriers.PASSAGE_FIELDS`), so it is the doorway's ONE answer
from either room.
"""

from __future__ import annotations

from tests.test_world_routes import client, story  # noqa: F401 - fixtures


def _doorway(scene, here, to):
    edge = next(e for e in scene["rooms"][here]["adjacent"]
                if e.get("to") == to)
    back = next(e for e in scene["rooms"][to]["adjacent"]
                if e.get("to") == here)
    record = scene.get("passages", {}).get(edge.get("passage"), {})
    return record, edge, back


def test_a_description_lands_on_the_record_and_both_edges(client, story,
                                                          temp_db):
    cid = story["chat_id"]
    patched = client.patch(f"/api/chats/{cid}/doorways/kitchen/hallway",
                           json={"desc": "a low arch of old brick",
                                 "material": "brick"})
    assert patched.status_code == 200, patched.text

    record, edge, back = _doorway(temp_db.wget(cid, "scene"), "kitchen", "hallway")
    assert record["desc"] == "a low arch of old brick"
    assert edge["desc"] == back["desc"] == "a low arch of old brick"
    assert record["material"] == "brick"

    grid = client.get(f"/api/chats/{cid}/rooms/kitchen/grid").json()
    door = next(d for d in grid["doorways"] if d["to"] == "hallway")
    assert door["desc"] == "a low arch of old brick"


def test_clearing_the_description_removes_it_everywhere(client, story, temp_db):
    cid = story["chat_id"]
    assert client.patch(f"/api/chats/{cid}/doorways/kitchen/hallway",
                        json={"desc": "a low arch"}).status_code == 200
    cleared = client.patch(f"/api/chats/{cid}/doorways/hallway/kitchen",
                           json={"desc": ""})
    assert cleared.status_code == 200, cleared.text

    record, edge, back = _doorway(temp_db.wget(cid, "scene"), "kitchen", "hallway")
    assert "desc" not in record
    assert "desc" not in edge and "desc" not in back
