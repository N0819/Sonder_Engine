"""The Writers' Room's authoring facade: one table of tools over existing
seams, written so an agent can be handed the table as its tools.

Every entry in `TOOLS` is a name, a paragraph written for a model, a JSON
schema for its arguments, and a pure-code handler. `tool_manifest()` is the
model-facing table; `run_tool()` is the one call site, which checks the
arguments against the schema, runs the handler, and caps the result. There
is NO tool that takes SQL, a file path, or a module name: the room reads
the world through the engine's own readers and writes it only through a
plot package (`story/plot_packages.py`), which is where the author-layer
invariant is enforced -- see that module's docstring.

Read tools return OBJECTIVE truth. The room is an author (v2 § 2.1) and may
read what no mind may: every room, every charter body's private mind, every
sealed package (through `read_package` with `reveal`, marked host-only in
the manifest so an agent is not handed it by default). Nothing a read tool
returns reaches a mind by being read here.

Three properties of the manifest an agent's loop may rely on:

* ``long`` marks a tool that makes a model call or lives a town forward
  (`prepare_package`); everything else returns in milliseconds.
* ``host_only`` marks a tool the panel offers the host and an agent is not
  handed by default (`read_package` with `reveal`, `retire_package`).
* Every write tool names the package it writes into; there is no write
  tool without a ``uid`` argument except `new_package`.
"""

from __future__ import annotations

import json

from story.plot_packages import operation_shape_text
from story.room_research import tool_entries as _research_tool_entries

#: Result ceiling, in characters of JSON; past it the result is truncated
#: with a `truncated` marker rather than a model being handed a transcript.
TOOL_RESULT_CHARS = 12_000
#: `search_lore` k ceiling; the default is the engine's own.
SEARCH_K_CAP = 12
SEARCH_K_DEFAULT = 6
#: Entries per `scan_lore` page.
SCAN_PAGE = 40
#: Characters of an entry's content shown in a listing (the full text is
#: `read_lore`).
EXCERPT_CHARS = 280
#: Recent events served by `inspect_events`.
EVENTS_CAP = 40
EVENTS_DEFAULT = 12
#: Route length `inspect_route` will search (hops).
ROUTE_HOPS_CAP = 64
#: Bodies listed per charter by `inspect_charters` before the caller must
#: ask for one charter.
BODIES_PER_CHARTER = 24


class ToolError(ValueError):
    """A refused call: bad arguments, an unknown tool, a seam's refusal."""


def _excerpt(text, limit=EXCERPT_CHARS):
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _cap(value, cap, default):
    try:
        value = int(value) if value is not None else default
    except (TypeError, ValueError):
        return default
    return max(1, min(cap, value))


# ---------------------------------------------------------------------------
# Read tools
# ---------------------------------------------------------------------------

def _t_search_lore(cid, frame_id, *, query, k=None, categories=None):
    from mind.memory import search_lore
    from mind.memory import chat_lorebook_weights

    hits = search_lore(chat_lorebook_weights(cid), str(query),
                       k=_cap(k, SEARCH_K_CAP, SEARCH_K_DEFAULT))
    wanted = {str(c) for c in (categories or ())}
    rows = []
    for hit in hits:
        if wanted and str(hit.get("category") or "other") not in wanted:
            continue
        rows.append({
            "citation": "lore:%s" % hit.get("id"),
            "id": hit.get("id"), "uid": hit.get("entry_uid"),
            "book_id": hit.get("book_id"), "title": hit.get("title"),
            "keys": hit.get("keys"), "category": hit.get("category"),
            "locked": bool(hit.get("locked")),
            "excerpt": _excerpt(hit.get("content")),
        })
    return {"query": str(query), "hits": rows}


def _t_read_lore(cid, frame_id, *, entry_id):
    from core.db import q
    from mind.memory import chat_lorebook_ids

    row = q("SELECT id, entry_uid, lorebook_id, keys, content, category, "
            "canon_locked, title, turn_added, knowledge_locations, source_notes "
            "FROM lore_entries WHERE id=?", (int(entry_id),), one=True)
    if not row:
        raise ToolError("no lore entry %s" % entry_id)
    attached = set(chat_lorebook_ids(cid))
    chat = q("SELECT lorebook_id FROM chats WHERE id=?", (cid,), one=True)
    if chat and chat["lorebook_id"]:
        attached.add(int(chat["lorebook_id"]))
    if int(row["lorebook_id"]) not in attached:
        raise ToolError("lore entry %s is in a book this story is not attached to"
                        % entry_id)
    return {"citation": "lore:%s" % row["id"], "id": row["id"],
            "uid": row["entry_uid"], "book_id": row["lorebook_id"],
            "title": row["title"], "keys": row["keys"], "content": row["content"],
            "category": row["category"], "locked": bool(row["canon_locked"]),
            "turn_added": row["turn_added"],
            "knowledge_locations": row["knowledge_locations"],
            "provenance": row["source_notes"]}


def _t_scan_lore(cid, frame_id, *, book_id=None, category=None, cursor=0,
                 limit=None):
    from core.db import q
    from mind.memory import chat_lorebook_ids

    attached = list(chat_lorebook_ids(cid))
    chat = q("SELECT lorebook_id FROM chats WHERE id=?", (cid,), one=True)
    if chat and chat["lorebook_id"] and int(chat["lorebook_id"]) not in attached:
        attached.append(int(chat["lorebook_id"]))
    if book_id is not None:
        if int(book_id) not in attached:
            raise ToolError("book %s is not attached to this story" % book_id)
        attached = [int(book_id)]
    if not attached:
        return {"entries": [], "next_cursor": None, "books": []}
    page = _cap(limit, SCAN_PAGE, SCAN_PAGE)
    cursor = max(0, int(cursor or 0))
    marks = ",".join("?" for _ in attached)
    args = list(attached)
    where = "lorebook_id IN (%s)" % marks
    if category:
        where += " AND category=?"
        args.append(str(category))
    rows = q("SELECT id, lorebook_id, title, keys, content, category, canon_locked "
             "FROM lore_entries WHERE %s ORDER BY id LIMIT ? OFFSET ?" % where,
             tuple(args + [page + 1, cursor]))
    entries = [{"citation": "lore:%s" % r["id"], "id": r["id"],
                "book_id": r["lorebook_id"], "title": r["title"],
                "keys": r["keys"], "category": r["category"],
                "locked": bool(r["canon_locked"]),
                "excerpt": _excerpt(r["content"])} for r in rows[:page]]
    return {"entries": entries, "books": attached,
            "next_cursor": cursor + page if len(rows) > page else None}


def _scene(cid):
    from core.db import q
    from story.scene import get_scene
    chat = q("SELECT * FROM chats WHERE id=?", (cid,), one=True)
    return get_scene(cid, chat) or {}


def _containment(scene):
    """``{room_id: holder}`` for every room that is the inside of a body
    (`parent_entity`). Such a room is a fact about the holder, never a
    place the Planner plans, routes through, or reads as a gap."""
    return {str(r): str(room.get("parent_entity"))
            for r, room in ((scene or {}).get("rooms") or {}).items()
            if isinstance(room, dict) and room.get("parent_entity")}


def _t_inspect_structures(cid, frame_id):
    from core.db import wget_for_frame
    from world.structure import STRUCTURES_KEY, normalize_structures, planned_room_ids

    stored = normalize_structures(
        wget_for_frame(cid, STRUCTURES_KEY, None, {}) or {})
    planned = sorted(planned_room_ids(cid))
    return {"structures": stored["items"], "planned_rooms": planned}


def _t_inspect_rooms(cid, frame_id, *, room_ids=None, include_planned=True):
    from world.structure import planned_context, planned_room_ids
    scene = _scene(cid)
    rooms = scene.get("rooms") or {}
    positions = scene.get("positions") or {}
    occupants = {}
    for who, room in positions.items():
        occupants.setdefault(str(room), []).append(str(who))
    wanted = {str(r) for r in (room_ids or ())}
    out, containment = [], []
    for rid, room in rooms.items():
        if wanted and str(rid) not in wanted:
            continue
        room = room if isinstance(room, dict) else {}
        if room.get("parent_entity"):
            # THE INSIDE OF A BODY IS NOT A ROOM TO PLAN. The Planner may
            # know somebody is contained -- that is a fact about the world
            # -- but a room whose record carries `parent_entity` is where
            # the world put a body, minted by the Director and living only
            # while the containment does. Reported as containment on its
            # holder, never as a room with exits (owner ruling, 2026-09-03).
            holder = str(room["parent_entity"])
            containment.append({
                "inside": holder, "who": occupants.get(str(rid), []),
                "holder_room": str(positions.get(holder) or ""),
                "room_id": str(rid)})
            continue
        out.append({
            "id": str(rid), "name": room.get("name"),
            "description": _excerpt(room.get("desc") or room.get("description")),
            "exits": [{"to": e.get("to"), "barrier": e.get("barrier")}
                      for e in (room.get("adjacent") or []) if isinstance(e, dict)],
            "occupants": occupants.get(str(rid), []),
            "planned_stub": bool(room.get("planned")),
        })
    planned = []
    if include_planned:
        for rid in sorted(planned_room_ids(cid)):
            if wanted and rid not in wanted:
                continue
            if rid in rooms:
                continue
            brief = planned_context(cid, rid) or {}
            planned.append({"id": rid, "name": brief.get("name"),
                            "purpose": brief.get("purpose"),
                            "exits": brief.get("adjacent") or []})
    return {"location": scene.get("location"), "rooms": out,
            "planned_only": planned,
            **({"containment": containment} if containment else {})}


def _t_inspect_route(cid, frame_id, *, from_room, to_room):
    from world.spatial import passable_neighbors
    from world.structure import planned_topology
    scene = _scene(cid)
    contained = _containment(scene)
    graph = {str(k): {str(v) for v in vs if str(v) not in contained}
             for k, vs in passable_neighbors(scene).items()
             if str(k) not in contained}
    # The plan's topology counts as walkable: a planned stub is a room the
    # Director furnishes on entry. By ID: `planned_context` renders edges by
    # NAME for a reader, and a walk over names reached nothing planned.
    for rid, others in planned_topology(cid).items():
        for other in others:
            graph.setdefault(rid, set()).add(other)
            graph.setdefault(other, set()).add(rid)
    start, goal = str(from_room), str(to_room)
    for end in (start, goal):
        if end in contained:
            raise ToolError("%r is the inside of %s, not a place a route "
                            "reaches; where the world puts a body is the "
                            "Director's" % (end, contained[end]))
    if start not in graph and start not in (scene.get("rooms") or {}):
        raise ToolError("room %r exists nowhere" % start)
    frontier, seen, parent = [start], {start}, {}
    hops = 0
    while frontier and hops < ROUTE_HOPS_CAP:
        nxt = []
        for node in frontier:
            for other in sorted(graph.get(node, ())):
                if other in seen:
                    continue
                seen.add(other)
                parent[other] = node
                if other == goal:
                    path = [goal]
                    while path[-1] != start:
                        path.append(parent[path[-1]])
                    return {"from": start, "to": goal, "hops": len(path) - 1,
                            "path": list(reversed(path))}
                nxt.append(other)
        frontier = nxt
        hops += 1
    return {"from": start, "to": goal, "hops": None, "path": [],
            "reachable": sorted(seen)[:LIST_CAP_ROUTE]}


LIST_CAP_ROUTE = 60


def _t_inspect_reserved_identities(cid, frame_id):
    """Every name the room may not reuse: registered characters, charter
    bodies, authored plans and their aliases."""
    from core.db import q
    from world.planned_entities import planned_entities
    out = {"characters": [], "charter_bodies": [], "plans": []}
    for row in q("SELECT c.id, c.name, cc.status FROM chat_chars cc "
                 "JOIN characters c ON c.id=cc.char_id WHERE cc.chat_id=?", (cid,)):
        out["characters"].append({"id": row["id"], "name": row["name"],
                                  "status": row["status"]})
    try:
        from world.charter_runtime import registry_for
        registry = registry_for(cid, frame_id)
        for key, item in sorted((registry.get("items") or {}).items()):
            for bkey, body in sorted(
                    ((item.get("state") or {}).get("bodies") or {}).items()):
                out["charter_bodies"].append({
                    "charter": key, "body": bkey, "name": body.get("name"),
                    "place": body.get("place"), "available": body.get("available")})
    except Exception as exc:
        out["charter_bodies_error"] = str(exc)
    for plan in planned_entities(cid, frame_id).values():
        out["plans"].append({"uid": plan["uid"], "kind": plan["kind"],
                             "name": plan["name"], "aliases": plan["aliases"],
                             "rendered": bool(plan.get("rendered"))})
    return out


def _t_inspect_plans(cid, frame_id, *, kind=None):
    from world.planned_entities import planned_entities
    plans = [p for p in planned_entities(cid, frame_id).values()
             if not kind or p["kind"] == str(kind)]
    return {"plans": plans}


def _t_inspect_charters(cid, frame_id, *, charter=None, body=None):
    from world.charter_runtime import charter_diagnostics, registry_for
    registry = registry_for(cid, frame_id)
    items = registry.get("items") or {}
    if charter and str(charter) not in items:
        raise ToolError("no charter %r" % charter)
    summary = {}
    for key, item in sorted(items.items()):
        if charter and key != str(charter):
            continue
        state = item.get("state") or {}
        bodies = state.get("bodies") or {}
        listed = sorted(bodies.items())
        summary[key] = {
            "name": item.get("name") or key,
            "posts": sorted((state.get("posts") or {}).keys()),
            "upkeeps": sorted((state.get("upkeeps") or {}).keys()),
            "places": sorted({str(b.get("place")) for b in bodies.values()
                              if b.get("place")}),
            "body_count": len(bodies),
            "bodies": [{"key": k, "name": b.get("name"), "place": b.get("place"),
                        "berth": b.get("berth"), "available": b.get("available")}
                       for k, b in listed[:BODIES_PER_CHARTER]],
            "bodies_truncated": max(0, len(listed) - BODIES_PER_CHARTER),
        }
    out = {"charters": summary}
    if charter:
        out["diagnostics"] = charter_diagnostics(
            cid, frame_id, charter_key=str(charter), body_key=str(body or ""))
    return out


def _t_inspect_events(cid, frame_id, *, n=None):
    """Recent objective beats (the omniscient row -- the room is an author)
    and every pending scheduled event."""
    from core.db import q
    count = _cap(n, EVENTS_CAP, EVENTS_DEFAULT)
    rows = q("SELECT e.id, e.content, t.idx AS turn_idx FROM events e "
             "LEFT JOIN turns t ON t.id=e.turn_id WHERE e.chat_id=? "
             "ORDER BY e.id DESC LIMIT ?", (cid, count))
    recent = [{"turn_idx": r["turn_idx"], "content": _excerpt(r["content"], 600)}
              for r in reversed(list(rows))]
    pending = []
    for r in q("SELECT event_id, due_at, kind, location_id, payload FROM "
               "scheduled_events WHERE chat_id=? AND status='pending' "
               "ORDER BY due_at LIMIT ?", (cid, EVENTS_CAP)):
        try:
            payload = json.loads(r["payload"] or "{}")
        except (TypeError, ValueError):
            payload = {}
        pending.append({"event_id": r["event_id"], "due_at": r["due_at"],
                        "kind": r["kind"], "location": r["location_id"],
                        "summary": _excerpt(payload.get("summary")
                                            or payload.get("charter_event")
                                            or "", 200),
                        "source": payload.get("source")})
    return {"recent": recent, "pending": pending}


def _t_inspect_clock(cid, frame_id):
    from core.db import q, wget_for_frame
    from world.day_cycle import DAY_LENGTH_HOURS_DEFAULT, phase_of_hour
    scene = _scene(cid)
    clock = wget_for_frame(cid, "simulation_clock", frame_id, {}) or {}
    row = q("SELECT MAX(idx) AS idx FROM turns WHERE chat_id=?", (cid,), one=True)
    hour = clock.get("hour_of_day")
    day_length = clock.get("day_length_hours") or DAY_LENGTH_HOURS_DEFAULT
    return {"turn_idx": row["idx"] if row else None, "frame_id": frame_id,
            "elapsed_seconds": clock.get("elapsed_seconds"),
            "display": clock.get("display"),
            "hour_of_day": hour, "day_length_hours": day_length,
            "phase": clock.get("phase") or (
                phase_of_hour(float(hour), float(day_length))
                if hour is not None else None),
            "time_of_day": scene.get("time_of_day"),
            "day_phase": scene.get("day_phase")}


def _t_inspect_config(cid, frame_id):
    """The dials this story runs under. READ ONLY, and host-owned.

    The room authors rooms and people the Director then renders under a house
    style, a populace budget and an off-screen answer it had no way to see. So
    it could not be ASKED about them either, which is the cheaper half of what
    this room is for: a critique before anything is drafted costs one question
    and no package.

    Every value here is preserved across a rewind and a branch
    (`checkpoints.PRESERVED_SETTING_KEYS`), which is exactly the test that says
    it belongs to the host rather than to an authoring agent -- so this reads
    and never writes, and says so in `host_owned` rather than leaving the room
    to draft a change the engine would refuse.

    Install-wide settings are deliberately absent: model roles, providers and
    credentials are not story state, they are already kept out of the chat
    archive, and a story-facing tool must not be the thing that carries them
    back in.
    """
    from story.scene import (background_config, dialogue_config,
                             promotion_config, style_guide)
    guide = style_guide(cid) or {}
    dialogue = dialogue_config(cid) or {}
    populace = background_config(cid) or {}
    try:
        promotion = promotion_config(cid) or {}
    except Exception:
        promotion = {}
    return {
        "host_owned": True,
        "note": ("These are the host's dials, not the room's. Read them to "
                 "reason and to answer questions about them; a package that "
                 "tried to change one would be refused. Say what you would "
                 "change and why, and let the host turn it."),
        "style": {
            "tone": guide.get("tone", ""),
            "avoid": guide.get("avoid", ""),
            "weather_severity": guide.get("weather_severity"),
            "narration_tense": guide.get("narration_tense"),
            "day_length_hours": guide.get("day_length_hours"),
            "survival_enabled": guide.get("survival_enabled"),
        },
        "scene": {
            "autonomy": dialogue.get("autonomy"),
            "min_lines": dialogue.get("min_lines"),
            "max_lines": dialogue.get("max_lines"),
            "max_character_calls": dialogue.get("max_character_calls"),
            "initial_parallel_reactors": dialogue.get(
                "initial_parallel_reactors"),
        },
        "populace": {
            "max_reactors": populace.get("max_reactors"),
            "scene_life": populace.get("scene_life"),
            "max_managed": populace.get("max_managed"),
            "promotion_dialogue": promotion.get("dialogue"),
            "promotion_mention": promotion.get("mention"),
        },
        "offscreen": {
            # ONE QUESTION (scene.COGNITION_OFF_RUNG). The rung rides along
            # because the living-world approaches are still written against
            # it, so a plan that leans on one can check what it will run as.
            "cognition": dialogue.get("offscreen_cognition"),
            "rung": dialogue.get("offscreen_life"),
            "max_offscreen_actors": dialogue.get("max_offscreen_actors"),
        },
    }


def _t_inspect_needs(cid, frame_id, *, kind=None):
    from world.planning_needs import open_planning_needs
    return {"needs": open_planning_needs(cid, frame_id, kind=kind)}


def _t_inspect_contradictions(cid, frame_id):
    """What the world holds that does not agree with itself: registry
    warnings, structure warnings, and dangling references -- a planned
    exit to nowhere, a plan placed in no room, a bill in a room that is
    gone, a need for a room that is gone, a package participant nobody
    holds, a clock past due on an active package."""
    from story.artifacts import POSTED, standing_artifacts
    from story.plot_packages import packages
    from world.planned_entities import planned_entities
    from world.planning_needs import open_planning_needs
    from world.structure import planned_context, planned_room_ids
    scene = _scene(cid)
    contained = _containment(scene)
    # A containment room is not a room the world is missing and not one a
    # thing can dangle in: it is a body's inside, transient by nature.
    rooms = set(scene.get("rooms") or {}) - set(contained)
    planned = set(planned_room_ids(cid))
    known = rooms | planned | set(contained)
    out = {"registry": [], "structure": [], "dangling": []}
    try:
        from world.charter_runtime import registry_for, registry_warnings
        out["registry"] = registry_warnings(
            registry_for(cid, frame_id), scene=scene, cid=cid, frame_id=frame_id)
    except Exception as exc:
        out["registry"] = ["registry unreadable: %s" % exc]
    try:
        from core.db import wget_for_frame
        from world.structure import (STRUCTURES_KEY, normalize_structures,
                                     structure_warnings)
        stored = normalize_structures(
            wget_for_frame(cid, STRUCTURES_KEY, None, {}) or {})
        for key, structure in stored["items"].items():
            for w in structure_warnings(structure, scene.get("rooms") or {}):
                out["structure"].append("%s: %s" % (key, w))
    except Exception as exc:
        out["structure"] = ["structures unreadable: %s" % exc]
    for rid in sorted(planned):
        brief = planned_context(cid, rid) or {}
        for other in brief.get("adjacent") or ():
            if str(other) not in known and not any(
                    str(other) == (scene.get("rooms") or {}).get(r, {}).get("name")
                    for r in rooms):
                out["dangling"].append(
                    {"kind": "planned_exit_to_nowhere", "room": rid, "to": other})
    for plan in planned_entities(cid, frame_id).values():
        where = plan["brief"].get("where")
        if where and where not in known:
            out["dangling"].append({"kind": "plan_in_no_room", "uid": plan["uid"],
                                    "where": where})
    for artifact in standing_artifacts(cid):
        if artifact.get("status") == POSTED and str(artifact.get("room")) not in known:
            out["dangling"].append({"kind": "artifact_in_no_room",
                                    "uid": artifact.get("uid"),
                                    "room": artifact.get("room")})
    for need in open_planning_needs(cid, frame_id):
        room = need["surface"].get("room")
        if room and room not in known:
            out["dangling"].append({"kind": "need_in_no_room", "uid": need["uid"],
                                    "room": room})
    reserved = {r["name"].casefold() for r in
                _t_inspect_reserved_identities(cid, frame_id)["characters"]
                if r.get("name")}
    for pkg in packages(cid, frame_id).values():
        if pkg["status"] not in ("published", "active"):
            continue
        for part in pkg["participants"]:
            name = str(part.get("name") or part.get("text") or "")
            if name and name.casefold() not in reserved:
                out["dangling"].append({"kind": "participant_nobody_holds",
                                        "package": pkg["uid"], "name": name})
    return out


def _t_inspect_packages(cid, frame_id, *, status=None):
    from story.plot_packages import list_packages
    return {"packages": list_packages(cid, status=status, frame_id=frame_id)}


def _t_read_package(cid, frame_id, *, uid, reveal=False):
    from story.plot_packages import package_view
    return package_view(cid, uid, reveal=bool(reveal), frame_id=frame_id)


# ---------------------------------------------------------------------------
# Write tools -- every one through a package
# ---------------------------------------------------------------------------

def _t_new_package(cid, frame_id, *, title, premise="", spoiler_policy="open",
                   scope=None, authority=None, actor="writers_room"):
    from story.plot_packages import new_package, package_projection
    # `actor` is not a model argument: `run_tool` passes the caller's name
    # so a package records who drafted it, and a package the Planner drafted
    # publishes only under a mandate (`plot_packages.AGENT_AUTHORS`).
    pkg = new_package(cid, title=title, premise=premise,
                      spoiler_policy=spoiler_policy, scope=scope,
                      authority=authority, frame_id=frame_id,
                      created_by=str(actor or "writers_room"))
    return package_projection(pkg)


def _t_edit_package(cid, frame_id, *, uid, fields, reason=""):
    from story.plot_packages import edit_package, package_projection
    return package_projection(edit_package(cid, uid, fields, frame_id=frame_id,
                                           reason=reason))


def _t_draft_operation(cid, frame_id, *, uid, operation):
    from story.plot_packages import draft_operation
    pkg = draft_operation(cid, uid, operation, frame_id=frame_id)
    return {"uid": pkg["uid"], "revision": pkg["revision"],
            "operations": [op["op"] for op in pkg["operations"]]}


def _t_remove_operation(cid, frame_id, *, uid, index):
    from story.plot_packages import remove_operation
    pkg = remove_operation(cid, uid, index, frame_id=frame_id)
    return {"uid": pkg["uid"], "revision": pkg["revision"],
            "operations": [op["op"] for op in pkg["operations"]]}


def _t_preview_package(cid, frame_id, *, uid):
    from story.plot_packages import preview_package
    return preview_package(cid, uid, frame_id=frame_id)


def _t_validate_package(cid, frame_id, *, uid):
    from story.plot_packages import validate_package
    return validate_package(cid, uid, frame_id=frame_id)


def _t_prepare_package(cid, frame_id, *, uid):
    from story.plot_packages import prepare_package
    return prepare_package(cid, uid, frame_id=frame_id)


def _t_publish_package(cid, frame_id, *, uid, expected_revision):
    from story.plot_packages import publish_package
    return publish_package(cid, uid, expected_revision=expected_revision,
                           frame_id=frame_id)


def _t_resolve_package(cid, frame_id, *, uid, note=""):
    from story.plot_packages import package_projection, resolve_package
    return package_projection(resolve_package(cid, uid, note=note,
                                              frame_id=frame_id))


def _t_retire_package(cid, frame_id, *, uid, note=""):
    from story.plot_packages import package_projection, retire_package
    return package_projection(retire_package(cid, uid, note=note,
                                             frame_id=frame_id))


# ---------------------------------------------------------------------------
# The table
# ---------------------------------------------------------------------------

def _schema(properties, required=()):
    return {"type": "object", "properties": properties,
            "required": list(required), "additionalProperties": False}


_S = {"type": "string"}
_I = {"type": "integer"}
_B = {"type": "boolean"}
_O = {"type": "object"}
_SL = {"type": "array", "items": {"type": "string"}}

TOOLS = [
    # -- read ------------------------------------------------------------
    {"name": "search_lore",
     "description": "Search the story's attached lorebooks for entries about a subject. Returns the best matches with a stable citation (lore:<id>), the book, title, keys, category, whether the entry is locked, and an excerpt. Cite an entry by its citation when you rely on it; use read_lore for the full text.",
     "args": _schema({"query": _S, "k": _I, "categories": _SL}, ["query"]),
     "handler": _t_search_lore},
    {"name": "read_lore",
     "description": "Read one lore entry in full by its numeric id, including its provenance note. Only entries in books attached to this story are readable.",
     "args": _schema({"entry_id": _I}, ["entry_id"]), "handler": _t_read_lore},
    {"name": "scan_lore",
     "description": "Page through the attached lorebooks in id order, optionally one book or one category at a time. Returns excerpts and a next_cursor when more remain.",
     "args": _schema({"book_id": _I, "category": _S, "cursor": _I, "limit": _I}),
     "handler": _t_scan_lore},
    {"name": "inspect_structures",
     "description": "The planted structures (settlements, buildings) and every planned room id the registry holds -- the town's own topology, which a beat may furnish and may not delete.",
     "args": _schema({}), "handler": _t_inspect_structures},
    {"name": "inspect_rooms",
     "description": "The scene's live rooms (name, description excerpt, exits with barriers, who stands there) and the planned stubs nobody has entered yet. Pass room_ids to narrow.",
     "args": _schema({"room_ids": _SL, "include_planned": _B}),
     "handler": _t_inspect_rooms},
    {"name": "inspect_route",
     "description": "Whether one room can be walked to from another over passable edges and the plan's topology, and the shortest path if so. When unreachable, lists what IS reachable from the start.",
     "args": _schema({"from_room": _S, "to_room": _S}, ["from_room", "to_room"]),
     "handler": _t_inspect_route},
    {"name": "inspect_reserved_identities",
     "description": "Every name the room may not reuse: the registered characters, every charter body with its place, and every authored plan with its aliases. A new person must not collide with any of these.",
     "args": _schema({}), "handler": _t_inspect_reserved_identities},
    {"name": "inspect_plans",
     "description": "The authored plans for people, things and creatures: what each is for, what is true of it, where the clock has put it, and whether the Director has rendered it yet.",
     "args": _schema({"kind": _S}), "handler": _t_inspect_plans},
    {"name": "inspect_charters",
     "description": "The institutions the town simulates: posts, upkeeps, places and bodies. Name a charter for its full author-only diagnostics (beliefs, judgments, commitments, economy, refused interventions), and a body within it for that body's life.",
     "args": _schema({"charter": _S, "body": _S}), "handler": _t_inspect_charters},
    {"name": "inspect_events",
     "description": "The most recent objective beats as the engine recorded them, and every scheduled event still pending (authored events, charter events, couriers) with its due time.",
     "args": _schema({"n": _I}), "handler": _t_inspect_events},
    {"name": "inspect_clock",
     "description": "Where the story stands in time: the latest turn index, elapsed story seconds, the hour of the day, the day phase, and the scene's declared time of day.",
     "args": _schema({}), "handler": _t_inspect_clock},
    {"name": "inspect_config",
     "description": "The dials this story runs under, which the host owns and the room only reads: house style (genre, tone, what to avoid, weather, tense, day length), the scene's pacing and call budget, how many of the populace may speak in a beat and what earns a promotion, and whether minds may think off screen. Read it before proposing anything that leans on one, and when asked whether a change would land.",
     "args": _schema({}), "handler": _t_inspect_config},
    {"name": "inspect_needs",
     "description": "The open planning needs: what a beat reached for that no plan holds -- an unplanned destination, a query nobody answered, a person the Director rendered with no plan behind them. Each carries the surface the beat committed, which a plan may add to and never contradict.",
     "args": _schema({"kind": _S}), "handler": _t_inspect_needs},
    {"name": "inspect_contradictions",
     "description": "What the world holds that does not agree with itself: charter registry warnings, structure warnings, and dangling references (a planned exit to nowhere, a plan in no room, a bill in a vanished room, a need for a vanished room, a package participant nobody holds).",
     "args": _schema({}), "handler": _t_inspect_contradictions},
    {"name": "inspect_packages",
     "description": "The plot packages in this frame as spoiler-safe projections: status, revision, counts, clocks, operation kinds, validation verdict. Filter by status.",
     "args": _schema({"status": _S}), "handler": _t_inspect_packages},
    {"name": "read_package",
     "description": "One package in full when it is open, or its projection when sealed. reveal=true returns a sealed package's hidden text and is a host action.",
     "args": _schema({"uid": _S, "reveal": _B}, ["uid"]),
     "handler": _t_read_package, "host_only_args": ["reveal"]},
    # -- write, every one through a package ---------------------------------
    {"name": "new_package",
     "description": "Open a draft plot package: a title, an author-facing premise, open or sealed spoiler policy, a scope (locations, earliest/latest time) and an authority (what the package may do: create people, author prehistory, schedule harm). Everything the room wants to change in the world is drafted into a package and lands when it is published.",
     "args": _schema({"title": _S, "premise": _S, "spoiler_policy": _S,
                      "scope": _O, "authority": _O}, ["title"]),
     "handler": _t_new_package, "takes_actor": True},
    {"name": "edit_package",
     "description": "Change a draft's fields: title, premise, truths, questions, participants, evidence, pressures, clocks, opportunities, constraints, planner_requests, scope, authority, spoiler_policy. Evidence needs an origin, a location, the truth ids it bears_on and an admission_path. A published package accepts only a superseding truth ({supersedes: <truth id>, text}) with a reason.",
     "args": _schema({"uid": _S, "fields": _O, "reason": _S}, ["uid", "fields"]),
     "handler": _t_edit_package},
    {"name": "draft_operation",
     "description": "Add one typed operation to a draft. `operation` is an object whose `op` names the kind and whose other keys are that kind's fields (`?` marks an optional one): " + operation_shape_text() + ". request_location and presimulate are long (prepared before publish). Anything else is refused: the room writes the world only through these.",
     "args": _schema({"uid": _S, "operation": _O}, ["uid", "operation"]),
     "handler": _t_draft_operation},
    {"name": "remove_operation",
     "description": "Remove the operation at an index from a draft.",
     "args": _schema({"uid": _S, "index": _I}, ["uid", "index"]),
     "handler": _t_remove_operation},
    {"name": "preview_package",
     "description": "The cross-system diff a draft would make: per operation, what changes and what would refuse it, plus package-level checks (evidence that is evidence, clocks with a due, participants the world holds). Read-only.",
     "args": _schema({"uid": _S}, ["uid"]), "handler": _t_preview_package},
    {"name": "validate_package",
     "description": "Run the preview and record the verdict on the draft at its current revision. Publishing requires a passing validation at the revision being published.",
     "args": _schema({"uid": _S}, ["uid"]), "handler": _t_validate_package},
    {"name": "prepare_package",
     "description": "Run the LONG operations of a validated draft before publish -- a lived-location generation (a model call) or a presimulation -- each landing under its own guard. Required before publishing a package that carries one.",
     "args": _schema({"uid": _S}, ["uid"]), "handler": _t_prepare_package,
     "long": True},
    {"name": "publish_package",
     "description": "Land a validated, prepared draft in one short transaction. Pass the revision you validated; a different one is refused. If history moved under the package and it still validates, it is rebased and published; if it no longer validates, the conflict is returned and nothing lands. Visible to the story from the next turn.",
     "args": _schema({"uid": _S, "expected_revision": _I}, ["uid", "expected_revision"]),
     "handler": _t_publish_package},
    {"name": "resolve_package",
     "description": "Mark a published or active package resolved, with a note. What it placed in the world stays.",
     "args": _schema({"uid": _S, "note": _S}, ["uid"]), "handler": _t_resolve_package},
    {"name": "retire_package",
     "description": "Retire a package from any state, with a note. What a landed package placed in the world stays; retiring closes the file.",
     "args": _schema({"uid": _S, "note": _S}, ["uid"]), "handler": _t_retire_package,
     "host_only": True},
    # -- research (story/room_research.py): the web, under a `research`
    # mandate, disclosed in the thread, cached per story, usable only as
    # filed lore. Never handed to the Dramaturge (RESEARCH_TOOL_NAMES).
    *_research_tool_entries(_schema),
]

TOOL_INDEX = {tool["name"]: tool for tool in TOOLS}


def tool_manifest(*, include_host_only=False):
    """The model-facing table: name, description, argument schema, and the
    `long` / `host_only` marks. What the Story Planner is handed."""
    out = []
    for tool in TOOLS:
        if tool.get("host_only") and not include_host_only:
            continue
        entry = {"name": tool["name"], "description": tool["description"],
                 "args": tool["args"]}
        if tool.get("long"):
            entry["long"] = True
        if tool.get("host_only"):
            entry["host_only"] = True
        if tool.get("host_only_args"):
            entry["host_only_args"] = list(tool["host_only_args"])
        out.append(entry)
    return out


_TYPES = {"string": str, "integer": int, "boolean": bool, "object": dict,
          "array": list}


def _check_args(tool, args):
    schema = tool["args"]
    args = dict(args or {})
    props = schema["properties"]
    unknown = sorted(k for k in args if k not in props)
    if unknown:
        raise ToolError("%s takes no argument %s" % (tool["name"], ", ".join(unknown)))
    missing = [k for k in schema["required"] if k not in args]
    if missing:
        raise ToolError("%s requires %s" % (tool["name"], ", ".join(missing)))
    for key, value in args.items():
        if value is None:
            continue
        expected = _TYPES.get(props[key].get("type"))
        if expected is int and isinstance(value, bool):
            raise ToolError("%s.%s must be an integer" % (tool["name"], key))
        if expected and not isinstance(value, expected):
            raise ToolError("%s.%s must be a %s" % (tool["name"], key, props[key]["type"]))
    return args


def run_tool(cid, name, args=None, *, frame_id=None, host=False,
             actor="writers_room"):
    """The one call site. Checks the arguments against the tool's schema,
    refuses a host-only tool (or a host-only argument) unless ``host``,
    runs the handler, and caps the result at `TOOL_RESULT_CHARS` of JSON.
    A seam's ValueError is returned as the tool's refusal, not raised.
    ``actor`` names the caller -- the host by default, an agent by its name
    -- and reaches only the tools that record it (`takes_actor`)."""
    tool = TOOL_INDEX.get(str(name))
    if tool is None:
        raise ToolError("no tool %r" % name)
    if tool.get("host_only") and not host:
        raise ToolError("%s is a host action" % name)
    args = _check_args(tool, args)
    for key in tool.get("host_only_args") or ():
        if args.get(key) and not host:
            raise ToolError("%s.%s is a host action" % (name, key))
    if tool.get("takes_actor"):
        args["actor"] = str(actor or "writers_room")
    try:
        result = tool["handler"](cid, frame_id, **args)
    except ToolError:
        raise
    except ValueError as exc:
        return {"refused": str(exc)}
    encoded = json.dumps(result, ensure_ascii=False, default=str)
    if len(encoded) > TOOL_RESULT_CHARS:
        return {"truncated": True, "chars": len(encoded),
                "text": encoded[:TOOL_RESULT_CHARS]}
    return result
