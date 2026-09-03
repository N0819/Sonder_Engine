"""The Writers' Room panel's backend: the thread, the seam, the two typed
rows beside the chat, and where the conversation travels.

`story/room_conversation.py` holds the contract; `web/room_routes.py` is
transport over it. The conversation is author-side state: a branch and an
archive carry it, a turn checkpoint does not, and a deleted story takes it
along. Until the Story Planner is seated the reply is one honest line, and
the panel is told nobody is seated so it never dresses the placeholder as an
agent.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from core.db import FRAME_SCOPED_WORLD_KEYS, wget_for_frame, wset_for_frame
from persist.checkpoints import restore_checkpoint, snapshot_state
from story import room_conversation as room
from web import app as app_module
from web import guest_access as guest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def client(temp_db):
    guest.reset_host_account()
    guest._join_attempts.clear()
    guest._login_attempts.clear()
    with TestClient(app_module.app) as c:
        r = c.post("/api/auth/setup",
                   json={"username": "host", "password": "pw12345"})
        assert r.status_code == 200, r.text
        yield c
    guest.reset_host_account()
    guest._join_attempts.clear()
    guest._login_attempts.clear()


@pytest.fixture
def unseated():
    """Every test starts and ends with nobody seated."""
    room.seat_planner(None)
    yield
    room.seat_planner(None)


def _chat(db, name="Room"):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 (name, "", time.time()))


def _frame(db, cid, label="Elsewhen"):
    return db.qi(
        "INSERT INTO frames(chat_id,label,ordinal,kind,created) "
        "VALUES(?,?,?,?,?)", (cid, label, 1, "past", time.time()))


def _turn(db, cid, idx, frame_id=None):
    return db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) "
        "VALUES(?,?,?,?,?)", (cid, idx, "wait", time.time(), frame_id))


# ---- the thread and the placeholder --------------------------------------

def test_the_placeholder_keeps_the_note_and_says_nobody_is_seated(client, temp_db, unseated):
    cid = _chat(temp_db)
    empty = client.get(f"/api/chats/{cid}/room").json()
    assert empty["messages"] == [] and empty["seated"] is False
    assert empty["page"] == room.ROOM_PAGE
    assert empty["message_chars"] == room.ROOM_MESSAGE_CHARS

    r = client.post(f"/api/chats/{cid}/room/messages",
                    json={"text": "  Prepare the harbour, quietly.  "})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["message"]["role"] == "player"
    assert out["message"]["text"] == "Prepare the harbour, quietly."
    (reply,) = out["replies"]
    # A `room` notice, never a `planner` line: nobody is seated.
    assert reply["role"] == "room" and reply["text"] == room.UNSEATED_LINE
    assert out["seated"] is False and out["error"] is None

    thread = client.get(f"/api/chats/{cid}/room").json()
    assert [m["role"] for m in thread["messages"]] == ["player", "room"]


def test_the_unseated_line_is_in_the_ui_catalog_and_the_panel_script(unseated):
    """The placeholder's line reaches a reader through the UI catalog, so
    the same English literal must be in `writers_room.js` (the harvester's
    source) and in the English catalog; a drift between the two spellings
    would ship an untranslated line."""
    catalog = json.loads((ROOT / "language_packs" / "en" / "ui.json").read_text())
    assert room.UNSEATED_LINE in catalog
    script = (ROOT / "static" / "js" / "writers_room.js").read_text()
    assert room.UNSEATED_LINE in script
    ja = json.loads((ROOT / "language_packs" / "ja" / "ui.json").read_text())
    assert ja.get(room.UNSEATED_LINE) not in (None, room.UNSEATED_LINE)


def test_an_empty_or_overlong_note_is_refused(client, temp_db, unseated):
    cid = _chat(temp_db)
    assert client.post(f"/api/chats/{cid}/room/messages",
                       json={"text": "   "}).status_code == 400
    r = client.post(f"/api/chats/{cid}/room/messages",
                    json={"text": "x" * (room.ROOM_MESSAGE_CHARS + 1)})
    assert r.status_code == 400
    assert client.get(f"/api/chats/{cid}/room").json()["messages"] == []


def test_the_thread_is_per_story_and_per_era(client, temp_db, unseated):
    cid, other = _chat(temp_db), _chat(temp_db, "Other")
    fid = _frame(temp_db, cid)
    client.post(f"/api/chats/{cid}/room/messages", json={"text": "now"})
    client.post(f"/api/chats/{cid}/room/messages",
                json={"text": "then", "frame_id": fid})
    present = client.get(f"/api/chats/{cid}/room").json()["messages"]
    past = client.get(f"/api/chats/{cid}/room",
                      params={"frame_id": fid}).json()["messages"]
    assert [m["text"] for m in present if m["role"] == "player"] == ["now"]
    assert [m["text"] for m in past if m["role"] == "player"] == ["then"]
    assert client.get(f"/api/chats/{other}/room").json()["messages"] == []
    # A frame of another story, or none at all, is not this story's era.
    assert client.get(f"/api/chats/{other}/room",
                      params={"frame_id": fid}).status_code == 404
    assert client.get(f"/api/chats/{cid}/room",
                      params={"frame_id": 999}).status_code == 404
    assert client.get("/api/chats/999/room").status_code == 404


def test_the_thread_keeps_its_tail_and_pages_back(temp_db, unseated):
    cid = _chat(temp_db)
    for i in range(room.ROOM_HISTORY_KEPT + 5):
        room.add_message(cid, None, "player", f"note {i}")
    kept = temp_db.q("SELECT text FROM room_messages WHERE chat_id=? ORDER BY id", (cid,))
    assert len(kept) == room.ROOM_HISTORY_KEPT
    assert kept[0]["text"] == "note 5"
    page = room.messages(cid, None)
    assert len(page) == room.ROOM_PAGE and page[-1]["text"].endswith(
        str(room.ROOM_HISTORY_KEPT + 4))
    earlier = room.messages(cid, None, before=page[0]["id"])
    assert earlier and earlier[-1]["id"] < page[0]["id"]


def test_the_room_is_the_hosts_seat_not_a_guest_surface(temp_db):
    from web.auth_routes import GUEST_ALLOWED_API_PATHS, PUBLIC_API_PATHS
    for path in (*GUEST_ALLOWED_API_PATHS, *PUBLIC_API_PATHS):
        assert "/room" not in path


# ---- the seam -------------------------------------------------------------

def test_a_seated_planner_answers_in_its_own_voice_and_the_dramaturges(client, temp_db, unseated):
    cid = _chat(temp_db)
    seen = {}

    def planner(chat_id, frame_id, text):
        seen.update(chat_id=chat_id, frame_id=frame_id, text=text)
        return {"reply": "Noted; I will prepare two roads.",
                "dramaturge": "A storm would suit the second.",
                "mandates": [{"uid": "m1", "text": "two roads", "scope": "here"}],
                "status": {"line": "Two roads are being prepared."}}

    room.seat_planner(planner)
    out = client.post(f"/api/chats/{cid}/room/messages",
                      json={"text": "Two roads, please."}).json()
    assert seen == {"chat_id": cid, "frame_id": None, "text": "Two roads, please."}
    assert [(m["role"], m["text"]) for m in out["replies"]] == [
        ("planner", "Noted; I will prepare two roads."),
        ("dramaturge", "A storm would suit the second."),
    ]
    assert out["seated"] is True
    assert out["mandates"][0]["uid"] == "m1"
    assert out["status"]["line"] == "Two roads are being prepared."
    assert client.get(f"/api/chats/{cid}/room").json()["seated"] is True


def test_a_planner_that_fails_leaves_the_note_and_reports(client, temp_db, unseated):
    cid = _chat(temp_db)

    def broken(chat_id, frame_id, text):
        raise RuntimeError("provider down")

    room.seat_planner(broken)
    r = client.post(f"/api/chats/{cid}/room/messages", json={"text": "hello"})
    assert r.status_code == 200
    out = r.json()
    assert out["replies"] == [] and "provider down" in out["error"]
    assert [m["role"] for m in room.messages(cid, None)] == ["player"]


# ---- mandates and status ---------------------------------------------------

def test_mandates_and_status_are_frame_scoped_world_rows():
    assert room.ROOM_MANDATES_KEY in FRAME_SCOPED_WORLD_KEYS
    assert room.ROOM_STATUS_KEY in FRAME_SCOPED_WORLD_KEYS


def test_the_player_revokes_a_mandate_and_the_planner_wrote_it(client, temp_db, unseated):
    cid = _chat(temp_db)
    _turn(temp_db, cid, 0)
    _turn(temp_db, cid, 7)
    wset_for_frame(cid, room.ROOM_MANDATES_KEY, [
        {"uid": "m1", "text": "Prepare up to two settlements ahead of me.",
         "scope": "this story", "capabilities": ["plan_rooms", "plan_people"],
         "limits": {"settlements": 2}, "granted_turn": 3},
        {"uid": "m2", "text": "A storm may come.", "status": "expired",
         "granted_turn": 1, "expires_turn": 5},
        {"garbage": True},
    ], None)
    listed = client.get(f"/api/chats/{cid}/room").json()["mandates"]
    assert [m["uid"] for m in listed] == ["m1", "m2"]
    assert listed[0]["status"] == "active" and listed[0]["limits"] == {"settlements": 2}

    r = client.post(f"/api/chats/{cid}/room/mandates/m1/revoke", json={})
    assert r.status_code == 200
    assert r.json()["mandate"]["status"] == "revoked"
    assert r.json()["mandate"]["revoked_turn"] == 7
    stored = wget_for_frame(cid, room.ROOM_MANDATES_KEY, None, [])
    assert stored[0]["status"] == "revoked"
    # Revoking again changes nothing; an expired grant stays expired.
    again = client.post(f"/api/chats/{cid}/room/mandates/m1/revoke", json={}).json()
    assert again["mandate"]["revoked_turn"] == 7
    assert client.post(f"/api/chats/{cid}/room/mandates/m2/revoke",
                       json={}).json()["mandate"]["status"] == "expired"
    assert client.post(f"/api/chats/{cid}/room/mandates/nope/revoke",
                       json={}).status_code == 404


def test_the_status_row_is_normalised_on_read(client, temp_db, unseated):
    cid = _chat(temp_db)
    wset_for_frame(cid, room.ROOM_STATUS_KEY, {
        "line": "  Something is  in motion at the harbour. ",
        "in_motion": [{"uid": "p1", "kind": "plot", "label": "a matter at the harbour",
                       "state": "active"}, "junk"],
        "questions": [{"uid": "q1", "text": "May the harbour burn?"}, {"text": ""}],
        "updated_turn": "4",
    }, None)
    st = client.get(f"/api/chats/{cid}/room/status").json()
    assert st["line"] == "Something is in motion at the harbour."
    assert st["in_motion"] == [{"uid": "p1", "kind": "plot",
                                "label": "a matter at the harbour", "state": "active"}]
    assert st["questions"] == [{"uid": "q1", "text": "May the harbour burn?"}]
    assert st["updated_turn"] == 4
    assert client.get(f"/api/chats/{cid}/room/status",
                      params={"frame_id": 42}).status_code == 404


# ---- where the conversation travels -----------------------------------------

def test_a_branch_carries_the_conversation_up_to_its_point_in_its_own_eras(temp_db, unseated):
    cid = _chat(temp_db)
    fid = _frame(temp_db, cid)
    t0 = _turn(temp_db, cid, 0, fid)
    _turn(temp_db, cid, 1, fid)
    room.add_message(cid, None, "player", "before, present", turn_idx=0)
    room.add_message(cid, fid, "player", "before, elsewhen", turn_idx=0)
    room.add_message(cid, None, "player", "after", turn_idx=1)

    ncid = app_module.turn_branch(t0)["id"]
    rows = temp_db.q("SELECT frame_id, text FROM room_messages WHERE chat_id=? ORDER BY id", (ncid,))
    assert [r["text"] for r in rows] == ["before, present", "before, elsewhen"]
    new_frames = {r["id"] for r in temp_db.q("SELECT id FROM frames WHERE chat_id=?", (ncid,))}
    assert rows[0]["frame_id"] is None
    assert rows[1]["frame_id"] in new_frames and rows[1]["frame_id"] != fid
    # The source keeps every line.
    assert temp_db.q("SELECT COUNT(*) AS n FROM room_messages WHERE chat_id=?",
                     (cid,), one=True)["n"] == 3


def test_an_archive_carries_the_conversation_with_its_eras_remapped(client, temp_db, unseated):
    cid = _chat(temp_db)
    fid = _frame(temp_db, cid)
    room.add_message(cid, None, "player", "present note")
    room.add_message(cid, fid, "planner", "elsewhen answer")
    archive = client.get(f"/api/chats/{cid}/export").json()
    assert [m["text"] for m in archive["room_messages"]] == ["present note", "elsewhen answer"]
    imported = client.post("/api/chats/import", json={"data": archive}).json()
    ncid = imported["id"]
    rows = temp_db.q("SELECT frame_id, role, text FROM room_messages WHERE chat_id=? ORDER BY id", (ncid,))
    assert [(r["role"], r["text"]) for r in rows] == [
        ("player", "present note"), ("planner", "elsewhen answer")]
    new_frame = temp_db.q("SELECT id FROM frames WHERE chat_id=?", (ncid,), one=True)["id"]
    assert rows[0]["frame_id"] is None and rows[1]["frame_id"] == new_frame
    # An archive from before the room has no thread and imports cleanly.
    del archive["room_messages"]
    assert client.post("/api/chats/import", json={"data": archive}).status_code == 200


def test_a_turn_checkpoint_does_not_unsay_the_conversation(temp_db, unseated):
    cid = _chat(temp_db)
    _turn(temp_db, cid, 0)
    temp_db.qi("INSERT INTO checkpoints(chat_id,turn_idx,blob,created) VALUES(?,?,?,?)",
               (cid, 0, json.dumps(snapshot_state(cid)), time.time()))
    room.add_message(cid, None, "player", "said after the checkpoint")
    restore_checkpoint(cid, 0)
    assert [m["text"] for m in room.messages(cid, None)] == ["said after the checkpoint"]


def test_deleting_a_story_takes_its_conversation_along(client, temp_db, unseated):
    cid = _chat(temp_db)
    room.add_message(cid, None, "player", "gone with the story")
    assert client.delete(f"/api/chats/{cid}").status_code == 200
    assert temp_db.q("SELECT COUNT(*) AS n FROM room_messages WHERE chat_id=?",
                     (cid,), one=True)["n"] == 0


# ---- the panel's script and page wiring -------------------------------------

def test_the_panel_script_loads_after_chat_and_before_app():
    html = (ROOT / "static" / "index.html").read_text()
    order = re.findall(r'/static/js/([a-z_-]+)\.js', html)
    assert order.index("chat") < order.index("writers_room") < order.index("app")
    assert 'id="room-tab"' in html and 'id="room"' in html


def test_the_panel_uses_the_pages_two_looks_not_a_third():
    css = (ROOT / "static" / "styles.css").read_text()
    # Docked: opaque chrome, named in the invariant's list.
    opaque = css[css.index("OPAQUE CHROME"):css.index("Scene backdrops")]
    assert "#room" in opaque
    # Floating: the prose plate's own rule and its weather gate, extended to
    # the panel rather than copied.
    assert re.search(r"body\.has-backdrop \.prose,\s*body\.has-backdrop #room\.floating\{", css)
    assert re.search(r"body\.has-weather-fx \.prose,\s*body\.has-weather-fx #room\.floating\{", css)
