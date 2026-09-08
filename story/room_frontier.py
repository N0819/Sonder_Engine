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
    """The room the player STANDS IN -- whatever holds it. A room carrying
    `parent_entity` is where the world put the player's body, and it is the
    same room `room_slice.room_index` lists with its holder; the two reads
    must name one room or the Planner plans against a phantom (chat 115:
    the frontier said `room_elevator_interior`, the room tool listed no
    such room, and a second lift car was planned beside the one the cast
    was riding)."""
    from core.db import q
    from story.character_schema import persona_name
    from story.scene import persona_of
    from world.spatial import room_of
    chat = q("SELECT * FROM chats WHERE id=?", (cid,), one=True)
    if not chat:
        return None
    name = persona_name(persona_of(dict(chat)))
    positions = scene.get("positions") or {}
    room = positions.get(name) or room_of(scene, name)
    return str(room) if room else None


def rooms_ahead(cid, scene, start, depth=FRONTIER_DEPTH_HOPS, contained=None):
    """Room ids within ``depth`` hops of ``start`` over passable edges plus
    the plan's topology, and which of them are still the plan's unfurnished
    stubs. Returns ``(reachable, stubs)``.

    The graph and the count are `room_slice.room_hops`, the same ones the
    room index reports, so the frontier and the tool agree hop for hop. A
    start that is the inside of a body counts OUT through the room its
    holder stands in (one hop); no other inside is ahead of the player or a
    frontier gap, because where the world puts a body is the Director's and
    transient (owner ruling, 2026-09-03) -- so contained rooms are counted
    through and never listed.

    ONE READ EACH. The containment map and the plan's topology are what the
    graph is built from and what the stub test asks; both were made here and
    again inside `room_graph` (C21). ``contained`` lets the caller that
    already holds the map hand it in."""
    from story.room_slice import containment, room_graph, room_hops
    from world.structure import is_planned_stub, planned_topology

    if not start:
        return [], []
    contained = containment(scene) if contained is None else contained
    topology = planned_topology(cid)
    hops = room_hops(cid, scene, [str(start)],
                     graph=room_graph(cid, scene, contained=contained,
                                      planned=topology))
    rooms = scene.get("rooms") or {}
    contained = set(contained)
    planned = set(topology)
    reachable = sorted(rid for rid, n in hops.items()
                       if 0 < n <= max(0, int(depth)) and rid not in contained)
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
        from story.room_slice import read_scene
        scene = read_scene(cid, frame_id) or {}
    from story.room_slice import containment
    start = _player_room(cid, scene)
    contained = containment(scene)
    reachable, stubs = rooms_ahead(cid, scene, start, contained=contained)
    holder = contained.get(start) if start else None
    plans = [p for p in planned_entities(cid, frame_id).values()
             if not p.get("rendered") and p.get("name")]
    identities = [p["name"] for p in plans if p["kind"] == "person"]
    # THE OTHER TWO THIRDS OF `PLAN_KINDS`. `identities_ahead` measures whether
    # enough PEOPLE stand ahead of the story, and that is the right measure --
    # `identities_short` is unchanged and still counts only persons. But the
    # report was also the one standing place an unrendered plan surfaced at
    # all, so a thing or a creature the Room had filed was in no read it has:
    # not here, not in `inspect_rooms` (which listed bodies only), and not in
    # the reply payload, which carries no scene. Reported beside the count
    # rather than inside it -- a filed prop is not a populated frontier.
    things = [{"uid": p["uid"], "name": p["name"], "kind": p["kind"],
               "where": (p.get("brief") or {}).get("where") or ""}
              for p in plans if p["kind"] != "person"]
    needs = open_planning_needs(cid, frame_id)
    by_kind = {}
    by_reason = {}
    for need in needs:
        by_kind[need["kind"]] = by_kind.get(need["kind"], 0) + 1
        by_reason[need["reason"]] = by_reason.get(need["reason"], 0) + 1
    return {
        "player_room": start,
        # The body the player's room is the inside of, when it is one: the
        # room stays the room they stand in, and this says what holds it.
        "player_holder": holder,
        "depth_hops": FRONTIER_DEPTH_HOPS,
        "reachable": reachable,
        "rooms_ahead": stubs,
        "rooms_short": max(0, FRONTIER_ROOMS_MIN - len(stubs)),
        "identities_ahead": identities,
        "identities_short": max(0, FRONTIER_IDENTITIES_MIN - len(identities)),
        "things_ahead": things,
        "open_needs": by_kind,
        # AND WHY EACH ONE IS OPEN. `kind` is three values against five
        # reasons, so a count by kind alone reads as a pile of props: 8 of
        # the 9 needs open on the owner's live stories (2026-09-06) are
        # `setting_fact`, filed as `thing` because that is the fallback and
        # carrying a whole sentence as their subject. `inspect_needs` and
        # the fill job always saw the reason; the report the Room reads
        # first did not.
        "open_needs_by_reason": by_reason,
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


#: Spend records kept on the row (one per Planner or Dramaturge pass);
#: older ones fall off.
SPEND_KEPT = 96


def record_spend(cid, frame_id, *, turn_idx, calls, who="planner"):
    """One pass's tool calls, counted against the hour's spend
    (`mandates.spend_limits`). Zero-call passes are not recorded."""
    calls = int(calls or 0)
    if calls <= 0:
        return _row(cid, frame_id)
    row = _row(cid, frame_id)
    spend = [s for s in (row.get("spend") or []) if isinstance(s, dict)]
    spend.append({"turn": int(turn_idx or 0),
                  "elapsed_seconds": _clock_seconds(cid, frame_id),
                  "at": time.time(), "calls": calls, "who": str(who)[:24]})
    row["spend"] = spend[-SPEND_KEPT:]
    _save(cid, frame_id, row)
    return row


def spend_this_hour(cid, frame_id, turn_idx=None):
    """Tool calls made within the last story hour, on the same clock the
    fill budget uses."""
    row = _row(cid, frame_id)
    spend = [s for s in (row.get("spend") or []) if isinstance(s, dict)]
    now = _clock_seconds(cid, frame_id)
    if now is not None:
        return sum(int(s.get("calls") or 0) for s in spend
                   if s.get("elapsed_seconds") is not None
                   and now - float(s["elapsed_seconds"]) < STORY_HOUR_SECONDS)
    turn = int(turn_idx or 0)
    return sum(int(s.get("calls") or 0) for s in spend
               if turn - int(s.get("turn") or 0) < HOUR_AS_TURNS_FALLBACK)


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
