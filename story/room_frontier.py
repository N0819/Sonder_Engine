"""The prepared frontier: how much world stands ready ahead of the player,
measured, and the identity-fill ledger the budget is counted against.

v2 § 3.2-3.3: the Story Planner keeps a SMALL frontier ahead of likely
movement -- rooms planned along the exits the player can reach, and
identities reserved for the people the story will meet -- so arrival can be
immediate and grounded. It is never a claim about where the player will go:
an unprepared direction is an ordinary miss, answered by a planning need.

Everything here is deterministic reading. It counts; it does not author.
What is short becomes a task for the Planner's fill job
(`agents/story_planner.py`), which authors through a package under the
identity-fill mandate and records each fill here so the per-story-hour
ceiling can be counted. The row rides the frame-scoped `room_frontier`
world key.
"""

from __future__ import annotations

import time

from core.db import wget_for_frame, wset_for_frame

#: The world key. Frame-scoped (core/db.FRAME_SCOPED_WORLD_KEYS).
FRONTIER_KEY = "room_frontier"

#: How far ahead of the player the frontier is counted, in room hops over
#: passable edges and the plan's topology.
FRONTIER_DEPTH_HOPS = 2
#: Planned, still-unfurnished rooms wanted within that depth. Below it the
#: frontier is short of rooms.
FRONTIER_ROOMS_MIN = 2
#: Reserved identities wanted: authored person plans nobody has rendered
#: yet, anywhere in the frame. Below it the frontier is short of people.
FRONTIER_IDENTITIES_MIN = 2
#: Fill records kept on the row; older ones fall off.
FILLS_KEPT = 48
#: One story hour, in the clock's seconds, for the per-hour budget.
STORY_HOUR_SECONDS = 3600.0
#: When the story has no clock yet, a fill "hour" is this many beats.
HOUR_AS_TURNS_FALLBACK = 8


def _row(cid, frame_id):
    stored = wget_for_frame(cid, FRONTIER_KEY, frame_id, {}) or {}
    return stored if isinstance(stored, dict) else {}


def _save(cid, frame_id, row):
    wset_for_frame(cid, FRONTIER_KEY, row, frame_id)


def _player_room(cid, scene):
    from core.db import q
    from story.character_schema import persona_name
    from story.scene import persona_of
    chat = q("SELECT * FROM chats WHERE id=?", (cid,), one=True)
    if not chat:
        return None
    name = persona_name(persona_of(dict(chat)))
    positions = scene.get("positions") or {}
    room = positions.get(name)
    return str(room) if room else None


def rooms_ahead(cid, scene, start, depth=FRONTIER_DEPTH_HOPS):
    """Room ids within ``depth`` hops of ``start`` over passable edges plus
    the plan's topology, and which of them are still the plan's unfurnished
    stubs. Returns ``(reachable, stubs)``."""
    from world.spatial import passable_neighbors
    from world.structure import is_planned_stub, planned_topology

    graph = {str(k): {str(v) for v in vs}
             for k, vs in passable_neighbors(scene).items()}
    topology = planned_topology(cid)
    planned = set(topology)
    for rid, others in topology.items():
        for other in others:
            graph.setdefault(rid, set()).add(other)
            graph.setdefault(other, set()).add(rid)
    if not start:
        return [], []
    seen, frontier = {start}, [start]
    for _hop in range(max(0, int(depth))):
        nxt = []
        for node in frontier:
            for other in sorted(graph.get(node, ())):
                if other not in seen:
                    seen.add(other)
                    nxt.append(other)
        frontier = nxt
    rooms = scene.get("rooms") or {}
    # The inside of a body (`parent_entity`) is not a place ahead of the
    # player and never a frontier gap: where the world puts a body is the
    # Director's, and it is transient (owner ruling, 2026-09-03).
    contained = {str(r) for r, room in rooms.items()
                 if isinstance(room, dict) and room.get("parent_entity")}
    reachable = sorted((seen - {start}) - contained)
    stubs = [rid for rid in reachable
             if (rid in rooms and is_planned_stub(scene, rid))
             or (rid not in rooms and rid in planned)]
    return reachable, stubs


def frontier_report(cid, frame_id=None, scene=None):
    """Measure the frontier: what stands ahead, what is short, what is
    open. Pure read; nothing is written."""
    from story.scene import get_scene
    from world.planned_entities import planned_entities
    from world.planning_needs import open_planning_needs
    if scene is None:
        from core.db import q
        chat = q("SELECT * FROM chats WHERE id=?", (cid,), one=True)
        scene = (get_scene(cid, chat) if chat else {}) or {}
    start = _player_room(cid, scene)
    reachable, stubs = rooms_ahead(cid, scene, start)
    identities = [p["name"] for p in planned_entities(cid, frame_id).values()
                  if p["kind"] == "person" and not p.get("rendered") and p.get("name")]
    needs = open_planning_needs(cid, frame_id)
    by_kind = {}
    for need in needs:
        by_kind[need["kind"]] = by_kind.get(need["kind"], 0) + 1
    return {
        "player_room": start,
        "depth_hops": FRONTIER_DEPTH_HOPS,
        "reachable": reachable,
        "rooms_ahead": stubs,
        "rooms_short": max(0, FRONTIER_ROOMS_MIN - len(stubs)),
        "identities_ahead": identities,
        "identities_short": max(0, FRONTIER_IDENTITIES_MIN - len(identities)),
        "open_needs": by_kind,
        "open_need_uids": [n["uid"] for n in needs],
    }


def record_measure(cid, frame_id, report, turn_idx=None):
    row = _row(cid, frame_id)
    row["measured_turn"] = turn_idx
    row["rooms_short"] = report.get("rooms_short", 0)
    row["identities_short"] = report.get("identities_short", 0)
    row["open_needs"] = dict(report.get("open_needs") or {})
    _save(cid, frame_id, row)
    return row


def _clock_seconds(cid, frame_id):
    clock = wget_for_frame(cid, "simulation_clock", frame_id, {}) or {}
    value = clock.get("elapsed_seconds") if isinstance(clock, dict) else None
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def record_fill(cid, frame_id, *, turn_idx, package_uid="", needs=()):
    """One fill landed: counted against the hour's budget."""
    row = _row(cid, frame_id)
    fills = [f for f in (row.get("fills") or []) if isinstance(f, dict)]
    fills.append({"turn": int(turn_idx or 0),
                  "elapsed_seconds": _clock_seconds(cid, frame_id),
                  "at": time.time(), "package": str(package_uid or ""),
                  "needs": [str(n) for n in needs][:8]})
    row["fills"] = fills[-FILLS_KEPT:]
    _save(cid, frame_id, row)
    return row


def fills_this_hour(cid, frame_id, turn_idx=None):
    """How many fills landed within the last story hour -- by the clock's
    elapsed seconds when the story keeps one, else within the last
    `HOUR_AS_TURNS_FALLBACK` beats."""
    row = _row(cid, frame_id)
    fills = [f for f in (row.get("fills") or []) if isinstance(f, dict)]
    now = _clock_seconds(cid, frame_id)
    if now is not None:
        return sum(1 for f in fills
                   if f.get("elapsed_seconds") is not None
                   and now - float(f["elapsed_seconds"]) < STORY_HOUR_SECONDS)
    turn = int(turn_idx or 0)
    return sum(1 for f in fills
               if turn - int(f.get("turn") or 0) < HOUR_AS_TURNS_FALLBACK)
