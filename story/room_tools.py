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
from story.room_slice import containment as _containment
from story.room_slice import read_scene as _scene
from story.room_slice import room_graph as _room_graph

#: Result ceiling, in characters of JSON; past it trailing items are
#: dropped until the result fits (`fit_result`), and the result says how many
#: -- valid JSON, never a transcript, never longer than what it cut.
TOOL_RESULT_CHARS = 12_000
#: `search_lore` k ceiling; the default is the engine's own.
SEARCH_K_CAP = 12
SEARCH_K_DEFAULT = 6
#: Entries per `scan_lore` page.
SCAN_PAGE = 40
#: Characters of an entry's content shown in a listing (the full text is
#: `read_lore`).
EXCERPT_CHARS = 280
#: LIMITS THE OWNER SHOULD KNOW ABOUT. Recent events served by
#: `inspect_events` and the excerpt each is cut to: the ceiling, the default
#: when the caller names no `n`, and the excerpt (`full: true` lifts it).
#: Measured 2026-09-04 on chat 114: at 12 events of 600 characters the
#: result was a constant 7.8k wherever twelve events existed, on a tool the
#: Planner reads to orient, not to quote.
EVENTS_CAP = 40
EVENTS_DEFAULT = 6
EVENT_EXCERPT_CHARS = 240
#: Route length `inspect_route` will search (hops).
ROUTE_HOPS_CAP = 64
#: LIMITS THE OWNER SHOULD KNOW ABOUT (`inspect_charters`). The tool shows
#: an INSTITUTION -- its upkeeps against their floors, its posts, the watch
#: standing now, its bodies with place/station/home post/condition, and the
#: roster's beliefs where they differ from the bodies -- and every one of
#: those sections is PAGED rather than truncated: a page says how many rows
#: it withheld and the exact call that returns them.
#:
#: Measured, and the reason the shape changed (caravanserai, 2026-09-05):
#: the old tool answered with no post, no watch, no station and 24 of 40
#: bodies, and the Room asked to describe the house named the gate warden as
#: its innkeeper and invented three staff. A cap that silently drops half a
#: town is the defect, not the fix.
#:
#: `CHARTER_PAGE` is rows of each section when ONE charter is named;
#: `CHARTER_OVERVIEW_ROWS` is rows of each section per charter when none is
#: (a story with six institutions must still fit the 12,000-character result
#: cap, and `fit_result` cuts by dropping a whole top-level key, which would
#: lose every charter at once). `CHARTER_PAGE_CAP` is the most a caller may
#: ask for in one page.
CHARTER_PAGE = 24
CHARTER_OVERVIEW_ROWS = 8
CHARTER_PAGE_CAP = 200
#: The sections of an institution, each independently pageable.
CHARTER_SECTIONS = ("upkeeps", "posts", "watch", "bodies", "roster")
#: The old name, kept because `AGENTS.md` and the play report both cite it as
#: the cap that hid sixteen bodies. It is `CHARTER_PAGE` now.
BODIES_PER_CHARTER = CHARTER_PAGE
#: LIMITS THE OWNER SHOULD KNOW ABOUT (`inspect_minds`). The room reads a
#: mind as AUTHOR knowledge -- what a character wants and believes, so the
#: world it places can invite it -- not as the character's own payload, so
#: each ledger is cut to what planning needs and the rest is a count:
#: beliefs per mind (highest credence first), intentions per mind (active
#: first, then by priority), former projects and former drives kept, the
#: other people a mind holds models of (one leading claim per kind), and the
#: characters of any one prose field. Measured 2026-09-04 on chat 114 (one
#: cast member, seven beliefs, four intentions, no project, one other
#: person modelled under five kinds): 4,329 characters whole under these
#: caps, nothing cut, against the 12,000-character result cap -- so a cast
#: of three fits whole and the caps, not `fit_result`, decide what a larger
#: cast loses.
MIND_BELIEFS_CAP = 12
MIND_INTENTIONS_CAP = 6
MIND_FORMER_CAP = 3
MIND_OTHERS_CAP = 6
MIND_TEXT_CHARS = 240
#: Characters of the drive essence and each project aim in the one-line-per-
#: cast-member summary the Planner payload carries under `minds`
#: (`cast_minds_summary`), so the Planner knows to reach for the tool.
#: Measured 2026-09-04 on chat 114: 136 characters for the one cast member.
MIND_LINE_CHARS = 120
#: Owner-visible: authored values, traits and protected beliefs shown per
#: mind (each cut to MIND_LINE_CHARS). The card is author knowledge as much
#: as the ledger is -- read without it the Planner INVENTED a belief for a
#: character whose sheet stated the opposite (chat 116, 2026-09-04).
MIND_AUTHORED_ITEMS = 8


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


def _t_inspect_structures(cid, frame_id):
    """The planted structures, their planned rooms, and THE SPACES STILL
    HELD OPEN.

    A planner that cannot see the slot plans beside it, which is what the
    Harrowmere corpus measured: every duplicate room of that run was a plan
    built next to a stub standing for the same place. `frontiers` is
    `structure.frontier_spaces` -- the axis, the room it hangs off, and
    whether a provisional stub already stands there -- and its `room` and
    `axis` are what a `plan_rooms` room's `claims` field takes.
    """
    from core.db import wget_for_frame
    from world.structure import (STRUCTURES_KEY, frontier_spaces,
                                 normalize_structures, planned_room_ids)

    stored = normalize_structures(
        wget_for_frame(cid, STRUCTURES_KEY, None, {}) or {})
    planned = sorted(planned_room_ids(cid))
    return {"structures": stored["items"], "planned_rooms": planned,
            "frontiers": frontier_spaces(cid)}


def _t_inspect_rooms(cid, frame_id, *, room_ids=None):
    """The map and the neighbourhood, from ONE reader (`story/room_slice.py`).

    With no ``room_ids``: ``index`` is every room the story knows -- live,
    planned or retired, with its holder and its distance in hops from the
    cast -- and ``rooms`` is the slice of every room within
    `room_frontier.FRONTIER_DEPTH_HOPS` of the cast, planned stubs included.
    Everything farther is index-only and opened by id. With ``room_ids``:
    the slices of exactly those rooms, whatever their status.

    Why the split, measured on chat 114 (49 planned rooms): the flat read
    was 12,109 characters, over the cap, and the wrapper then handed back
    13,076 characters of cut JSON encoded as a string. And why one reader:
    this tool used to file a room carrying `parent_entity` under
    `containment` while the frontier reported the player standing in it
    (chat 115, `room_elevator_interior`), and the Planner planned a second
    lift car beside the one the cast was riding. The room a body stands in
    is a room whatever holds it; the index says who holds it and counts its
    hops through the holder's room.
    """
    from story.room_frontier import FRONTIER_DEPTH_HOPS
    from story.room_slice import attire_summary, room_index, room_slices

    def slices(ids):
        # The slice carries each occupant's attire ledger whole, for a
        # reader that renders a body; the tool carries the ledger's own
        # summary (`attire_summary`), because the ledger alone put five
        # rooms over the result cap.
        rows = room_slices(cid, frame_id, ids, scene)
        for row in rows:
            for who in row["occupants"]:
                who["attire"] = attire_summary(who["attire"])
        return rows

    scene = _scene(cid, frame_id)
    if room_ids:
        wanted = [str(r) for r in room_ids]
        rows = slices(wanted)
        known = {r["id"] for r in rows}
        out = {"location": scene.get("location"), "rooms": rows}
        unknown = [r for r in wanted if r not in known]
        if unknown:
            out["unknown"] = unknown
        return out
    index = room_index(cid, frame_id, scene)
    near = [row["id"] for row in index
            if row["hops"] is not None and row["hops"] <= FRONTIER_DEPTH_HOPS]
    return {"location": scene.get("location"), "index": index,
            "rooms": slices(near)}


def _t_inspect_route(cid, frame_id, *, from_room, to_room):
    scene = _scene(cid, frame_id)
    contained = _containment(scene)
    graph = _room_graph(cid, scene)
    origin, goal = str(from_room), str(to_room)
    if goal in contained:
        raise ToolError("%r is the inside of %s, not a place a route "
                        "reaches; where the world puts a body is the "
                        "Director's" % (goal, contained[goal]))
    # A route may START inside a body -- the player riding a lift car is
    # standing in a room whatever holds it -- and its first step is out,
    # into the room the holder stands in (`room_slice.room_graph`, which
    # joins an inside to its holder's room and to nothing else, so nothing
    # routes THROUGH one). It may not end in one.
    prefix = []
    start = origin
    if origin in contained:
        from story.room_slice import holder_room
        start = holder_room(scene, contained[origin])
        if not start:
            raise ToolError("%r is the inside of %s, which the story places "
                            "nowhere" % (origin, contained[origin]))
        prefix = [origin]
    if start not in graph and start not in (scene.get("rooms") or {}):
        raise ToolError("room %r exists nowhere" % start)
    if start == goal:
        return {"from": origin, "to": goal, "hops": len(prefix),
                "path": prefix + [goal]}
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
                    path = prefix + list(reversed(path))
                    return {"from": origin, "to": goal, "hops": len(path) - 1,
                            "path": path}
                nxt.append(other)
        frontier = nxt
        hops += 1
    return {"from": origin, "to": goal, "hops": None, "path": [],
            # An inside the walk stepped into is somewhere the story got to
            # and nowhere a route may end, so it is not offered as one.
            "reachable": sorted(r for r in seen
                                if r not in contained)[:LIST_CAP_ROUTE]}


LIST_CAP_ROUTE = 60


def _t_inspect_reserved_identities(cid, frame_id):
    """Every name the room may not reuse: registered characters, charter
    bodies, authored plans and their aliases. A charter body is its NAME
    here, under its charter: this tool answers "is the name taken", and a
    body's place, availability and post are `inspect_charters`' answer
    (measured 2026-09-04, chat 114: 9,137 of 9,677 characters were the
    same 66 bodies' place and availability that `inspect_charters` lists).

    The set itself is `plot_packages.reserved_identities`, which is what
    package validation compares a new name against: this tool REPORTS the
    reservation, it does not keep a second one (B19)."""
    from story.plot_packages import reserved_identities
    identities = reserved_identities(cid, frame_id)
    out = {"characters": [dict(row) for row in identities["cast"]],
           "charter_bodies": dict(identities["charter_bodies"]),
           "plans": [{"uid": plan["uid"], "kind": plan["kind"],
                      "name": plan["name"], "aliases": plan["aliases"],
                      "rendered": bool(plan.get("rendered"))}
                     for plan in identities["plans"].values()],
           "charter_bodies_note": "names under their charter; a body's place "
                                  "and availability are inspect_charters'"}
    if identities["charter_error"]:
        out["charter_bodies_error"] = identities["charter_error"]
    return out


def _t_inspect_plans(cid, frame_id, *, kind=None):
    from world.planned_entities import planned_entities
    plans = [p for p in planned_entities(cid, frame_id).values()
             if not kind or p["kind"] == str(kind)]
    return {"plans": plans}


def _charter_upkeep_rows(state):
    """Every condition the institution owes, against its floor, with the
    posts that tend it and who is standing them. `out_of_band` is the
    engine's own predicate, not a comparison restated here."""
    from world.charter import out_of_band
    posts = state.get("posts") or {}
    watch = state.get("watch") or {}
    bodies = state.get("bodies") or {}
    rows = []
    for key in sorted(state.get("upkeeps") or {}):
        upkeep = (state["upkeeps"] or {})[key]
        serving = sorted(p for p, post in posts.items()
                         if key in (post.get("serves") or ()))
        tending = [str((bodies.get(str(watch[p])) or {}).get("name")
                       or watch[p]) for p in serving if watch.get(p)]
        rows.append({
            "key": key, "place": upkeep.get("place") or "",
            "level": round(float(upkeep.get("level") or 0.0), 4),
            "floor": round(float(upkeep.get("floor") or 0.0), 4),
            "below_floor": bool(out_of_band(upkeep)),
            "drift_per_hour": upkeep.get("drift_per_hour"),
            "service_per_hour": upkeep.get("service_per_hour"),
            "depends_on": list(upkeep.get("depends_on") or ()),
            "requires": dict(upkeep.get("requires") or {}),
            "served_by": serving, "tended_by": tending,
        })
    return rows


def _charter_post_rows(state):
    """Every duty slot: where it is stood, what it is for, what it serves,
    which fixture of its room it is stood at, and who holds it now."""
    watch = state.get("watch") or {}
    bodies = state.get("bodies") or {}
    rows = []
    for key in sorted(state.get("posts") or {}):
        post = (state["posts"] or {})[key]
        holder = str(watch.get(key) or "")
        rows.append({
            "key": key, "place": post.get("place") or "",
            "purpose": post.get("purpose") or "",
            "serves": list(post.get("serves") or ()),
            "requires": dict(post.get("requires") or {}),
            "reports_to": post.get("reports_to") or "",
            "authority": list(post.get("authority") or ()),
            "anchor": post.get("anchor") or "",
            "held_by": holder,
            "held_by_name": str((bodies.get(holder) or {}).get("name") or holder),
        })
    return rows


def _charter_watch_rows(state):
    """WHO IS STANDING WHAT, right now, and which posts nobody is."""
    watch = state.get("watch") or {}
    posts = state.get("posts") or {}
    bodies = state.get("bodies") or {}
    standing = []
    for post in sorted(posts):
        body_key = str(watch.get(post) or "")
        if not body_key:
            continue
        held = bodies.get(body_key) or {}
        standing.append({
            "post": post, "body": body_key,
            "name": str(held.get("name") or body_key),
            "place": (posts.get(post) or {}).get("place") or "",
            "at": (posts.get(post) or {}).get("anchor") or "",
            "serves": list((posts.get(post) or {}).get("serves") or ()),
            "condition": held.get("condition") or "well",
        })
    return standing


def _charter_body_rows(state, charter_key, placements):
    """Every body with its place, its within-room station, its home post,
    the duty it is standing now, and its condition. ``placements`` is
    `charter_place.charter_placements` keyed by placement uid, so a body the
    scene can actually lay carries the station it is standing at."""
    from world.charter import placement_uid
    watch = state.get("watch") or {}
    standing = {str(b): p for p, b in watch.items() if b}
    rows = []
    for key in sorted(state.get("bodies") or {}):
        held = (state["bodies"] or {})[key]
        placed = placements.get(placement_uid(charter_key, key)) or {}
        row = {
            "key": key, "name": held.get("name") or key,
            "place": held.get("place") or "", "berth": held.get("berth") or "",
            "home_post": held.get("home_post") or "",
            "standing": standing.get(key, ""),
            "available": bool(held.get("available")),
            "condition": held.get("condition") or "well",
            "competence": dict(held.get("competence") or {}),
        }
        station = placed.get("station") or held.get("station")
        if station:
            row["station"] = station
            row["station_from"] = placed.get("source") or "authored"
        if placed.get("facing"):
            row["facing"] = placed["facing"]
        if held.get("departed"):
            row["departed"] = True
        if held.get("stood_down"):
            row["stood_down"] = True
        if held.get("walk"):
            row["walking_to"] = (held["walk"] or {}).get("target") or ""
        if held.get("errand"):
            row["errand"] = {"to": (held["errand"] or {}).get("to") or "",
                             "purpose": (held["errand"] or {}).get("purpose") or ""}
        rows.append(row)
    return rows


def _charter_roster_rows(state):
    """THE ROSTER'S BELIEFS WHERE THEY DIFFER FROM THE BODIES.

    A roster is what the institution BELIEVES about its people and it is
    allowed to be wrong: it improves by OBSERVATION and decays otherwise
    (`world/charter_roster.py`). Reading the difference is an AUTHOR act --
    the room reads objective truth, and the charter's own planner never sees
    this -- and it is the field that makes a town which learns of a death
    when somebody sees the body legible instead of looking like a bug.
    """
    from world.charter import stale_claims
    roster = state.get("roster") or {}
    bodies = state.get("bodies") or {}
    rows = []
    for key, why in sorted(stale_claims(roster, bodies)):
        record = roster.get(key) or {}
        held = bodies.get(key) or {}
        rows.append({
            "body": key, "name": str(held.get("name") or key),
            "differs": why,
            "believes": {
                "available": bool(record.get("believed_available")),
                "competence": dict(record.get("competence") or {}),
                "strength": round(float(record.get("strength") or 0.0), 4),
                "as_of_hours": record.get("as_of_hours"),
            },
            "in_fact": {} if why == "no such body" else {
                "available": bool(held.get("available")),
                "competence": dict(held.get("competence") or {}),
                "condition": held.get("condition") or "well",
            },
        })
    return rows


def _page(rows, cursor, limit, *, charter, section):
    """One page of a section, and -- when rows remain -- how many were
    withheld and the exact call that returns them. TRUNCATION IS THE DEFECT
    BEING FIXED: a caller that asks for more gets more."""
    total = len(rows)
    cursor = max(0, int(cursor or 0))
    page = rows[cursor:cursor + limit]
    if cursor + limit >= total:
        return page, None
    return page, {
        "withheld": total - (cursor + len(page)), "of": total,
        "next_cursor": cursor + len(page),
        "ask": "inspect_charters(charter=%r, section=%r, cursor=%d)"
               % (charter, section, cursor + len(page)),
    }


def _t_inspect_charters(cid, frame_id, *, charter=None, body=None,
                        section=None, cursor=0, limit=None):
    """The institution, legibly: its upkeeps against their floors, its posts
    with their places and what they serve, the watch standing now, every
    body with place, station, home post and condition, and the roster's
    BELIEFS where they differ from the bodies.

    MEASURED, AND THE REASON THIS SHAPE EXISTS (caravanserai, 2026-09-05):
    the old tool returned no post, no watch, no station and 24 of 40 bodies,
    so the Room asked to describe the house named the gate warden as its
    innkeeper and invented three staff who did not exist. A tool that hides
    the field the question is about is worse than no tool, because it
    answers confidently.

    PAGED, NEVER TRUNCATED. Each section is cut at a page and says how many
    rows were withheld and the exact call that returns them; ``section``
    plus ``cursor`` pages one of them. Naming a ``charter`` opens that one
    institution at the full page and adds its author-only diagnostics; a
    ``body`` within it adds that body's life.
    """
    from world.charter import charter_placements
    from world.charter_runtime import charter_diagnostics, registry_for
    registry = registry_for(cid, frame_id)
    items = registry.get("items") or {}
    if charter and str(charter) not in items:
        raise ToolError("no charter %r; the charters are %s"
                        % (charter, ", ".join(sorted(items)) or "none"))
    if section and str(section) not in CHARTER_SECTIONS:
        raise ToolError("no section %r; the sections are %s"
                        % (section, ", ".join(CHARTER_SECTIONS)))
    rows_per_page = _cap(limit, CHARTER_PAGE_CAP,
                         CHARTER_PAGE if charter else CHARTER_OVERVIEW_ROWS)
    try:
        placements = charter_placements(registry, _scene(cid, frame_id))
    except Exception:
        # A scene that cannot be read costs the station column, never the
        # institution: every other field here is the registry's own.
        placements = {}
    wanted = (str(section),) if section else CHARTER_SECTIONS
    summary = {}
    for key, item in sorted(items.items()):
        if charter and key != str(charter):
            continue
        state = item.get("state") or {}
        build = {
            "upkeeps": _charter_upkeep_rows, "posts": _charter_post_rows,
            "watch": _charter_watch_rows,
            "bodies": lambda s, k=key: _charter_body_rows(s, k, placements),
            "roster": _charter_roster_rows,
        }
        entry = {"key": key, "name": item.get("name") or state.get("key") or key,
                 "clock_hours": state.get("clock_hours"),
                 "places": sorted({str(p) for p in (
                     [b.get("place") for b in (state.get("bodies") or {}).values()]
                     + [p.get("place") for p in (state.get("posts") or {}).values()]
                     + [u.get("place") for u in (state.get("upkeeps") or {}).values()]
                 ) if p}),
                 "counts": {}, "withheld": {}}
        for name in CHARTER_SECTIONS:
            rows = build[name](state)
            entry["counts"][name] = len(rows)
            if name not in wanted:
                continue
            page, more = _page(rows, cursor if section else 0, rows_per_page,
                               charter=key, section=name)
            entry[name] = page
            if more:
                entry["withheld"][name] = more
        unfilled = sorted(p for p in (state.get("posts") or {})
                          if not (state.get("watch") or {}).get(p))
        entry["unfilled_posts"] = unfilled
        entry["counts"]["unfilled_posts"] = len(unfilled)
        if not entry["withheld"]:
            entry.pop("withheld")
        summary[key] = entry
    out = {"charters": summary, "sections": list(wanted),
           "rows_per_page": rows_per_page,
           "paging": "every section is paged, never truncated: `withheld` "
                     "names the rows held back and the call that returns them"}
    if charter:
        out["diagnostics"] = charter_diagnostics(
            cid, frame_id, charter_key=str(charter), body_key=str(body or ""))
    return out


def _t_inspect_events(cid, frame_id, *, n=None, full=False):
    """Recent objective beats (the omniscient row -- the room is an author)
    and every pending scheduled event. ``n`` beats, `EVENTS_DEFAULT` unless
    asked; each an `EVENT_EXCERPT_CHARS` excerpt unless ``full``."""
    from core.db import q
    count = _cap(n, EVENTS_CAP, EVENTS_DEFAULT)
    rows = q("SELECT e.id, e.content, t.idx AS turn_idx FROM events e "
             "LEFT JOIN turns t ON t.id=e.turn_id WHERE e.chat_id=? "
             "ORDER BY e.id DESC LIMIT ?", (cid, count))
    recent = [{"turn_idx": r["turn_idx"],
               "content": (" ".join(str(r["content"] or "").split()) if full
                           else _excerpt(r["content"], EVENT_EXCERPT_CHARS))}
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
    # WHAT THIS WORLD WRITES (D15): the kinds of objective event it has
    # actually recorded, with their counts, so a clock that waits on one can
    # be drafted against the vocabulary rather than against a guess.
    from story.plot_packages import world_event_kinds
    return {"recent": recent, "pending": pending,
            "event_kinds": world_event_kinds(cid, frame_id)}


def _t_inspect_clock(cid, frame_id):
    from core.db import q, wget_for_frame
    from world.day_cycle import DAY_LENGTH_HOURS_DEFAULT, phase_of_hour
    scene = _scene(cid, frame_id)
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
    holds, a clock past due on an active package, a clock waiting on a kind
    of event this world has never written (D15), two rooms of the registry
    that answer to one spelling, and a planted structure no live room can be
    walked to."""
    from story.artifacts import POSTED, standing_artifacts
    from story.plot_packages import packages
    from world.planned_entities import planned_entities
    from world.planning_needs import open_planning_needs
    from world.structure import planned_context, planned_room_ids
    scene = _scene(cid, frame_id)
    contained = _containment(scene)
    # A containment room is not a room the world is missing and not one a
    # thing can dangle in: it is a body's inside, transient by nature.
    rooms = set(scene.get("rooms") or {}) - set(contained)
    planned = set(planned_room_ids(cid))
    known = rooms | planned | set(contained)
    out = {"registry": [], "structure": [], "dangling": [], "layout": []}
    # THE LAYOUT LINT (`world/spatial_lint.py`): every standing row, not only
    # the ones that appeared this beat -- the commit reports appearance, the
    # Room reads the standing state. Reads bearings, extents, shapes and
    # placed cells; never prose.
    try:
        from world.spatial import room_layout_lint
        out["layout"] = _one_row_per_contradiction(room_layout_lint(scene))
    except Exception as exc:
        out["layout"] = [{"kind": "layout_unreadable", "error": str(exc)}]
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
        # The structure check asks whether a PLANNED room carries prose.
        # Handed every live room it called each developed room a
        # contradiction (chat 116, 2026-09-04: all five rooms the opening
        # developed from the plan). Only stubs still flagged `planned` are
        # the structure's planned rooms in the live scene.
        stubs = {rid: room for rid, room in (scene.get("rooms") or {}).items()
                 if isinstance(room, dict) and room.get("planned")}
        # And every OTHER live room is `known`: a plan may name a room that
        # already exists, and a live room is the least unknown thing in the
        # scene (PE8, 2026-09-05 -- two planned rooms opening onto the
        # landing were reported as three contradictions the Room had not
        # made).
        for key, structure in stored["items"].items():
            for w in structure_warnings(structure, stubs,
                                        known=(scene.get("rooms") or {})):
                if w.endswith("structure has no planned rooms"):
                    continue
                out["structure"].append("%s: %s" % (key, w))
    except Exception as exc:
        out["structure"] = ["structures unreadable: %s" % exc]
    # ASK THE TOPOLOGY, NOT THE RENDERING. `planned_context` exists to brief a
    # reader and renders each edge as the neighbour's DISPLAY NAME
    # (`names.get(uid, uid)`); this check then compared those names against a
    # set of room IDS, so every planned edge whose target had a display name
    # read as an exit to nowhere. Measured on the live chat 114 register: 83
    # dangling rows, 65 of them pure rendering artefact, for a plan that is
    # coherent. `planned_topology` returns the same edges as the ids they are
    # stored as, which is what a reachability question wants and removes the
    # mismatch at its source rather than translating back.
    #
    # It also stops depending on `planned_context` returning anything at all:
    # that function answers None whenever a query matches two rows, and its
    # match is a SUBSTRING test, so `guest_parking_lot` is ambiguous against a
    # room called `parking` and 30-odd rooms of this story's district resolve
    # to nothing. That is its own defect and is not repaired here.
    from world.structure import planned_topology

    for rid, edges in sorted(planned_topology(cid).items()):
        for other in edges:
            if str(other) in known:
                continue
            out["dangling"].append(
                {"kind": "planned_exit_to_nowhere", "room": rid, "to": other})
    # WHERE THE SCENE HAS ALREADY PUT WHAT THE PLAN IS STILL PROMISING.
    # A plan and a scene entity carrying its uid are the same thing written
    # twice, and the Director binds the second to the first through the
    # identity floor -- so once a mint carries `plan_ref`, the plan's `where`
    # is a claim about a thing the world has already placed. Measured live
    # (chat 114): the Room filed the TARDIS for the hibiscus garden at beat 6,
    # the Director stood it on the beach at beat 9 with `plan_ref` bound, and
    # `plan_in_no_room` passed the pair clean because `garden` is a perfectly
    # real planned room. Nothing anywhere compared the two, so the plan went
    # on offering a police box to a garden that already had none.
    rendered_at = {}
    for eid, ent in (scene.get("entities") or {}).items():
        if not isinstance(ent, dict):
            continue
        ref = ent.get("plan_ref")
        uid = str(ref.get("uid") or "") if isinstance(ref, dict) else ""
        if not uid:
            continue
        # Placed by a position row OR by being an anchor of the room it
        # stands in -- the live TARDIS is the second shape and has no
        # position at all, so reading only `room_of` compared nothing.
        from world.spatial import room_of
        where = room_of(scene, str(eid))
        if not where:
            for _rid, _room in (scene.get("rooms") or {}).items():
                if isinstance(_room, dict) and str(eid) in (
                        _room.get("anchors") or {}):
                    where = str(_rid)
                    break
        rendered_at[uid] = (str(eid), where or "")
    for plan in planned_entities(cid, frame_id).values():
        where = plan["brief"].get("where")
        if where and where not in known:
            out["dangling"].append({"kind": "plan_in_no_room", "uid": plan["uid"],
                                    "where": where})
        standing = rendered_at.get(plan["uid"])
        if standing and where and standing[1] and standing[1] != where:
            out["dangling"].append({
                "kind": "plan_rendered_elsewhere", "uid": plan["uid"],
                "name": plan.get("name") or "", "plan_says": where,
                "entity": standing[0], "actually_in": standing[1]})
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
    # ONE PART OF THE MAP IN TWO PIECES. Two live rooms the story files under
    # one region with no path between them -- over every declared edge and
    # the plan's topology -- are two rooms said to be one place and never
    # joined: what a Director-minted room standing beside the planned room it
    # duplicates looks like (chat 115's second lift car). A reachability
    # fact, never a name comparison (`world.regions.room_pieces`).
    try:
        from world.regions import registry_room_regions, room_pieces
        out["dangling"].extend(
            room_pieces(cid, scene, registry_room_regions(cid)))
    except Exception as exc:  # diagnostics only
        out["dangling"].append({"kind": "regions_unreadable", "error": str(exc)})
    out["dangling"].extend(_rooms_named_alike(cid))
    out["dangling"].extend(_structures_out_of_reach(cid, scene, contained))
    # NOBODY THE WORLD HOLDS IS ONE QUESTION. Both the reserved set and the
    # exemption for a participant the package itself plans live in
    # `plot_packages`; this lint read the registered cast alone and knew
    # nothing of the exemption, so it reported a charter body, an authored
    # plan (or its alias) and a package's own `plan_entity` subject as
    # strangers that validation had already accepted (B19, 2026-09-07).
    from story.plot_packages import (reserved_names, unheld_participants,
                                     world_event_kinds)
    reserved = reserved_names(cid, frame_id)
    # A CLOCK THAT NEVER TICKS SAYS SO (D15, owner ruling 2026-09-08). A
    # clock with `advance_on` waits on `world_events.kind` -- the one
    # vocabulary the world writes -- so a live clock that has filled nothing
    # and names no kind this world has ever written is a fuse that will sit
    # there for the rest of the story in silence. Data-driven, never a list
    # of kinds kept here: the world is asked what it writes.
    #
    # A world that has written NOTHING is not evidence of anything (D15
    # rework): an empty `world_events` is a young story, and reporting there
    # would flag the kind this engine writes on every consequence as if it
    # were a kind nothing writes. The lint speaks once the world has
    # recorded an event and that clock's kind is not among them; until then
    # `inspect_events` reports `event_kinds` as {} and says so plainly.
    written = None
    for pkg in packages(cid, frame_id).values():
        if pkg["status"] not in ("published", "active"):
            continue
        for name in unheld_participants(pkg, reserved):
            out["dangling"].append({"kind": "participant_nobody_holds",
                                    "package": pkg["uid"], "name": name})
        for clock in pkg["clocks"]:
            triggers = clock.get("advance_on") or []
            if not triggers or clock.get("fired_turn") is not None \
                    or clock.get("refused_turn") is not None:
                continue
            if int(clock.get("filled") or 0):
                continue
            if written is None:
                written = world_event_kinds(cid, frame_id)
            if not written:
                continue
            waits = sorted({str(t.get("event_kind") or "") for t in triggers})
            if set(waits) & set(written):
                continue
            out["dangling"].append(
                {"kind": "clock_waits_on_unwritten_event",
                 "package": pkg["uid"], "clock": clock["id"],
                 "waits_on": waits, "filled": 0,
                 "segments": clock.get("segments"),
                 "world_writes": sorted(written)})
    return out


#: A layout row about a PAIR of rooms says one thing about both of them, and
#: the lint walks the pair from each end -- so `rooms_overlap_when_placed`
#: arrived twice, once per ordering, and the Room read one contradiction as
#: two (PS6, solitude run turn 18, 2026-09-05). The row is keyed by the
#: unordered pair here rather than in the lint, because the tool is where a
#: reader asks "how many things are wrong".
_PAIRED_LAYOUT_KINDS = ("rooms_overlap_when_placed",)


def _one_row_per_contradiction(rows):
    """Layout rows with each PAIRED contradiction reported once."""
    seen, out = set(), []
    for row in rows or ():
        if not isinstance(row, dict) or row.get("kind") not in _PAIRED_LAYOUT_KINDS:
            out.append(row)
            continue
        key = (row["kind"], frozenset(str(r) for r in row.get("rooms") or ()),
               str(row.get("via") or ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _rooms_named_alike(cid):
    """Two rooms of the registry that answer to ONE spelling.

    THE REGISTRY IS THE LEDGER OF ROOM IDENTITY, so two rows in it under one
    spelling are two rooms the world says are one place -- and neither the
    story nor a reader can say which is meant. The comparison is over the
    spellings the registry ITSELF keeps (`normalize_room_id` of the uid, the
    name and every alias), not over prose: `planned_room_spellings` already
    treats a spelling two rooms share as naming neither, and this is the same
    fact reported instead of swallowed.

    The live case: `generate_lived_location` minted
    `vaunts_yard_waterfront_2_yard` beside the live `yard` it had been told
    to build onto, and eleven siblings with it; `inspect_contradictions`
    answered `structure: [], dangling: [], layout: []` while the yard stood
    empty for half the story (PM10/PM11, multitude run turns 8-9,
    2026-09-05).
    """
    from world.spatial import normalize_room_id
    from world.structure import registry_rows

    by_spelling = {}
    # Off the turn's one parse of the registry (C16), the same rows every
    # `planned_*` reader sees.
    for uid, entry in registry_rows(cid).items():
        for spelling in {normalize_room_id(uid),
                         normalize_room_id(entry["name"]),
                         *(normalize_room_id(str(a or ""))
                           for a in entry["aliases"] or ())}:
            if spelling:
                by_spelling.setdefault(spelling, set()).add(uid)
    return [{"kind": "rooms_named_alike", "spelling": spelling,
             "rooms": sorted(uids)}
            for spelling, uids in sorted(by_spelling.items())
            if len(uids) > 1]


def _structures_out_of_reach(cid, scene, contained):
    """A planted structure no live room can be walked to.

    A structure is a region of the map; a region no route joins to the rooms
    the story is standing in is a place nothing in the story can ever reach.
    A reachability fact over the same graph `inspect_route` walks, never a
    name comparison -- and it is what a host would have used to find the
    parallel town `generate_lived_location` planted beside the live yard
    (PM10/PM11, multitude run, 2026-09-05). A story whose scene holds no live
    room yet (the plan is all there is) reports nothing: there is nothing to
    be out of reach OF.
    """
    from core.db import wget_for_frame
    from world.structure import (STRUCTURES_KEY, normalize_structures,
                                 skeleton_rooms)

    live = {str(rid) for rid, room in (scene.get("rooms") or {}).items()
            if isinstance(room, dict) and not room.get("planned")
            and str(rid) not in contained}
    if not live:
        return []
    graph = _room_graph(cid, scene)
    seen, stack = set(live), list(live)
    while stack:
        for other in graph.get(stack.pop(), ()):
            if other not in seen:
                seen.add(other)
                stack.append(other)
    out = []
    stored = normalize_structures(
        wget_for_frame(cid, STRUCTURES_KEY, None, {}) or {})
    for key in sorted(stored["items"]):
        rooms = set(skeleton_rooms(cid, key).get("rooms") or {})
        if rooms and not (rooms & seen):
            out.append({"kind": "structure_out_of_reach", "structure": key,
                        "rooms": sorted(rooms)[:LIST_CAP_ROUTE]})
    return out


def _cut(text, limit=MIND_TEXT_CHARS):
    return _excerpt(text, limit)


def _mind_intentions(sheet, interior):
    """The intentions a character holds: the live ledger, plus any authored
    standing intention the ledger has not restated -- the same rule the
    character payload applies (`agents.character._merge_standing_intentions`),
    because an authored goal is always present and a live copy that restates
    it carries the progress."""
    from story.character_schema import character_standing_intentions
    live = [i for i in (interior.get("intentions") or []) if isinstance(i, dict)]
    seen = {str(i.get("intent") or "").strip().casefold() for i in live}
    authored = [a for a in character_standing_intentions(sheet)
                if str(a.get("intent") or "").strip().casefold() not in seen]
    return authored + live


def _mind_projects(sheet, interior):
    """Held projects: the live ledger once commit has seeded it, the authored
    card list only before any live or former project exists -- the character
    payload's own rule, so a project given up out loud never reads as held."""
    from story.character_schema import character_projects
    if interior.get("projects") or interior.get("former_projects"):
        return [p for p in (interior.get("projects") or []) if isinstance(p, dict)]
    return character_projects(sheet)


def _loads(text):
    try:
        value = json.loads(text or "{}")
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _mind_of(row, turn_idx):
    """One cast member's mind, read through the engine's own readers and cut
    to author knowledge. Nothing here is derived from raw rows that a reader
    does not already derive: the drive is `effective_drive` (the rupture-
    shifted one when there is one), the ledgers are the interior commit
    writes (`persist/commit_memory.py`), stress is the resolved row
    (`psychology_runtime.resolve_stress`), and what this mind holds of other
    people is `theory_of_mind.mind_models_for_payload` with no competitors."""
    from mind.affect import CRISIS_STRAIN_MIN, RUPTURE_STRAIN_MIN
    from mind.theory_of_mind import mind_models_for_payload
    from story.character_schema import character_psychology, effective_drive
    sheet = _loads(row["sheet"])
    state = _loads(row["cstate"])
    interior = state.get("interior") if isinstance(state.get("interior"), dict) else {}
    active = state.get("active_state") if isinstance(state.get("active_state"), dict) else {}

    drive = effective_drive(character_psychology(sheet), interior)
    out_drive = {k: _cut(drive.get(k)) for k in ("essence", "expression", "taboo")}
    override = interior.get("drive_override")
    if isinstance(override, dict) and str(override.get("essence") or "").strip():
        out_drive["shifted"] = {"since_turn": override.get("since_turn"),
                                "by_event": _cut(override.get("by_event"))}
    former_drives = [{"essence": _cut(d.get("essence")),
                      "ended_turn": d.get("ended_turn"),
                      "by_event": _cut(d.get("by_event"))}
                     for d in (interior.get("former_drives") or [])
                     if isinstance(d, dict)][-MIND_FORMER_CAP:]

    try:
        strain = float(interior.get("drive_strain") or 0.0)
    except (TypeError, ValueError):
        strain = 0.0
    rupture = interior.get("drive_rupture")
    log = [e for e in (interior.get("strain_log") or []) if isinstance(e, dict)]
    out_strain = {
        "drive_strain": round(strain, 3),
        "at_rupture_level": strain >= RUPTURE_STRAIN_MIN,
        "crisis": strain >= CRISIS_STRAIN_MIN,
        "rupture_window": ({"direction": rupture.get("direction"),
                            "why": _cut(rupture.get("why")),
                            "window_expires": rupture.get("window_expires")}
                           if isinstance(rupture, dict) else None),
        "last_moved_by": ({"source": log[-1].get("source"),
                           "delta": log[-1].get("delta"), "turn": log[-1].get("turn"),
                           "why": _cut(log[-1].get("why"))} if log else None),
    }
    stress = active.get("stress") if isinstance(active.get("stress"), dict) else {}
    out_stress = {k: stress.get(k) for k in
                  ("activation", "strain", "load", "overloaded", "coping_mode")
                  if k in stress}

    projects = []
    for p in _mind_projects(sheet, interior):
        entry = {"id": p.get("id"), "aim": _cut(p.get("project")),
                 "about": p.get("about") or "",
                 "satisfied_when": _cut(p.get("satisfied_when")),
                 "status": "probation" if p.get("probation") else "established",
                 "adopted_turn": p.get("adopted_turn"),
                 "last_served_turn": p.get("last_served_turn")}
        if isinstance(turn_idx, int) and isinstance(p.get("last_served_turn"), int):
            entry["unserved_beats"] = max(0, turn_idx - int(p["last_served_turn"]))
        projects.append(entry)
    former_projects = [{"id": p.get("id"), "aim": _cut(p.get("project")),
                        "end": p.get("end"), "why": _cut(p.get("why")),
                        "turn": p.get("turn")}
                       for p in (interior.get("former_projects") or [])
                       if isinstance(p, dict)][-MIND_FORMER_CAP:]
    review = interior.get("project_review")

    ranked = sorted(_mind_intentions(sheet, interior),
                    key=lambda i: (0 if (i.get("status") or "active") == "active" else 1,
                                   -float(i.get("priority") or 0.0)))
    intentions = []
    for i in ranked[:MIND_INTENTIONS_CAP]:
        entry = {"id": i.get("id"), "intent": _cut(i.get("intent")),
                 "status": i.get("status") or "active",
                 "progress": i.get("progress"), "priority": i.get("priority"),
                 "authored": bool(i.get("authored"))}
        if isinstance(turn_idx, int) and isinstance(i.get("last_progress_turn"), int):
            entry["idle_beats"] = max(0, turn_idx - int(i["last_progress_turn"]))
        intentions.append(entry)

    beliefs = sorted((b for b in (interior.get("beliefs") or []) if isinstance(b, dict)),
                     key=lambda b: -float(b.get("confidence") or 0.0))
    out_beliefs = [{"belief": _cut(b.get("belief")),
                    "confidence": b.get("confidence"),
                    "protected": bool(b.get("protected")),
                    "authored": bool(b.get("authored"))}
                   for b in beliefs[:MIND_BELIEFS_CAP]]

    models = mind_models_for_payload(state.get("mind_models"), turn_idx,
                                     max_competitors=0)
    others = {}
    for about, kinds in list(models.items())[:MIND_OTHERS_CAP]:
        others[about] = {kind: {"claim": _cut(v["leading"].get("claim")),
                                "confidence": v["leading"].get("confidence")}
                         for kind, v in kinds.items() if isinstance(v, dict)}

    psych = character_psychology(sheet)
    self_model = psych.get("self_model") if isinstance(psych.get("self_model"), dict) else {}

    def _authored_list(items):
        out_items = []
        for item in (items or [])[:MIND_AUTHORED_ITEMS]:
            if isinstance(item, dict):
                text = " ".join(str(v) for k, v in item.items()
                                if k in ("name", "value", "text", "belief", "trait")
                                and str(v or "").strip()) or json.dumps(item, ensure_ascii=False)
                strength = item.get("strength") if "strength" in item else item.get("weight")
                if strength is not None:
                    text = "%s (%s)" % (text, strength)
            else:
                text = str(item)
            text = " ".join(text.split())
            if text:
                out_items.append(text if len(text) <= MIND_LINE_CHARS
                                 else text[:MIND_LINE_CHARS - 1] + "…")
        return out_items

    authored = {
        "self_model": _cut(self_model.get("summary")),
        "values": _authored_list(psych.get("values")),
        "traits": _authored_list(psych.get("traits")),
        "protected_beliefs": _authored_list(self_model.get("protected_beliefs")),
    }

    mind = {
        "id": row["id"], "name": row["name"],
        "drive": out_drive,
        "authored": authored,
        "former_drives": former_drives,
        "strain": out_strain,
        "stress": out_stress,
        "goal": _cut(active.get("goal")),
        "projects": projects,
        "former_projects": former_projects,
        "intentions": intentions,
        "beliefs": out_beliefs,
        "about_others": others,
        "counts": {"beliefs": len(beliefs), "intentions": len(ranked),
                   "former_projects": len(interior.get("former_projects") or []),
                   "former_drives": len(interior.get("former_drives") or []),
                   "others_modelled": len(models)},
    }
    if isinstance(review, dict):
        mind["project_review"] = {"why": _cut(review.get("why")),
                                  "turn": review.get("turn")}
    return mind


def _t_inspect_minds(cid, frame_id, *, name=None):
    """What each attached cast member wants and believes, as AUTHOR knowledge
    (the module docstring: the room may read what no mind may, and reading
    puts nothing in anyone's head). READ-ONLY by construction -- it opens
    the rows `scene.active_cast` resolves (the per-story card over the
    reusable one; the frame's state over the base row) and writes nothing;
    its handler is reachable only through `run_tool`, and no pipeline stage
    imports this module (`tests/test_room_minds.py`)."""
    from core.db import q
    from story.scene import active_cast
    row = q("SELECT MAX(idx) AS idx FROM turns WHERE chat_id=?", (cid,), one=True)
    turn_idx = row["idx"] if row and row["idx"] is not None else None
    cast = active_cast(cid, frame_id)
    if name is not None:
        wanted = str(name).strip().casefold()
        cast = [r for r in cast if str(r["name"] or "").strip().casefold() == wanted]
        if not cast:
            raise ToolError("no attached cast member named %r" % name)
    return {"turn_idx": turn_idx,
            "minds": [_mind_of(r, turn_idx) for r in cast],
            "note": "author knowledge: what each wants and believes, so the "
                    "world you place can invite it; nothing here is a thing "
                    "you can place"}


def cast_minds_summary(cid, frame_id):
    """One line per attached cast member -- the drive's essence and the aim
    of each held project -- for the Planner payload's `minds` key, so the
    Planner knows what `inspect_minds` would answer before it reaches. Each
    prose field is cut to `MIND_LINE_CHARS`. An empty list with no cast."""
    from story.character_schema import character_psychology, effective_drive
    from story.scene import active_cast
    out = []
    for row in active_cast(cid, frame_id):
        sheet = _loads(row["sheet"])
        state = _loads(row["cstate"])
        interior = state.get("interior") if isinstance(state.get("interior"), dict) else {}
        drive = effective_drive(character_psychology(sheet), interior)
        out.append({"name": row["name"],
                    "drive": _cut(drive.get("essence"), MIND_LINE_CHARS),
                    "projects": [_cut(p.get("project"), MIND_LINE_CHARS)
                                 for p in _mind_projects(sheet, interior)]})
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
     "reads": True,
     "handler": _t_search_lore},
    {"name": "read_lore",
     "description": "Read one lore entry in full by its numeric id, including its provenance note. Only entries in books attached to this story are readable.",
     "args": _schema({"entry_id": _I}, ["entry_id"]), "reads": True,
     "handler": _t_read_lore},
    {"name": "scan_lore",
     "description": "Page through the attached lorebooks in id order, optionally one book or one category at a time. Returns excerpts and a next_cursor when more remain.",
     "args": _schema({"book_id": _I, "category": _S, "cursor": _I, "limit": _I}),
     "reads": True,
     "handler": _t_scan_lore},
    {"name": "inspect_structures",
     "description": "The planted structures (settlements, buildings), every planned room id the registry holds -- the town's own topology, which a beat may furnish and may not delete -- and `frontiers`, the spaces the plan is still holding open: each is an axis, the room it hangs off, and whether it is `open` (nothing minted there yet) or `provisional` (a stub stands in it, named from the structure's grammar, until a plan claims it). To fill one, plan a room with `claims: {room, axis}` copied from the row: the space BECOMES that room -- same id, so every edge and everything standing in it survives -- instead of a second room beside it. A room the story has already been in keeps the name it is known by and takes the rest.",
     "args": _schema({}), "reads": True,
     "handler": _t_inspect_structures},
    {"name": "inspect_rooms",
     "description": "The map and the neighbourhood. With no arguments: `index` is every room the story knows -- live, planned (a stub nobody has entered) or retired (an id that is spent) -- with its holder when it is the inside of a body, its `region` (the part of the map it belongs to; the index is grouped by it, the cast's region first) and its distance in hops from the cast; `rooms` is the full slice of every room within two hops (description, exits with barriers, who stands there and in what, what stands there, the plan's brief for a stub, and what the author layer already claims for it: planned entities, open needs, package operations). Everything farther is index-only: pass room_ids to open any rooms by id, whatever their status. The room a body stands in is a room whatever holds it.",
     "args": _schema({"room_ids": _SL}),
     "reads": True,
     "handler": _t_inspect_rooms},
    {"name": "inspect_route",
     "description": "Whether one room can be walked to from another over the edges a body could cross -- a closed door is a hop, not a wall -- and the plan's topology, and the shortest path if so. When unreachable, lists what IS reachable from the start.",
     "args": _schema({"from_room": _S, "to_room": _S}, ["from_room", "to_room"]),
     "reads": True,
     "handler": _t_inspect_route},
    {"name": "inspect_reserved_identities",
     "description": "Every name the room may not reuse: the registered characters, every charter body's name under its charter, and every authored plan with its aliases. A new person must not collide with any of these. Names only: a body's place, availability and post are inspect_charters' answer.",
     "args": _schema({}), "reads": True,
     "handler": _t_inspect_reserved_identities},
    {"name": "inspect_plans",
     "description": "The authored plans for people, things and creatures: what each is for, what is true of it, where the clock has put it, and whether the Director has rendered it yet.",
     "args": _schema({"kind": _S}), "reads": True,
     "handler": _t_inspect_plans},
    {"name": "inspect_charters",
     "description": "The institutions the town simulates, as institutions: `upkeeps` (each condition it owes, its level against its floor, whether it is below it, what it drifts and what it depends on, the posts that serve it and who is tending it), `posts` (place, purpose, what it serves, what it requires, who it reports to, the fixture it is stood at, and who holds it), `watch` (who is standing what, right now) with `unfilled_posts`, `bodies` (place, within-room station, berth, home post, the duty being stood now, availability, condition, and any walk or errand under way), and `roster` -- what the institution BELIEVES about its people where that differs from the bodies, because a roster improves by observation and decays otherwise, so a town learns of a death when somebody sees the body. Every section is PAGED, never truncated: `withheld` names how many rows were held back and the exact call that returns them; pass section and cursor to page one. Name a charter for that one institution at a fuller page plus its author-only diagnostics (beliefs, judgments, commitments, economy, refused interventions), and a body within it for that body's life.",
     "args": _schema({"charter": _S, "body": _S, "section": _S, "cursor": _I,
                      "limit": _I}),
     "reads": True,
     "handler": _t_inspect_charters},
    {"name": "inspect_events",
     "description": "The most recent objective beats as the engine recorded them (the last few, each as a short excerpt; pass n for more and full=true for the whole record of each), every scheduled event still pending (authored events, charter events, couriers) with its due time, and under event_kinds the kinds of objective event this world has actually written, with their counts -- the vocabulary a package clock's advance_on waits on.",
     "args": _schema({"n": _I, "full": _B}), "reads": True,
     "handler": _t_inspect_events},
    {"name": "inspect_clock",
     "description": "Where the story stands in time: the latest turn index, elapsed story seconds, the hour of the day, the day phase, and the scene's declared time of day. Your payload already carries this under `clock`, rebuilt every step; a call is answered with that key, not a copy.",
     "args": _schema({}), "reads": True,
     "handler": _t_inspect_clock, "payload_key": "clock"},
    {"name": "inspect_config",
     "description": "The dials this story runs under, which the host owns and the room only reads: house style (genre, tone, what to avoid, weather, tense, day length), the scene's pacing and call budget, how many of the populace may speak in a beat and what earns a promotion, and whether minds may think off screen. Read it before proposing anything that leans on one, and when asked whether a change would land.",
     "args": _schema({}), "reads": True,
     "handler": _t_inspect_config},
    {"name": "inspect_needs",
     "description": "The open planning needs: what a beat reached for that no plan holds -- an unplanned destination, a query nobody answered, a person the Director rendered with no plan behind them. Each carries the surface the beat committed, which a plan may add to and never contradict.",
     "args": _schema({"kind": _S}), "reads": True,
     "handler": _t_inspect_needs},
    {"name": "inspect_contradictions",
     "description": "What the world holds that does not agree with itself: charter registry warnings, structure warnings, and dangling references (a planned exit to nowhere, a plan in no room, a bill in a vanished room, a need for a vanished room, a package participant nobody holds, a region whose live rooms are in pieces no path joins -- a possible duplicate room, two rooms of the registry that answer to one spelling, a planted structure no live room can be walked to), and `layout`: where the rooms' geometry cannot all be true (two sides of one doorway naming bearings that are not opposites, rooms that land on top of each other when placed by their bearings, a wall whose anchors need more paces than its extent holds, two doorways placed on one cell, a shape that contradicts itself).",
     "args": _schema({}), "reads": True,
     "handler": _t_inspect_contradictions},
    {"name": "inspect_minds",
     "description": "What a character wants and believes, so the world you place can invite it; you cannot place a want or a belief. For each attached cast member (or the one named): the drive that survives every goal (its essence, how it shows, what it will not do; whether a rupture shifted it and what it was before), how strained that drive is and whether a rupture window is open, the resolved stress, the current beat goal, the held projects (aim, criterion, probation, how long unserved) and the ones given up with the stated reason, the standing and formed intentions with their progress, the beliefs by credence, and the leading claim this mind holds about each other person. Author knowledge, read the way the pipeline drawer reads it: nothing here reaches a mind by being read, and nothing you place may name what a character will conclude from it.",
     "args": _schema({"name": _S}), "reads": True,
     "handler": _t_inspect_minds},
    {"name": "inspect_packages",
     "description": "The plot packages in this frame as spoiler-safe projections: status, revision, counts, clocks, operation kinds, validation verdict. Filter by status. Your payload already carries every package under `packages`, rebuilt every step; a call is answered with that key, not a copy.",
     "args": _schema({"status": _S}), "reads": True,
     "handler": _t_inspect_packages,
     "payload_key": "packages"},
    {"name": "read_package",
     "description": "One package in full when it is open, or its projection when sealed. reveal=true returns a sealed package's hidden text and is a host action.",
     "args": _schema({"uid": _S, "reveal": _B}, ["uid"]),
     "reads": True,
     "handler": _t_read_package, "host_only_args": ["reveal"]},
    # -- write, every one through a package ---------------------------------
    {"name": "new_package",
     "description": "Open a draft plot package: a title, an author-facing premise, open or sealed spoiler policy, a scope (locations, earliest/latest time) and an authority (what the package may do: create people, author prehistory, schedule harm). Everything the room wants to change in the world is drafted into a package and lands when it is published.",
     "args": _schema({"title": _S, "premise": _S, "spoiler_policy": _S,
                      "scope": _O, "authority": _O}, ["title"]),
     "handler": _t_new_package, "takes_actor": True},
    {"name": "edit_package",
     "description": "Change a draft's fields: title, premise, truths, questions, participants, evidence, pressures, clocks, opportunities, constraints, planner_requests, scope, authority, spoiler_policy. A truth is a fact about the WORLD; give it known_by ([the names of the minds this fact is already inside, or `player` for the player's own character]) when somebody already holds it, and leave known_by off when nobody does. Everyone else reaches it through evidence, which needs an origin, a location, the truth ids it bears_on and an admission_path. A published package accepts only a superseding truth ({supersedes: <truth id>, text}) with a reason. A clock is due by TIME (due_turns from publish, or due_story_hours) or by WHAT HAPPENS: give it advance_on ([{event_kind, location_id?}] -- the kinds of objective event that fill it, which inspect_events lists under event_kinds for this world) and segments (how many fillings it takes, 1 unless you say otherwise), and it fires when they are filled. A clock with neither a due nor an advance_on never fires, and a clock waiting on a kind this world does not write is warned about at validation.",
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


def tool_only_reads(name):
    """Whether running ``name`` can leave the database saying anything
    different. A tool the table marks ``reads`` cannot; ANYTHING ELSE CAN.

    The default is the point (review 2026-09-07, C21). The Room's agents
    hold a per-reply memo of the half of their payload that comes out of
    the database (`room_calls.ReplyMemo`), and a tool that writes is what
    drops it. An unknown name, an unmarked entry, a tool somebody adds next
    year: each counts as a writer, so the memo is dropped for nothing at
    worst, and a stale frontier is never served for the rest of a reply.
    The research tools are deliberately unmarked -- they disclose into the
    thread and fill a cache -- and so is `preview_package`, whose reads are
    pure but whose neighbours in the table are not.
    """
    tool = TOOL_INDEX.get(str(name))
    return bool(tool) and bool(tool.get("reads"))


def tool_manifest(*, include_host_only=False):
    """The model-facing table: name, description, argument schema, and the
    `long` / `host_only` / `payload_key` marks. What the Story Planner is
    handed. `payload_key` names the key of the Planner's per-step payload
    that already carries the tool's answer; the loop echoes the key instead
    of a second copy (`agents/story_planner.run_planner`)."""
    out = []
    for tool in TOOLS:
        if tool.get("host_only") and not include_host_only:
            continue
        entry = {"name": tool["name"], "description": tool["description"],
                 "args": tool["args"]}
        if tool.get("long"):
            entry["long"] = True
        if tool.get("payload_key"):
            entry["payload_key"] = tool["payload_key"]
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
    result = fit_result(result, TOOL_RESULT_CHARS)
    # Every row this reply has actually read, remembered here because this
    # is the one call site every read passes through. It is what a claim in
    # the reply is checked against (`story/room_citations.py`): the room may
    # state as fact what it read, and must offer anything else as a
    # proposal. Cut rows are not remembered -- `fit_result` ran first, so
    # what the room could not see it cannot cite.
    from story.room_citations import note_reads
    note_reads(name, result)
    return result


def _encoded_length(value):
    return len(json.dumps(value, ensure_ascii=False, default=str))


def fit_result(result, cap):
    """The result under ``cap`` characters of JSON, as JSON.

    Past the cap, trailing items are dropped from the result's top-level
    lists -- the longest (by encoded size) first, one item at a time -- and
    when no list has an item left, whole top-level keys, largest first. The
    returned value carries ``truncated: true`` and ``dropped: <count>`` and
    is never longer than the original. The old wrapper re-encoded the cut
    JSON AS A STRING, so what it returned was both larger than the result it
    was cutting (12,109 -> 13,076 characters on chat 114's room read) and
    unparseable by the model it was cut for. A tool that orders its lists
    nearest-first (`inspect_rooms`) therefore loses the farthest rooms.

    THE CUT IS COUNTED, NOT RE-ENCODED (review 2026-09-07, C21). Choosing
    each item to drop re-serialized the whole result and every top-level
    value again, so cutting a result to size cost the encoder one full pass
    PER DROPPED ITEM -- quadratic in exactly the case the cut exists for.
    Measured on the bench copy of chat 114: `inspect_charters` fell from
    30,988 characters in 6 drops and spent 11.3 ms doing it. Sizes are
    composed instead: JSON writes a dict as ``{`` + ``"k": v`` joined by
    ``", "`` + ``}`` and a list the same way, so a container's length is its
    parts' lengths plus its punctuation, and dropping the last item of a
    list subtracts that item's length and its separator. Same arithmetic,
    same choices, same bytes out.
    """
    if not isinstance(result, dict):
        return result
    original = _encoded_length(result)
    if original <= cap:
        return result
    out = json.loads(json.dumps(result, ensure_ascii=False, default=str))
    out["truncated"] = True
    out["dropped"] = 0
    # Every top-level value's encoded length, and every list's per-item
    # lengths, measured once. `_joined` composes a container's length from
    # them, which is what json.dumps would have answered.
    items = {k: [_encoded_length(e) for e in v] if isinstance(v, list) else None
             for k, v in out.items()}
    sizes = {k: _joined(items[k], 2) if items[k] is not None
             else _encoded_length(v) for k, v in out.items()}

    def _total():
        sizes["dropped"] = _encoded_length(out["dropped"])
        return _joined([_encoded_length(k) + 2 + sizes[k] for k in out], 2)

    while _total() > cap:
        lists = [(k, sizes[k]) for k, v in out.items()
                 if isinstance(v, list) and v]
        if lists:
            key = max(lists, key=lambda kv: kv[1])[0]
            out[key].pop()
            gone = items[key].pop()
            sizes[key] -= gone + (2 if items[key] else 0)
        else:
            keys = [(k, sizes[k]) for k in out
                    if k not in ("truncated", "dropped")]
            if not keys:
                break
            key = max(keys, key=lambda kv: kv[1])[0]
            out.pop(key)
            sizes.pop(key)
            items.pop(key)
        out["dropped"] += 1
    return out


def _joined(lengths, punctuation):
    """The encoded length of a JSON container holding parts of these
    lengths: the two brackets plus the parts plus ``", "`` between them."""
    lengths = list(lengths)
    return punctuation + sum(lengths) + 2 * max(0, len(lengths) - 1)
