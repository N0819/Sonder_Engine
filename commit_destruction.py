"""Single- and multi-book destruction cascades: what a destruction dooms,
who hears of it, and when.

Extracted verbatim from commit.py, which re-exports every name here.
See docs/experiments/AUDIT_COMMIT.md for the split record.
"""

import json
from db import q, qi, wget, wset
from memory import lorebook_descendants
from mechanics import news_latency_seconds
from spatial import normalize_room_id
from commit_common import _stable_event_key

# ---- Destruction: single-book (Phase 2) + multi-book cascades (3b) ----
#
# The DIRECTOR resolves the causal destructive event by declaring it in
# state_diff.destruction (the revived DestructionEffect shape) -- code
# never originates a destruction, it only realizes a declared one
# deterministically. scale 'vehicle'/'building' dooms the target's ONE
# anchored/scoped book; scale 'region' (Phase 3b) dooms a multi-book
# CASCADE enumerated from the lorebook tree (_destruction_cascade below).
# Either way the doomed books and their registered rooms are retired
# (retire-not-delete: the ruin's history stays retrievable), the live
# rooms/entities drop through the ordinary diff machinery, a stranded
# occupant ANYWHERE in the doomed set fails the whole commit (guard
# above), and awareness propagates only through latency-gated
# `news_arrival` scheduled events that the mechanics sweep fires against
# the minting frame's clock -- latency declared by the Director, or
# derived from the audience's distance in the book graph (near regions
# hear sooner; mechanics.news_latency_seconds).

def _destruction_book(cid, target):
    """The live ROOT book destruction of `target` starts from: its
    anchored vehicle book, else the book scoped to it as a location."""
    row = q(
        "SELECT id, name FROM lorebooks WHERE chat_id=? AND "
        "anchor_entity_id=? AND retired_turn_id IS NULL ORDER BY id LIMIT 1",
        (cid, target), one=True,
    )
    if row:
        return row
    return q(
        "SELECT id, name FROM lorebooks WHERE chat_id=? AND "
        "scope_location_id IN (?, ?) AND retired_turn_id IS NULL "
        "ORDER BY id LIMIT 1",
        (cid, target, normalize_room_id(target)), one=True,
    )


def _chat_book_graph(cid):
    """This chat's whole lorebook graph in one read: rows by id,
    undirected edges (parent_id containment + currently_within presence),
    and the directed currently_within list (cascade enumeration needs the
    direction; the news-distance walk does not). Pure reads -- runs in
    commit preparation."""
    books = {
        row["id"]: dict(row)
        for row in q(
            "SELECT id, name, parent_id, anchor_entity_id, "
            "scope_location_id, retired_turn_id FROM lorebooks "
            "WHERE chat_id=?", (cid,))
    }
    edges = {bid: set() for bid in books}
    for bid, row in books.items():
        pid = row["parent_id"]
        if pid in edges:
            edges[bid].add(pid)
            edges[pid].add(bid)
    within = []
    for link in q(
        "SELECT source_book_id AS s, target_book_id AS t "
        "FROM lorebook_links WHERE relation_type='currently_within' "
        "ORDER BY id",
    ):
        if link["s"] in edges and link["t"] in edges:
            edges[link["s"]].add(link["t"])
            edges[link["t"]].add(link["s"])
            within.append((link["s"], link["t"]))
    return books, edges, within


def _book_distances(root_id, edges):
    """BFS hop distances from the destruction root over the undirected
    book graph -- the deterministic 'how far away is that audience'
    measure derived news latency uses (Phase 3b)."""
    if root_id not in edges:
        return {}
    distances = {root_id: 0}
    frontier = [root_id]
    while frontier:
        nxt = []
        for bid in frontier:
            for neighbor in sorted(edges[bid]):
                if neighbor not in distances:
                    distances[neighbor] = distances[bid] + 1
                    nxt.append(neighbor)
        frontier = nxt
    return distances


def _audience_book_id(audience, books):
    """Deterministically match a declared news audience to a lorebook --
    by name, scope_location_id, or anchor_entity_id, exact or slugified;
    lowest book id wins. None when nothing matches (the caller falls back
    to the flat unreachable-latency default)."""
    keys = {audience.casefold(), normalize_room_id(audience)} - {""}
    if not keys:
        return None
    for bid in sorted(books):
        row = books[bid]
        candidates = set()
        for value in (row.get("name"), row.get("scope_location_id"),
                      row.get("anchor_entity_id")):
            value = str(value or "").strip()
            if value:
                candidates.add(value.casefold())
                candidates.add(normalize_room_id(value))
        if keys & candidates:
            return bid
    return None


def _destruction_cascade(cid, root_book_id, prev_scene, books, within):
    """Phase 3b: enumerate the multi-book cascade a region destruction
    dooms -- a deterministic function of (committed state, declared root),
    never model output. Two edge kinds, mirroring monitoring_subtree:

    - parent_id descendants of the root (canonical containment): every
      child book falls with its region, rooms or no rooms;
    - inbound currently_within members (live presence), to a fixpoint,
      but only when the member's anchor entity is PHYSICALLY positioned
      inside an already-doomed room -- the ferry docked in the burning
      harbor goes down with it (and the van aboard the ferry with the
      ferry), while a ship whose stale link says 'within' but whose
      anchor is not actually in a doomed room is spared.

    Returns {"book_ids": sorted live cascaded books, "anchors": their
    anchor entity ids, "registered": live registry room_uids owned by any
    cascaded book (the whole registries -- rooms live only in a sibling
    frame's scene included, because the books are gone everywhere)}."""
    prev_rooms = prev_scene.get("rooms") or {}
    positions = {
        str(k): str(v)
        for k, v in (prev_scene.get("positions") or {}).items()
    }
    rooms_by_book = {}
    for row in q(
        "SELECT room_uid, owning_book_id FROM room_registry "
        "WHERE chat_id=? AND retired_turn_id IS NULL ORDER BY room_uid",
        (cid,),
    ):
        rooms_by_book.setdefault(row["owning_book_id"], []).append(
            row["room_uid"])

    def subtree(book_id):
        return {b for b in lorebook_descendants(book_id) if b in books}

    cascade = subtree(root_book_id)
    while True:
        anchors = {books[b]["anchor_entity_id"] for b in cascade
                   if books[b]["anchor_entity_id"]}
        doomed_live = {
            rid for b in cascade for rid in rooms_by_book.get(b, ())
            if rid in prev_rooms
        } | {
            str(rid) for rid, room in prev_rooms.items()
            if isinstance(room, dict)
            and room.get("parent_entity") in anchors
        }
        grew = False
        for source, target_book in within:
            if target_book not in cascade or source in cascade:
                continue
            anchor = books[source]["anchor_entity_id"]
            if anchor and positions.get(str(anchor)) in doomed_live:
                cascade |= subtree(source)
                grew = True
        if not grew:
            break

    return {
        "book_ids": sorted(
            b for b in cascade if books[b]["retired_turn_id"] is None),
        "anchors": anchors,
        "registered": sorted({
            rid for b in cascade for rid in rooms_by_book.get(b, ())
        }),
    }


def _prepare_destruction(cid, prev_scene, diff, add_warning=None):
    """Validate the Director's state_diff.destruction declaration and fold
    its mechanical consequences into the (already deep-copied) diff:
    remove every doomed entity and room. Pure reads; returns the plan
    commit_scene applies durably, or None. Ledger-not-cage does NOT apply
    here -- an invalid declaration is dropped with a warning rather than
    guessed at, because destruction is irreversible.

    scale 'vehicle'/'building' dooms the target's ONE book (Phase 2);
    scale 'region' dooms the deterministic multi-book cascade enumerated
    by _destruction_cascade above (Phase 3b)."""
    decl = diff.get("destruction")
    if not isinstance(decl, dict):
        return None

    def warn(message):
        if add_warning:
            add_warning(message)

    target = str(decl.get("target_id") or "").strip()
    if not target:
        warn("destruction declaration dropped: no target_id")
        return None
    scale = str(decl.get("scale") or "").strip().casefold()
    if scale not in ("vehicle", "building", "region"):
        warn(
            f"destruction of {target!r} dropped: scale {scale!r} is not a "
            "single vehicle/building or a multi-book region"
        )
        return None
    kind = str(decl.get("kind") or "destroyed").strip() or "destroyed"

    books, edges, within = _chat_book_graph(cid)
    root = _destruction_book(cid, target)
    prev_rooms = prev_scene.get("rooms") or {}

    if scale == "region":
        if not root:
            warn(
                f"destruction of region {target!r} dropped: no live "
                "lorebook is anchored or scoped to it, so the cascade "
                "cannot be enumerated"
            )
            return None
        cascade = _destruction_cascade(
            cid, root["id"], prev_scene, books, within)
        book_ids = cascade["book_ids"]
        doomed_entities = sorted(
            {str(a) for a in cascade["anchors"]} | {target})
        registered = cascade["registered"]
        doomed_set = set(doomed_entities)
        entity_rooms = {
            rid for rid, r in prev_rooms.items()
            if isinstance(r, dict)
            and r.get("parent_entity") in doomed_set}
    else:
        book_ids = [root["id"]] if root else []
        doomed_entities = [target]
        registered = []
        if root:
            registered = [
                r["room_uid"] for r in q(
                    "SELECT room_uid FROM room_registry WHERE chat_id=? AND "
                    "owning_book_id=? AND retired_turn_id IS NULL",
                    (cid, root["id"]),
                )
            ]
        entity_rooms = {rid for rid, r in prev_rooms.items()
                        if isinstance(r, dict)
                        and r.get("parent_entity") == target}

    doomed_live = set(entity_rooms) \
        | {r for r in registered if r in prev_rooms}
    # Retirement covers the doomed books' whole registries, including
    # rooms that live only in a sibling frame's scene -- the books are
    # gone everywhere.
    retire_rooms = sorted(set(registered) | {
        rid for rid in entity_rooms
        if q("SELECT 1 FROM room_registry WHERE chat_id=? AND room_uid=?",
             (cid, rid), one=True)
    })

    entities = prev_scene.get("entities") or {}
    label = target
    ent = entities.get(target)
    if isinstance(ent, dict) and ent.get("name"):
        label = str(ent["name"])
    elif root:
        label = root["name"]

    # Fold the mechanical consequences into the diff: the ordinary diff
    # machinery (merge_scene_with_diff) is what actually drops the live
    # entities/rooms -- destruction adds no second removal path.
    removals = diff.setdefault("remove_entities", [])
    for eid in doomed_entities:
        if eid in entities and eid not in removals:
            removals.append(eid)
    room_removals = diff.setdefault("remove_rooms", [])
    for rid in sorted(doomed_live):
        if rid not in room_removals:
            room_removals.append(rid)

    # Occupants who escape the doomed rooms by DEPARTING (cast_changes,
    # the guard's second legal exit) rather than repositioning keep a
    # stale positions entry that merge_scene_with_diff's occupied-room
    # refusal would trip over, silently keeping a doomed room live in
    # the scene while its registry row retires. Vacate them here (the
    # guard has already proven every doomed-room occupant repositioned
    # or departed); prepare_scene_commit pops these positions and the
    # remaining doomed rooms right after the merge.
    diff_positions = {
        str(k).casefold(): str(v)
        for k, v in (diff.get("positions") or {}).items()
    }
    departed = {
        str(c.get("who") or "").casefold()
        for c in (diff.get("cast_changes") or []) if isinstance(c, dict)
    }
    vacated = sorted(
        str(name)
        for name, room in (prev_scene.get("positions") or {}).items()
        if str(room) in doomed_live
        and str(name).casefold() in departed
        and diff_positions.get(str(name).casefold()) is None
    )

    distances = _book_distances(root["id"], edges) if root else {}
    news = []
    for item in decl.get("news") or []:
        if not isinstance(item, dict):
            continue
        audience = str(item.get("audience") or "").strip()
        if not audience:
            continue
        try:
            latency = max(0.0, float(item["latency_seconds"]))
        except (KeyError, TypeError, ValueError):
            # No declared latency: derive it from the audience's hop
            # distance to the root in the book graph (Phase 3b) -- near
            # regions hear sooner, distant later, unmatched a flat day.
            audience_book = _audience_book_id(audience, books)
            latency = news_latency_seconds(
                distances.get(audience_book)
                if audience_book is not None else None)
        summary = str(item.get("summary") or "").strip() \
            or f"{label} has been {kind}"
        news.append({"audience": audience, "latency_seconds": latency,
                     "summary": summary})

    return {
        "target": target, "scale": scale, "kind": kind, "label": label,
        "book_ids": book_ids,
        "doomed_rooms": sorted(doomed_live),
        "doomed_entities": list(doomed_entities),
        "retire_rooms": retire_rooms,
        "vacated": vacated,
        "news": news,
    }


def _finalize_destruction_news(destruction, cid, frame_id, turn, elapsed):
    """Mint the news_arrival scheduled-event rows: one per audience scope,
    due_at = the minting frame's sim clock + declared latency, stable
    event ids so a rerun cannot double-schedule. Same frame-gating payload
    convention as transit_arrival (the sweep never fires one against
    another frame's clock)."""
    rows = []
    for item in destruction["news"]:
        event_id = _stable_event_key(
            "news_arrival", cid, frame_id, destruction["target"], turn.id,
            item["audience"])
        rows.append({
            "event_id": event_id, "chat_id": cid,
            "due_at": elapsed + item["latency_seconds"],
            "kind": "news_arrival", "location_id": None,
            "payload": json.dumps({
                "frame_id": frame_id,
                "audience": item["audience"],
                "summary": item["summary"],
                "target_id": destruction["target"],
                "destruction_kind": destruction["kind"],
                "provenance": "told",
            }, ensure_ascii=False),
            "seed": f"news:{cid}:{turn.idx}", "status": "pending",
        })
    destruction["news_rows"] = rows


def _apply_destruction(cid, turn_id, destruction):
    """Durable half, inside commit_scene's transaction: retire every
    doomed book (one for vehicle/building scale, the whole cascade for
    region scale) and their registered rooms atomically with the scene
    write, mint the news events, and stage engine notices (appended --
    the transit sweep already wrote this beat's list in the domain before
    this one). All-or-nothing with the rest of the turn: any domain
    failure rolls the entire outer transaction back."""
    book_ids = destruction.get("book_ids") or []
    for book_id in book_ids:
        qi("UPDATE lorebooks SET retired_turn_id=? "
           "WHERE id=? AND chat_id=? AND retired_turn_id IS NULL",
           (turn_id, book_id, cid))
    for rid in destruction.get("retire_rooms") or []:
        qi("UPDATE room_registry SET retired_turn_id=? "
           "WHERE chat_id=? AND room_uid=? AND retired_turn_id IS NULL",
           (turn_id, cid, rid))
    for row in destruction.get("news_rows") or []:
        qi(
            "INSERT OR REPLACE INTO scheduled_events"
            "(event_id,chat_id,due_at,kind,location_id,payload,seed,status)"
            " VALUES(?,?,?,?,?,?,?,?)",
            (row["event_id"], row["chat_id"], row["due_at"], row["kind"],
             row["location_id"], row["payload"], row["seed"], row["status"]),
        )
    notices = wget(cid, "engine_notices", []) or []
    retired = len(destruction.get("retire_rooms") or [])
    notices.append(
        f"{destruction['label']} has been {destruction['kind']}; "
        f"its records ({retired} registered room(s)"
        + (f", {len(book_ids)} lorebook(s)" if book_ids else "")
        + ") are retired history now."
    )
    wset(cid, "engine_notices", notices)
