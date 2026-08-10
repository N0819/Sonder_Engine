"""Physical information carriers for living-world approach C.

Truth in ``world_events`` is not knowledge. This module creates the first
legitimate bridge: when a mechanically fired event has a non-empty public
``witnessed`` surface, only registered characters physically at that location
acquire that surface. The report then travels because its holder travels; it is
stored in that character's frame-specific state and exposed only to that
character's private agent payload.

No timer grants knowledge, no prose is generated, and no other mind reads the
envelope. A listener learns later through the ordinary speech -> perception ->
memory path. Anonymous crowds/messages and copy-time subtractive degradation
are later C layers; they must reuse this envelope rather than broadcast the
objective event ledger.
"""

from __future__ import annotations

import json

from character_schema import normalize_character_data
from db import q
from living_world import living_world_allows, living_world_config
from scene import active_cast, set_char_state
from spatial import room_of


STATE_KEY = "carried_reports"
REPORT_CAP = 16
ROUTE_CAP = 12
PAYLOAD_CAP = 4


def _character_room(scene, sheet):
    identity = normalize_character_data(sheet or {}).get("identity") or {}
    keys = [identity.get("name"), identity.get("uid"),
            *(identity.get("aliases") or [])]
    for key in keys:
        if key:
            room = room_of(scene, str(key))
            if room:
                return str(room)
    return ""


def reports_for_state(state, cap=PAYLOAD_CAP):
    """Capped private projection; exact witnessed surfaces, newest first."""
    state = state if isinstance(state, dict) else {}
    rows = [r for r in state.get(STATE_KEY) or []
            if isinstance(r, dict) and r.get("world_event_id") and r.get("claim")]
    try:
        cap = max(0, int(cap))
    except (TypeError, ValueError):
        cap = PAYLOAD_CAP
    return [
        {k: row[k] for k in (
            "world_event_id", "source_event_id", "claim", "kind",
            "occurred_at", "acquired_turn", "current_location", "hops",
            "provenance") if k in row}
        for row in rows[-cap:]
    ]


def advance_carriers(ctx, scene, world_event_result):
    """Acquire public event surfaces and update each holder's physical trail.

    Runs inside ``commit_all`` after the normal character-state/memory domain,
    so it merges onto that domain's final state instead of being overwritten by
    a prepared state update. All writes share the turn transaction.
    """
    cid = ctx.chat.id
    if not living_world_allows(
            living_world_config(cid), "rumor_ledger", "floor"):
        offered = len((world_event_result or {}).get("events") or [])
        return {"enabled": False, "events_offered": offered,
                "public_surfaces": 0, "carrier_opportunities": 0,
                "acquired": 0, "carriers_moved": 0}

    event_ids = [str(e.get("event_id")) for e in
                 (world_event_result or {}).get("events") or []
                 if isinstance(e, dict) and e.get("event_id")]
    event_rows = []
    for event_id in event_ids:
        row = q(
            "SELECT * FROM world_events WHERE chat_id=? AND event_id=? "
            "AND frame_id IS ?", (cid, event_id, ctx.turn.frame_id), one=True)
        if not row:
            continue
        try:
            payload = json.loads(row["payload"] or "{}")
        except (TypeError, ValueError):
            payload = {}
        witnessed = " ".join(str((payload or {}).get("witnessed") or "").split())
        if witnessed and row["location_id"]:
            event_rows.append((dict(row), payload, witnessed[:320]))

    public_surfaces = len(event_rows)
    carrier_opportunities = acquired = moved = 0
    for cast_row in active_cast(cid, ctx.turn.frame_id):
        try:
            sheet = json.loads(cast_row["sheet"] or "{}")
        except (TypeError, ValueError):
            sheet = {}
        current_room = _character_room(scene, sheet)
        try:
            state = json.loads(cast_row["cstate"] or "{}")
        except (TypeError, ValueError):
            state = {}
        if not isinstance(state, dict):
            state = {}
        reports = [dict(r) for r in state.get(STATE_KEY) or []
                   if isinstance(r, dict) and r.get("world_event_id")]
        changed = False

        # The envelope moves only because its physical holder moved. Endpoint
        # movement is enough for provenance; no code invents intermediate
        # route rooms that the scene did not establish.
        for report in reports:
            previous = str(report.get("current_location") or "")
            if current_room and previous and current_room != previous:
                route = [str(x) for x in report.get("route") or [] if x]
                if not route or route[-1] != current_room:
                    route.append(current_room)
                report["route"] = route[-ROUTE_CAP:]
                report["current_location"] = current_room
                report["hops"] = max(0, int(report.get("hops") or 0)) + 1
                report["last_moved_turn"] = int(ctx.turn.idx)
                moved += 1
                changed = True

        known = {str(r.get("world_event_id")) for r in reports}
        for row, payload, witnessed in event_rows:
            if str(row["location_id"]) != current_room:
                continue
            carrier_opportunities += 1
            if str(row["event_id"]) in known:
                continue
            reports.append({
                "world_event_id": str(row["event_id"]),
                "source_event_id": str(payload.get("source_event_id") or ""),
                "claim": witnessed,
                "kind": str(row["kind"]),
                "occurred_at": float(row["occurred_at"]),
                "acquired_turn": int(ctx.turn.idx),
                "acquired_location": current_room,
                "current_location": current_room,
                "route": [current_room],
                "hops": 0,
                "provenance": "witnessed_surface",
            })
            known.add(str(row["event_id"]))
            acquired += 1
            changed = True

        if changed:
            state[STATE_KEY] = reports[-REPORT_CAP:]
            set_char_state(cid, cast_row["id"],
                           json.dumps(state, ensure_ascii=False),
                           frame_id=ctx.turn.frame_id)

    return {"enabled": True, "events_offered": len(event_ids),
            "public_surfaces": public_surfaces,
            "carrier_opportunities": carrier_opportunities,
            "acquired": acquired, "carriers_moved": moved}
