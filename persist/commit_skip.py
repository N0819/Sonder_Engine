"""The skip's far end, committed: who is away and where, and who is asleep.

`agents/skip_stage.py` runs the cast through a stretch the players' input
passes over; this domain writes what its far end leaves that no diff states.
The PLACEMENTS are not here: the far end is laid under the beat's own diff
where the scene is composed (`commit_scene_state.compose_beat_scene`), so the
scene domain writes them with everything else the beat did and the account
that follows the skip keeps the last word on anyone it moves. What is here:

  * **The roster.** A mind whose day ends somewhere the world does not hold
    is AWAY there: dormant (`story.scene.CAST_STATUS_ABSENT`), with a typed
    whereabouts (`skip_stage.WHEREABOUTS_KEY`, the frame's world key). A
    dormant mind the far end puts in a room the world holds is back: active,
    its whereabouts gone.
  * **Awareness.** A sleep the far end ended is ended; a sleep it began is a
    condition row from when it began, so the natural waking floor counts
    from the right hour (`director_floors._NATURAL_SLEEP_SECONDS`).

Runs inside the turn's transaction, after the scene and before the entities
domain, so a resolve that wakes a sleeper the far end put down -- it saw the
row (`story.scene.awareness_conditions` under the onset preview) and ended it
by its id -- closes the row this domain opens; and before the cast domain, so
the beat's own `cast_changes` have the last word on the roster.
"""

from __future__ import annotations

import json

from core.db import q, qi, wget, wset


def _fold(text):
    return " ".join(str(text or "").split()).casefold()


def commit_skip_lives(ctx, nonce=None):
    """Write the far end's roster, whereabouts and awareness. Returns what it
    wrote, by mind name; `{}` for a beat with no skip."""
    output = getattr(ctx, "skip_lives", None)
    minds = (output or {}).get("minds") if isinstance(output, dict) else None
    if not isinstance(minds, dict) or not minds:
        return {}
    from agents.skip_stage import (WHEREABOUTS_KEY, WHEREABOUTS_OFF_MAP,
                                   FarEnd)
    from story.scene import (CAST_STATUS_ABSENT, CAST_STATUS_PRESENT,
                             awareness_conditions, set_char_status)
    from story.character_schema import character_name_from_text
    chat_id = ctx.chat.id
    frame_id = getattr(ctx.turn, "frame_id", None)
    rows = q("SELECT ch.id, COALESCE(cc.sheet,ch.sheet) AS sheet, cc.status "
             "FROM chat_chars cc JOIN characters ch ON ch.id=cc.char_id "
             "WHERE cc.chat_id=?", (chat_id,))
    ids = {}
    for row in rows:
        name = character_name_from_text(row["sheet"])
        if name:
            ids[_fold(name)] = int(row["id"])
    scene_rooms = (wget(chat_id, "scene", {}) or {}).get("rooms") or {}
    whereabouts = dict(wget(chat_id, WHEREABOUTS_KEY, {}) or {})
    span = output.get("span") or {}
    out = {"away": {}, "back": [], "asleep": [], "woke": []}
    for name in sorted(minds):
        far = (minds[name] or {}).get("far_end") or {}
        cid = ids.get(_fold(name))
        for key in [k for k in whereabouts if _fold(k) == _fold(name)]:
            whereabouts.pop(key, None)
        if far.get("away") and not far.get("room"):
            whereabouts[name] = {
                "kind": WHEREABOUTS_OFF_MAP, "label": str(far["away"]),
                "since_s": _since_away(minds[name], span),
                "turn_idx": int(getattr(ctx.turn, "idx", 0) or 0),
                "char_id": cid}
            if cid is not None:
                set_char_status(chat_id, cid, CAST_STATUS_ABSENT, frame_id=frame_id)
            out["away"][name] = str(far["away"])
        elif far.get("room") in scene_rooms and cid is not None:
            row = next((r for r in rows if int(r["id"]) == cid), None)
            if row is not None and str(row["status"] or "") != CAST_STATUS_PRESENT:
                set_char_status(chat_id, cid, CAST_STATUS_PRESENT, frame_id=frame_id)
                out["back"].append(name)
    wset(chat_id, WHEREABOUTS_KEY, whereabouts)
    far = FarEnd(chat_id, output, getattr(ctx.turn, "id", None))
    ended, started = far.awareness_changes(awareness_conditions(chat_id))
    for record in ended:
        payload = dict(record.get("payload") or {})
        payload.update(condition_id=record["condition_id"], subject_id=record["subject"],
                       kind=str(payload.get("kind") or "awareness"), active=0,
                       ended_reason="woke within a skipped stretch")
        qi("UPDATE world_conditions SET payload=?, active=0 "
           "WHERE condition_id=? AND chat_id=?",
           (json.dumps(payload, ensure_ascii=False), record["condition_id"], chat_id))
        out["woke"].append(record["subject"])
    for cond in started:
        payload = json.dumps(
            {**cond, "last_asserted_turn_idx": int(getattr(ctx.turn, "idx", 0) or 0)},
            ensure_ascii=False)
        qi("DELETE FROM world_conditions WHERE condition_id=? AND chat_id=?",
           (cond["condition_id"], chat_id))
        qi("INSERT INTO world_conditions(condition_id,chat_id,subject_id,kind,"
           "started_at,expires_at,next_tick,payload,active) VALUES(?,?,?,?,?,?,?,?,?)",
           (cond["condition_id"], chat_id, cond["subject_id"], cond["kind"],
            cond["started_at_seconds"], None, None, payload, 1))
        out["asleep"].append(cond["subject_id"])
    return out


def _since_away(mind, span):
    """When the mind went off the map: the start of the unbroken run of
    off-map stretches its log ends in."""
    log = (mind or {}).get("log") or []
    since = None
    for row in reversed(log):
        if row.get("room") or not row.get("away"):
            break
        since = row.get("from_s")
    try:
        return float(since if since is not None else span.get("until_s"))
    except (TypeError, ValueError):
        return None
