"""Typed HTTP boundary for the Writers' Room panel.

Transport only: validation, status codes and the wire shapes. Every rule --
what a message may be, who may speak, what a mandate looks like, what the
placeholder says -- lives in :mod:`story.room_conversation`, so the room's
contract is testable without a request. Host-only by construction: the
access-control middleware in ``web/app.py`` admits a guest to
``GUEST_ALLOWED_API_PATHS`` alone, and nothing here is in it -- the room is
the host's authoring seat, not a player surface.

Routes (all under ``/api/chats/{cid}/room``; ``frame_id`` absent or null is
the present, else a frame row of this chat):

* ``GET  ?frame_id=&before=`` -> ``{messages, mandates, status, seated}``
* ``POST /messages {text, frame_id}`` -> ``{message, replies, error,
  mandates, status, seated}``
* ``POST /mandates/{uid}/revoke {frame_id}`` -> ``{mandate, mandates}``
* ``GET  /status?frame_id=`` -> the status row
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.db import q
from story import room_conversation as room

router = APIRouter(prefix="/api/chats/{cid}/room", tags=["writers-room"])


class RoomMessage(BaseModel):
    text: str = ""
    frame_id: int | None = None


class RoomFrame(BaseModel):
    frame_id: int | None = None


def _chat_and_frame(cid: int, frame_id):
    if not q("SELECT id FROM chats WHERE id=?", (cid,), one=True):
        raise HTTPException(404, detail="No such story")
    if not room.frame_belongs(cid, frame_id):
        raise HTTPException(404, detail="No such frame in this story")


@router.get("")
def room_thread(cid: int, frame_id: int | None = None, before: int | None = None):
    _chat_and_frame(cid, frame_id)
    return {
        "messages": room.messages(cid, frame_id, before=before),
        "mandates": room.mandates(cid, frame_id),
        "status": room.status(cid, frame_id),
        "seated": room.planner_seated(),
        "page": room.ROOM_PAGE,
        "message_chars": room.ROOM_MESSAGE_CHARS,
    }


@router.post("/messages")
def room_say(cid: int, body: RoomMessage):
    _chat_and_frame(cid, body.frame_id)
    text = str(body.text or "").strip()
    if not text:
        raise HTTPException(400, detail="Say something to the room first")
    if len(text) > room.ROOM_MESSAGE_CHARS:
        raise HTTPException(
            400, detail="That note is longer than the room reads at once; "
                        "attach a document as lore instead")
    return room.converse(cid, body.frame_id, text)


@router.post("/messages/stream")
def room_say_stream(cid: int, body: RoomMessage):
    """`room_say`, as a stream, so the panel shows the room working.

    NDJSON rather than server-sent events, matching the turn stream this
    engine already speaks (`web/app._stream`) so the browser has one decoder
    and one reconnection story rather than two.

    The generator does the writes, in the same order the non-streaming route
    does, so a client that cannot stream loses only the watching. Refusals
    stay HTTP: the argument checks below run BEFORE the response begins,
    because a 400 delivered as an event inside a 200 is a refusal the client
    has to be taught to look for.
    """
    _chat_and_frame(cid, body.frame_id)
    text = str(body.text or "").strip()
    if not text:
        raise HTTPException(400, detail="Say something to the room first")
    if len(text) > room.ROOM_MESSAGE_CHARS:
        raise HTTPException(
            400, detail="That note is longer than the room reads at once; "
                        "attach a document as lore instead")

    def lines():
        for event in room.converse_stream(cid, body.frame_id, text):
            yield json.dumps(event, ensure_ascii=False, default=str) + "\n"

    return StreamingResponse(lines(), media_type="application/x-ndjson")


@router.post("/mandates/{uid}/revoke")
def room_revoke(cid: int, uid: str, body: RoomFrame):
    _chat_and_frame(cid, body.frame_id)
    mandate = room.revoke_mandate(cid, uid, body.frame_id)
    if mandate is None:
        raise HTTPException(404, detail="No such mandate")
    return {"mandate": mandate, "mandates": room.mandates(cid, body.frame_id)}


@router.get("/status")
def room_status(cid: int, frame_id: int | None = None):
    _chat_and_frame(cid, frame_id)
    return room.status(cid, frame_id)
