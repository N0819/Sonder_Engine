"""A character the host moves from the cast editor leaves the old room's pose
detail, its support, and every other body's hold on it behind -- as a body
the Director moves, or one moved on the World Browser's map, does.

`PUT /api/chats/{cid}/characters/{ch}/position` writes the scene without the
merge, and ran none of the merge's three move invalidators
(`invalidate_moved_body_pose_details`, `invalidate_moved_body_place_details`,
`release_moved_body_supports`). All three key on a move INSIDE one write
(`previous_positions` against `positions`), so no later beat ever saw the
host's move: the body kept "standing by the hall's open ledger" in the
kitchen, kept standing on the hall bench, and another body's pose went on
holding it by the wrist from the room it had left (web_routes_extensions F10's
class; L2 fixed the map route, `body_room_put`).

The snapshot is re-keyed to the name the move writes: a stored key spelled
otherwise ("mara quill") read as a body that had never been anywhere.
"""
from __future__ import annotations

import json
import time


def _story(db):
    from story.character_schema import default_character_data
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Story", "", time.time()))
    ch = db.qi("INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
               ("Mara Quill", json.dumps(default_character_data("Mara Quill")), "{}",
                time.time()))
    db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
          (cid, ch, "active", "{}"))
    db.wset(cid, "scene", {
        "location": "Hall",
        "rooms": {"hall": {"name": "Hall"}, "kitchen": {"name": "Kitchen"}},
        # stored under another spelling of her name, as `room_of` tolerates
        "positions": {"mara quill": "hall", "Bram": "hall"},
        "poses": {
            "Mara Quill": {"posture": "standing", "support": "the hall bench",
                           "detail": "standing by the hall's open ledger"},
            "Bram": {"posture": "standing", "support": "",
                     "detail": "holding Mara Quill by the wrist"},
        },
    })
    return cid, ch


def test_the_move_retires_what_the_old_room_held(temp_db):
    from web import app

    cid, ch = _story(temp_db)
    assert app.chat_char_position_put(cid, ch, {"room": "kitchen"}) == {
        "ok": True, "name": "Mara Quill", "room": "kitchen"}

    scene = temp_db.wget(cid, "scene")
    assert scene["positions"] == {"Mara Quill": "kitchen", "Bram": "hall"}
    mara = scene["poses"]["Mara Quill"]
    assert mara["detail"] == "" and mara["support"] == ""
    assert mara["posture"] == "standing", "the posture is hers and goes with her"
    assert scene["poses"]["Bram"]["detail"] == ""


def test_a_move_to_the_room_she_is_in_retires_nothing(temp_db):
    from web import app

    cid, ch = _story(temp_db)
    app.chat_char_position_put(cid, ch, {"room": "hall"})
    scene = temp_db.wget(cid, "scene")
    assert scene["poses"]["Mara Quill"]["detail"] == "standing by the hall's open ledger"
    assert scene["poses"]["Bram"]["detail"] == "holding Mara Quill by the wrist"
