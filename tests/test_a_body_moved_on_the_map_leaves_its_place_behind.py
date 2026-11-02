"""A body the host moves to another room on the map leaves the old room's
pose detail and what it stood on behind, as a body the Director moves does.

Audit 2026-11-01 (web_routes_extensions F10, CONFIRMED by snippet):
`PUT /bodies/{name}/room` ran only `invalidate_moved_body_pose_details` (a
detail holding ANOTHER body). The merge also runs
`invalidate_moved_body_place_details` and `release_moved_body_supports`, and
both key on a move inside ONE merge (`was != room`), so no later beat ever
saw the host's move: Wren moved from the corridor to the parlour kept
`{support: "coat_stand", detail: "standing near the coat-stand, looking down
toward the turn"}` through the next merge -- F49 and PB7 (those functions'
own measured cases) re-entered through the editor.
"""

from __future__ import annotations

from tests.test_world_routes import client, story  # noqa: F401 - fixtures


def test_moving_the_player_drops_the_place_detail_and_releases_the_support(
        client, story, temp_db):
    cid = story["chat_id"]
    scene = temp_db.wget(cid, "scene")
    scene["poses"] = {"Nathan": {
        "posture": "standing", "support": "the study's armchair",
        "detail": "standing by the armchair, looking down at the open ledger"}}
    temp_db.wset(cid, "scene", scene)

    moved = client.put(f"/api/chats/{cid}/bodies/Nathan/room",
                       json={"room": "kitchen"})
    assert moved.status_code == 200, moved.text

    after = temp_db.wget(cid, "scene")
    assert after["positions"]["Nathan"] == "kitchen"
    pose = after["poses"]["Nathan"]
    assert pose["detail"] == ""
    assert pose["support"] == ""
    # The posture is the body's own and goes with it.
    assert pose["posture"] == "standing"


def test_a_support_that_stands_in_the_room_entered_is_kept(
        client, story, temp_db):
    cid = story["chat_id"]
    scene = temp_db.wget(cid, "scene")
    scene["entities"]["handcart"] = {"name": "Handcart", "kind": "vehicle"}
    scene["positions"]["handcart"] = "kitchen"
    scene["poses"] = {"Nathan": {"posture": "sitting", "support": "handcart",
                                 "detail": ""}}
    temp_db.wset(cid, "scene", scene)

    moved = client.put(f"/api/chats/{cid}/bodies/Nathan/room",
                       json={"room": "kitchen"})
    assert moved.status_code == 200, moved.text

    assert temp_db.wget(cid, "scene")["poses"]["Nathan"]["support"] == "handcart"
