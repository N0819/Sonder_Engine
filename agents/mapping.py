"""The world-context compiler: lore routing and retrieval, deterministic.

`compile_world_context` is what the two mapping model stages used to be. It
assembles, with no model call, what they assembled -- the beat's relevant
lore from the story's own rows, the books that lore came from, the owed
history a place has accrued, the plan's brief for a room the beat named,
and the movement classification the cached-recall stage did cheaply -- and
it refuses the one thing they also did: inventing. Where `mapping_stage`
staged a room for a door the plan had not drawn, the compiler emits a typed
PLANNING NEED (`world/planning_needs.py`) and the Director renders the
surface the beat perceived, the way it renders an unplanned frontier stub.
The creative fallback belongs to the Writers' Room (v2 § 9.3), and until
the room exists a deterministic fill answers the need at commit.

Every reader of the old stages' output keeps its keys: `relevant_lore`,
`relevant_books`, `staged_lore` (always empty now) and `scene_patch` (always
the empty containers). `PipelineContext.world_context()` is the one read.
"""

from __future__ import annotations

from core.db import wget
from mind.memory import search_lore
from story.scene import (
    cast_scene_context,
    get_scene,
    recent_events,
)

from .common import (
    _books,
    _book_weights,
    _join_text,
    _lore_fingerprint,
    _normalize_scene_patch,
)

#: Candidates retrieved for a beat -- the full stage's `k`.
WORLD_CONTEXT_LORE_K = 14
#: Entries carried on the step after the cache merge -- the quick stage's cap.
WORLD_CONTEXT_LORE_CAP = 12
#: Recent beats folded into the retrieval query -- the full stage's window.
WORLD_CONTEXT_RECENT_EVENTS = 5

#: The fields a relevant-lore row carries onto the step. The engine's own
#: rows, verbatim -- there is no model echo to join any more, which was the
#: transcription that lost sentences in 13.6% of 855 measured entries.
LORE_ROW_FIELDS = (
    "id", "entry_uid", "book_id", "keys", "content", "category", "locked")


def _lore_row(hit):
    return {field: hit.get(field) for field in LORE_ROW_FIELDS if field in hit}


def _query(ctx, interp):
    chat = ctx.chat
    fl = interp.get("flow") or {}
    pieces = [e.get("text") or e.get("attempt") or ""
              for e in (interp.get("sequence") or []) if isinstance(e, dict)]
    pieces += [fl.get("mapping_request") or "",
               interp.get("location_query") or "", ctx.input or ""]
    # Frame-scoped and scrubbed (audit X18): a routing stage is never
    # entitled to the omniscient events row.
    pieces += recent_events(chat["id"], WORLD_CONTEXT_RECENT_EVENTS)
    if not interp:
        # The opening: no interpretation yet, so the scenario and the cast's
        # public surface are the query.
        pieces += [chat.get("scenario") or ""]
        for actor in cast_scene_context(ctx.cast):
            pieces.extend([
                actor["name"],
                actor["public_history"],
                actor["opening_context"],
                " ".join(str(ab.get("name") or "") for ab in actor["abilities"]
                         if isinstance(ab, dict)),
                " ".join(str(ab.get("notes") or "") for ab in actor["abilities"]
                         if isinstance(ab, dict)),
            ])
    return _join_text(pieces)


def classify_movement(interp, scene, *, planned_for):
    """Where the beat is going, and whether the world has it.

    ``planned_for(query)`` answers with the plan's record for a room the
    plan holds under that spelling, or None. Returns
    ``{"to_room", "status"}`` with status one of ``known`` (a scene room),
    ``planned`` (the plan holds it; the Director furnishes it on entry),
    ``unplanned`` (neither -- a planning need), or ``None`` when the beat
    declares no destination. This is the classification `mapping_quick`
    made to decide whether to escalate; it is now a fact on the step.
    """
    mv = interp.get("movement") if isinstance(interp, dict) else None
    target = mv.get("to_room") if isinstance(mv, dict) else None
    if not target:
        return {"to_room": None, "status": None}
    target = str(target)
    if target in ((scene or {}).get("rooms") or {}):
        return {"to_room": target, "status": "known"}
    if planned_for(target):
        return {"to_room": target, "status": "planned"}
    return {"to_room": target, "status": "unplanned"}


def _location_query_status(query, scene, *, planned_for, destination=None):
    """A location query is answered by the scene, by the plan, or by nobody.

    The Director writes the query as a DESCRIPTION, not an id -- "Reeve's
    Hall interior and occupants", "Ford Inn kitchen Harrowmere" (21 of 21
    on the Harrowmere replay named a room this way and none was an id) --
    so a room answers it when the room's own spelling, uid or name, is the
    query or sits inside it, which is the reading `structure.planned_context`
    has always applied to the plan. And a query that rides a beat whose
    destination the world already holds is a request for lore ABOUT that
    room, not for the room: the destination answers it.
    """
    if not query:
        return None
    from world.spatial import normalize_room_id

    if destination in ("known", "planned"):
        return destination
    folded = normalize_room_id(str(query))
    if not folded:
        return None
    rooms = (scene or {}).get("rooms") or {}
    for rid, room in rooms.items():
        spellings = {normalize_room_id(str(rid))}
        if isinstance(room, dict):
            spellings.add(normalize_room_id(str(room.get("name") or "")))
        spellings.discard("")
        if any(sp == folded or sp in folded for sp in spellings):
            return "known"
    if planned_for(query):
        return "planned"
    return "unmatched"


def compile_world_context(ctx, nonce):
    """Assemble the beat's world context from the story's own rows.

    Deterministic: same inputs, same output, no provider call. ``nonce`` is
    accepted for the step-handler signature and unused -- a reroll of this
    step is the same compilation.
    """
    from world.planning_needs import planning_need
    from world.structure import planned_context

    chat = ctx.chat
    cid = chat["id"]
    interp = ctx.get("director_interpret") or {}
    fl = interp.get("flow") if isinstance(interp.get("flow"), dict) else {}

    query = _query(ctx, interp)
    books = _books(ctx, refresh=True)
    weights = _book_weights(ctx, refresh=True)
    hits = search_lore(weights, query, k=WORLD_CONTEXT_LORE_K,
                       exclude_categories=["knowledge"])
    # Living world, approach D: a location entry the beat is about to work
    # from may carry the history the unvisited place has accrued. This seam
    # is the obligation ledger's ONLY consumer -- the place's debt surfaces
    # where the place itself is compiled, never in any mind's payload;
    # arrival is the earning event.
    owed = 0
    try:
        from world.living_world import attach_owed_history
        before = [dict(h) for h in hits]
        hits = attach_owed_history(cid, hits)
        owed = sum(1 for b, a in zip(before, hits)
                   if isinstance(a, dict) and a.get("content") != b.get("content"))
    except Exception as exc:
        ctx.add_warning(f"owed history not attached: {exc}")

    fresh = [_lore_row(h) for h in hits if isinstance(h, dict)]
    # Owed history is attached to the hit's `content`, which `_lore_row`
    # carries -- so the debt rides the step exactly as it rode the model
    # payload, and `lore_for` serves it to the Director.
    cache = wget(cid, "lore_cache", []) or []
    merged = merge_lore(fresh, cache)[:WORLD_CONTEXT_LORE_CAP]

    valid = set(books)
    relevant_books = []
    for entry in merged:
        try:
            bid = int(entry.get("book_id"))
        except (TypeError, ValueError):
            continue
        if bid in valid and bid not in relevant_books:
            relevant_books.append(bid)

    scene = get_scene(cid, chat)

    def planned_for(spelling):
        try:
            return planned_context(cid, spelling)
        except Exception as exc:
            ctx.add_warning(f"planned room context not attached: {exc}")
            return None

    movement = classify_movement(interp, scene, planned_for=planned_for)
    location_query = interp.get("location_query") or None
    query_status = _location_query_status(
        location_query, scene, planned_for=planned_for,
        destination=movement["status"])

    planned = None
    if movement["status"] == "planned":
        planned = planned_for(movement["to_room"])
    elif query_status == "planned":
        planned = planned_for(location_query)

    needs = []
    frame_id = getattr(ctx.turn, "frame_id", None)
    turn_idx = getattr(ctx.turn, "idx", 0) or 0
    mv = interp.get("movement") if isinstance(interp.get("movement"), dict) else {}
    if movement["status"] == "unplanned":
        needs.append(planning_need(
            "room", "declared_destination_unplanned",
            subject=movement["to_room"],
            surface={"why": str(mv.get("why") or ""),
                     "request": str(fl.get("mapping_request") or "")},
            turn_idx=turn_idx, frame_id=frame_id))
    if query_status == "unmatched":
        needs.append(planning_need(
            "room", "location_query_unmatched",
            subject=location_query,
            surface={"request": str(fl.get("mapping_request") or "")},
            turn_idx=turn_idx, frame_id=frame_id))
    for request in (fl.get("generation_requests") or []):
        if not isinstance(request, dict):
            continue
        subject = request.get("subject") or request.get("location_id")
        if not subject:
            continue
        try:
            needs.append(planning_need(
                request.get("kind"), "generation_request",
                subject=subject,
                surface={k: request[k] for k in (
                    "location_id", "constraints", "urgency") if request.get(k)},
                turn_idx=turn_idx, frame_id=frame_id))
        except ValueError as exc:
            ctx.add_warning(f"generation request not recorded: {exc}")
    # One need per identity: the same door reached twice in one beat, under
    # whatever reasons, is one need (the first reason is kept).
    unique, seen = [], set()
    for need in needs:
        if need["identity"] in seen:
            continue
        seen.add(need["identity"])
        unique.append(need)

    summary = (f"{len(merged)} lore entries compiled from "
               f"{len(relevant_books)} book(s)")
    if unique:
        summary += f"; {len(unique)} planning need(s) raised"
    return {
        "relevant_lore": merged,
        "relevant_books": relevant_books,
        # The compiler never stages and never patches: a room the beat
        # reached with no plan is a NEED, not a proposal.
        "staged_lore": [],
        "scene_patch": _normalize_scene_patch({}),
        "movement": movement,
        "location_query": {"query": location_query, "status": query_status}
                          if location_query else None,
        **({"planned": planned} if planned else {}),
        "planning_needs": unique,
        "owed_history_attached": owed,
        "compiled": True,
        "summary": summary,
    }


def merge_lore(hits, cache):
    """Fresh retrieval first, cached entries after, one copy of each entry.

    `id` FIRST, because it is the one field two revisions of the same entry
    must share. Lore entries ACCRETE -- the engine appends narrative events to
    them -- and the cache stores SNAPSHOTS rather than references, so the same
    entry can sit here twice at two lengths.

    `entry_uid or fingerprint` could not collide those. A cached dict written
    before the uid was carried through has none, so it falls to the
    fingerprint, and a uid and a fingerprint live in different namespaces. The
    fingerprint cannot rescue it either: it hashes keys+content, which is
    exactly what differs between two revisions.

    Measured live, chat 59: ten cached entries, nine distinct ids, entry 2213
    present twice at 1,572 and 1,442 characters. The shorter copy predates a
    sentence the longer one carries, so the model was handed the same room
    twice at two revisions, one of which did not know a character had gone
    upstairs. A contradiction served as retrieved lore, not a wasted slot.

    `hits` precede `cache`, so keeping the first occurrence keeps the freshly
    retrieved revision and drops the fossil.
    """
    seen, merged = set(), []
    for e in list(hits or []) + list(cache or []):
        if not isinstance(e, dict):
            continue
        key = e.get("id") or e.get("entry_uid") or _lore_fingerprint(e)
        if key in seen:
            continue
        seen.add(key)
        merged.append(e)
    return merged
