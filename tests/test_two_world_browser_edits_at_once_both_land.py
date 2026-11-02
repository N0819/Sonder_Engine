"""Two World Browser edits made at once both land, and the room registry
still agrees with the scene.

Audit 2026-11-01 (web_routes_extensions F5): every write route read the scene
OUTSIDE any transaction and opened one only around the write, so two edits
that read the same scene -- two tabs, the map's arrow keys firing a write per
keydown without awaiting the last, the threadpool running `def` routes side
by side -- each wrote their own copy and the second erased the first. Worse
than a lost edit: `sync_room_registry_with_scene` diffed against the second
writer's stale `before`, so a room the first write minted was in neither
side of the second's diff and stayed LIVE in `room_registry` while the scene
no longer held it -- the "hand-removed rooms live in the registry forever"
case that function exists to prevent. The read now happens inside the same
`transaction()` (BEGIN IMMEDIATE) as the write.
"""

from __future__ import annotations

import threading

from tests.test_world_routes import story  # noqa: F401 - fixture


def test_two_rooms_created_at_once_are_both_in_the_scene_and_the_registry(
        story, temp_db, monkeypatch):
    from web import world_routes

    cid = story["chat_id"]
    real = world_routes.get_scene
    # Both readers meet here when nothing serialises them; when the read is
    # inside the write's transaction the second never arrives, and the first
    # goes on alone once the wait runs out.
    meet = threading.Barrier(2, timeout=1.5)

    def get_scene_and_wait(cid_, chat=None):
        scene = real(cid_, chat)
        try:
            meet.wait()
        except threading.BrokenBarrierError:
            pass
        return scene

    monkeypatch.setattr(world_routes, "get_scene", get_scene_and_wait)
    errors = []

    def create(name):
        try:
            world_routes.room_create(cid, {"name": name})
        except Exception as exc:  # noqa: BLE001 - reported below
            errors.append(exc)

    threads = [threading.Thread(target=create, args=(name,))
               for name in ("Pantry", "Larder")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)

    assert not errors
    scene = temp_db.wget(cid, "scene")
    assert {"pantry", "larder"} <= set(scene["rooms"])
    live = {row["room_uid"] for row in temp_db.q(
        "SELECT room_uid FROM room_registry WHERE chat_id=? "
        "AND retired_turn_id IS NULL", (cid,))}
    assert {"pantry", "larder"} <= live
    # The registry holds no live room the scene does not, beyond the ones
    # the plan alone holds (the fixture's attic and crypt).
    assert live - set(scene["rooms"]) <= {"attic", "crypt"}
