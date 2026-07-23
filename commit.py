"""Atomic world-state commit with mutation validation."""

import copy
import json, re, threading, time, weakref
from concurrent.futures import ThreadPoolExecutor
from db import q, qi, qtx, transaction, wget, wset, get_setting
from memory import (
    add_memories_batch, prepare_memories_batch, delete_turn_memories, search_lore, add_lore,
    update_lore, LORE_CATEGORIES, LOREBOOK_TYPES,
    chat_lorebook_ids, chat_lorebook_weights, lorebook_manifest, dump_chat_memories,
    add_lorebook_link, lorebook_descendants,
    restore_chat_memories, dump_lorebook, restore_lorebook,
    knowledge_for_character, get_relationships,
    save_relationships, update_relationships_from_inference,
    apply_relationship_updates, maybe_consolidate_character_memory,
)
from providers import embed_texts
from prompts import get_prompt
import affect
from character_schema import (character_name, new_uid, character_psychology,
                              character_initial_active_state, effective_drive,
                              normalize_character_data, persona_name)
from frames import is_recognized_in_frame
from scene import set_char_state, set_char_status
from mechanics import mechanics_sweep, news_latency_seconds, stable_event_key
from spatial import (merge_scene_with_diff,
                     normalize_room_id, spatial_rel, hear_level)
from theory_of_mind import apply_mind_model_updates
from paradox import check_and_apply_paradox
from spatial_frames import detect_and_reconcile as detect_and_reconcile_spatial
from spatial_frames import (infer_companion_carry, infer_vehicle_zones,
                            infer_came_from, infer_focus, infer_facing)

_COMMIT_LOCKS = weakref.WeakValueDictionary()
_COMMIT_LOCKS_GUARD = threading.Lock()

def _commit_lock(turn_id):
    with _COMMIT_LOCKS_GUARD:
        return _COMMIT_LOCKS.setdefault(turn_id, threading.Lock())

def _keys_str(value):
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(v) for v in value if v is not None)
    return str(value or "")

# Deterministic event/memory ids live in mechanics.py now (the sweep needs
# them without importing commit); kept under the old private name for the
# many call sites and tests that use it.
_stable_event_key = stable_event_key

def _clamp(value, lo=0.0, hi=1.0):
    try:
        return max(lo, min(hi, float(value)))
    except Exception:
        return lo

_NON_ATTIRE_TERMS = {
    "chair", "cushion", "seat", "table", "cup", "mug", "glass",
    "bottle", "book", "weapon", "tool",
}

def sanitize_attire_items(items):
    result = []
    for item in items or []:
        text = str(item).strip()
        lowered = text.casefold()
        if not text:
            continue
        if any(re.search(rf"\b{re.escape(term)}\b", lowered) for term in _NON_ATTIRE_TERMS):
            continue
        if text not in result:
            result.append(text)
    return result

def _normalize_character_output(out):
    if not out.get("mind_model_updates") and out.get("inference_updates"):
        converted = []
        for update in out["inference_updates"]:
            converted.append({
                "about_entity": str(update.get("about") or "unknown"),
                "kind": "goal",
                "claim": str(update.get("conclusion") or ""),
                "confidence": float(update.get("confidence", 0.5)),
                "evidence": [{"event_id": "", "fact": str(update.get("basis") or "")}],
                "alternatives": [],
            })
        out["mind_model_updates"] = converted
    return out

# ---- Scene commit with entity-aware merge ----

def _anchor_current_room(sc, entity_id):
    """The anchor entity's current exterior room, tolerating positions
    keyed by entity id, display name, or alias (the same read tolerance
    spatial._entity_exterior_room applies)."""
    positions = sc.get("positions") or {}
    if entity_id in positions:
        return positions[entity_id]
    ent = (sc.get("entities") or {}).get(entity_id)
    if isinstance(ent, dict):
        for cand in [ent.get("name"), *(ent.get("aliases") or [])]:
            cand = str(cand or "").strip()
            if cand and cand in positions:
                return positions[cand]
    return None


def sync_anchored_books(cid, sc):
    """A vehicle-class (or any anchor_entity_id-flagged) lorebook tracks
    its anchor entity's current room via a 'currently_within' lorebook
    link -- presence ("is at"), rewritten from scene positions at every
    commit. parent_id is canonical containment ("belongs to") and is
    NEVER mutated here: the old behavior reparented the book to follow
    the vehicle, collapsing the two relations into one and destroying
    the authored hierarchy every time the vehicle docked somewhere new.

    The link targets the book of wherever the anchor currently is:
    - the room is another anchored entity's interior (a van aboard a
      ferry) -> that entity's own anchored book, giving the true nesting
      chain the monitoring walk (memory.monitoring_subtree) reads;
    - otherwise the location book whose scope_location_id matches the
      room.
    follow_for_retrieval stays on (default weight) so docked-location
    lore remains reachable through the vehicle book via
    resolve_lorebook_graph. The link is retrieval bookkeeping ONLY --
    it must never be read as perception authorization; what an observer
    aboard actually perceives stays with the epistemic/spatial layer.
    """
    anchored = q(
        "SELECT id, anchor_entity_id, parent_id FROM lorebooks "
        "WHERE chat_id=? AND anchor_entity_id IS NOT NULL",
        (cid,),
    )
    if not anchored:
        return
    book_by_anchor = {b["anchor_entity_id"]: b["id"] for b in anchored}
    rooms = sc.get("rooms") or {}
    for book in anchored:
        room = _anchor_current_room(sc, book["anchor_entity_id"])
        if not room:
            # No recorded position -> nothing to derive from; leave the
            # last known presence link standing (mirrors the old
            # missing-position behavior).
            continue
        room_def = rooms.get(room)
        parent_entity = room_def.get("parent_entity") \
            if isinstance(room_def, dict) else None
        target_id = None
        if parent_entity and parent_entity != book["anchor_entity_id"]:
            target_id = book_by_anchor.get(parent_entity)
        if target_id is None:
            target = q(
                "SELECT id FROM lorebooks WHERE chat_id=? AND "
                "scope_location_id=? ORDER BY id LIMIT 1",
                (cid, room), one=True,
            )
            target_id = target["id"] if target else None
        if target_id == book["id"]:
            target_id = None
        current = q(
            "SELECT id, target_book_id FROM lorebook_links "
            "WHERE source_book_id=? AND relation_type='currently_within'",
            (book["id"],),
        )
        for link in current:
            if link["target_book_id"] != target_id:
                qi("DELETE FROM lorebook_links WHERE id=?", (link["id"],))
        if target_id is not None \
                and not any(l["target_book_id"] == target_id for l in current):
            try:
                add_lorebook_link(book["id"], target_id, "currently_within")
            except ValueError:
                pass

def _guard_occupied_mover_removal(prev_scene, diff, doomed=None):
    """Deterministic refusal: removing an entity whose parent_entity-linked
    interior rooms still hold occupants, without the same beat repositioning
    every occupant (state_diff.positions, to a room OUTSIDE the doomed
    interior) or recording their departure (cast_changes), would leave
    people positioned inside rooms of a container that no longer exists.
    Raising here fails commit preparation, so the whole turn rolls back per
    the existing atomicity contract -- the same conservatism as
    merge_scene_with_diff's occupied-room removal refusal, made loud
    because losing PEOPLE is worse than losing a room.

    `doomed` ({label: room_id set}) generalizes the guard to BOOK scope
    for destruction: every room registered to a destroyed book is doomed
    alongside the entity's own interiors, and a stranded occupant in ANY
    of them fails the whole commit -> rollback. Since Phase 3b the doomed
    set may span a whole multi-book cascade; an occupant that is ITSELF
    being removed this beat (a doomed vehicle inside a doomed region) is
    not stranded -- it ceases to exist with its container, and its own
    interior rooms carry their own doom entry below, so the people inside
    IT are still guarded."""
    removals = [str(e) for e in (diff.get("remove_entities") or []) if e]
    if not removals and not doomed:
        return
    removal_set = set(removals)
    rooms = prev_scene.get("rooms") or {}
    positions = prev_scene.get("positions") or {}
    diff_positions = {
        str(k).casefold(): v for k, v in (diff.get("positions") or {}).items()
    }
    departed = {
        str(c.get("who") or "").casefold()
        for c in (diff.get("cast_changes") or []) if isinstance(c, dict)
    }
    doom_map = {}
    for eid in removals:
        interior = {rid for rid, r in rooms.items()
                    if isinstance(r, dict) and r.get("parent_entity") == eid}
        if interior:
            doom_map[eid] = interior
    for label, extra in (doomed or {}).items():
        doom_map[label] = doom_map.get(label, set()) | {
            str(r) for r in extra if str(r) in rooms}
    for eid, interior in doom_map.items():
        stranded = []
        for name, room in positions.items():
            if room not in interior or str(name) == eid:
                continue
            if str(name) in removal_set:
                continue  # removed/destroyed itself this beat (see above)
            cf = str(name).casefold()
            new_room = diff_positions.get(cf)
            if new_room is not None and new_room not in interior:
                continue
            if cf in departed:
                continue
            stranded.append(name)
        if stranded:
            raise RuntimeError(
                f"removal/destruction would strand occupant(s) {stranded!r} "
                f"inside removed {eid!r}'s doomed room(s); "
                "reposition them via state_diff.positions or record their "
                "departure in cast_changes in the same beat"
            )

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


# ---- Room registry (normalized) + commit-side structural dedup ----
#
# Two live failure classes share one root: nothing at commit time knew which
# rooms an owner (a vehicle, the current location) ALREADY has. (1) Two
# structurally identical vehicles minting the same interior key ("deck_3")
# silently merged one ship's deck into the other's. (2) The same owner's
# room re-minted under a fresh key ("deck_three" for an existing "Deck 3")
# created a live duplicate that only the advisory remove_rooms self-heal
# might later clean up. The registry is the normalized `room_registry`
# table (Phase 2; it supersedes Phase 1's derived lore_entries encoding):
# one row per room ever minted, keyed (chat_id, room_uid), scoped to its
# owning vehicle/location book. It is the sole cross-frame ledger of room
# IDENTITY, dedup, and retirement (Phase 3a) -- the frame-scoped scene JSON
# is the sole authority for LIVE rooms/positions, and the registry is a
# deterministic projection of every scene write: commit_scene maintains it
# in the same commit domain, and the manual world editor reconciles it via
# sync_room_registry_with_scene below. Removal
# RETIRES a row (retired_turn_id = the removing turn) instead of deleting
# it, so a destroyed ship's decks remain retrievable history. Ledger,
# never a cage: a colliding mint is REDIRECTED or REKEYED, never rejected
# (invention is always allowed, duplication is not).

def _anchored_book_ids(cid):
    return {
        row["anchor_entity_id"]: row["id"]
        for row in q(
            "SELECT id, anchor_entity_id FROM lorebooks "
            "WHERE chat_id=? AND anchor_entity_id IS NOT NULL",
            (cid,),
        )
    }

def _room_display_slug(room_id, room_def):
    name = ""
    if isinstance(room_def, dict):
        name = str(room_def.get("name") or "")
    return normalize_room_id(name or str(room_id))

def _registry_alias_index(cid, book_id):
    """{normalized name/alias: room_uid} for every LIVE room registered
    under one owning book -- read from the room_registry table. Retired
    rows are excluded on purpose: dedup must never redirect a new mint
    onto a destroyed room's identity (a rebuilt deck is a new room; the
    ruin keeps its own retired row)."""
    index = {}
    for row in q(
        "SELECT room_uid, name, aliases FROM room_registry "
        "WHERE chat_id=? AND owning_book_id=? AND retired_turn_id IS NULL",
        (cid, book_id),
    ):
        try:
            aliases = json.loads(row["aliases"] or "[]")
        except Exception:
            aliases = []
        for alias in [row["name"], *aliases]:
            slug = normalize_room_id(str(alias or ""))
            if slug:
                index.setdefault(slug, row["room_uid"])
        index.setdefault(normalize_room_id(row["room_uid"]), row["room_uid"])
    return index

def _apply_room_renames(diff, renames):
    """Rewrite every reference to a renamed/redirected room key inside the
    diff: the rooms table itself, adjacency 'to' edges, positions, room
    removals, entity interior_rooms, and transit destinations."""
    rooms = diff.get("rooms")
    if isinstance(rooms, dict):
        for old, new in renames.items():
            if old not in rooms:
                continue
            moved = rooms.pop(old)
            existing = rooms.get(new)
            if isinstance(existing, dict) and isinstance(moved, dict):
                merged = dict(existing)
                for key, value in moved.items():
                    if value or key not in merged:
                        merged[key] = value
                rooms[new] = merged
            else:
                rooms[new] = moved
        for room in rooms.values():
            if not isinstance(room, dict):
                continue
            for edge in room.get("adjacent") or []:
                if isinstance(edge, dict) and edge.get("to") in renames:
                    edge["to"] = renames[edge["to"]]
    positions = diff.get("positions")
    if isinstance(positions, dict):
        for name, room in list(positions.items()):
            if room in renames:
                positions[name] = renames[room]
    if isinstance(diff.get("remove_rooms"), list):
        diff["remove_rooms"] = [
            renames.get(r, r) for r in diff["remove_rooms"]
        ]
    for edge in diff.get("remove_adjacent") or []:
        if isinstance(edge, dict):
            if edge.get("room") in renames:
                edge["room"] = renames[edge["room"]]
            if edge.get("to") in renames:
                edge["to"] = renames[edge["to"]]
    for ent in (diff.get("entities") or {}).values():
        if not isinstance(ent, dict):
            continue
        if isinstance(ent.get("interior_rooms"), list):
            ent["interior_rooms"] = [
                renames.get(r, r) for r in ent["interior_rooms"]
            ]
        state = ent.get("state")
        transit = state.get("transit") if isinstance(state, dict) else None
        if isinstance(transit, dict):
            for field in ("destination_room", "route_room"):
                if transit.get(field) in renames:
                    transit[field] = renames[transit[field]]

def dedup_minted_rooms(cid, prev_scene, diff, add_warning=None):
    """Structural dup prevention at creation time. For each room key the
    diff mints, check the CURRENT CONTAINMENT SCOPE (rooms sharing the same
    parent_entity owner -- None = the open location -- plus the owning
    book's registry aliases) before accepting it:

    - same key, DIFFERENT declared owner than the existing room (the
      two-ship 'deck_3' class): the incoming room is a new room of ITS
      owner colliding on a flat key -- REKEY it to an owner-scoped id;
    - new key whose name/alias collides with an existing room of the SAME
      scope (a re-mint of 'Deck 3' as 'deck_three'): REDIRECT the diff onto
      the existing id instead of minting a duplicate.

    Mutates `diff` in place (rewriting the room key and every reference:
    positions, adjacency, interiors, transit) and returns {old: new}.
    Never rejects a genuinely new room -- ledger, not cage. The advisory
    remove_rooms self-heal in prepare_scene_commit stays as the backstop
    for duplicates that predate this check.
    """
    rooms = diff.get("rooms")
    if not isinstance(rooms, dict) or not rooms:
        return {}
    prev_rooms = prev_scene.get("rooms") or {}
    anchor_books = _anchored_book_ids(cid)
    registry_cache = {}
    renames = {}
    taken = set(prev_rooms) | set(rooms)

    def unique_key(base):
        candidate = base
        suffix = 2
        while candidate in taken:
            candidate = f"{base}_{suffix}"
            suffix += 1
        taken.add(candidate)
        return candidate

    for rid in list(rooms.keys()):
        rdef = rooms[rid]
        if not isinstance(rdef, dict):
            continue
        incoming_owner = rdef.get("parent_entity")
        existing = prev_rooms.get(rid)
        if isinstance(existing, dict):
            existing_owner = existing.get("parent_entity")
            if incoming_owner and existing_owner \
                    and incoming_owner != existing_owner:
                new_id = unique_key(
                    normalize_room_id(f"{incoming_owner}_{rid}"))
                renames[rid] = new_id
                if add_warning:
                    add_warning(
                        f"Room key collision: '{rid}' already belongs to "
                        f"{existing_owner!r}; the new room declared for "
                        f"{incoming_owner!r} was rekeyed to '{new_id}'."
                    )
            continue
        # Brand-new key: name/alias dedup within the same containment scope.
        slug = _room_display_slug(rid, rdef)
        rid_slug = normalize_room_id(rid)
        match = None
        for prev_id, prev_def in prev_rooms.items():
            if not isinstance(prev_def, dict):
                continue
            if prev_def.get("parent_entity") != incoming_owner:
                continue
            if _room_display_slug(prev_id, prev_def) == slug \
                    or normalize_room_id(prev_id) in (slug, rid_slug):
                match = prev_id
                break
        if match is None and incoming_owner in anchor_books:
            book_id = anchor_books[incoming_owner]
            if book_id not in registry_cache:
                registry_cache[book_id] = _registry_alias_index(cid, book_id)
            registered = registry_cache[book_id].get(slug) \
                or registry_cache[book_id].get(rid_slug)
            if registered and registered in prev_rooms:
                match = registered
        if match and match != rid:
            renames[rid] = match
            if add_warning:
                add_warning(
                    f"Duplicate room mint: '{rid}' matches existing room "
                    f"'{match}' in the same scope; redirected instead of "
                    "minting a duplicate."
                )

    if renames:
        _apply_room_renames(diff, renames)
    return renames

def _prepare_room_registry(cid, canon_book_id, prev_scene, sc):
    """Build this commit's room_registry mutations -- pure reads only, so
    it runs in preparation, before the write lock. Each live room registers
    under its owning book: parent_entity rooms under the entity's anchored
    book; open-location rooms under the book whose scope_location_id
    matches the location (falling back to chat canon).

    Retire-not-delete: a room that was live in THIS frame's pre-turn scene
    but is absent from the post-merge scene lost its live existence this
    beat (diff remove_rooms, the mapping remove_rooms self-heal, or
    destruction) -- its registry row is marked retired, never deleted.
    Diffing prev vs post scene (rather than registry vs scene) is what
    keeps this frame-safe: rooms living only in a SIBLING frame's scene
    are simply never mentioned, so their rows are left untouched."""
    rooms = sc.get("rooms") or {}
    anchor_books = _anchored_book_ids(cid)
    location_slug = normalize_room_id(str(sc.get("location") or ""))
    location_book = None
    if location_slug:
        # retired_turn_id filter: rooms minted after a region's
        # destruction must not register under the dead book -- they fall
        # back to chat canon (the ruin's registry is closed history).
        row = q(
            "SELECT id FROM lorebooks WHERE chat_id=? AND "
            "scope_location_id=? AND retired_turn_id IS NULL "
            "ORDER BY id LIMIT 1",
            (cid, location_slug), one=True,
        )
        location_book = row["id"] if row else None
    default_book = location_book or canon_book_id

    existing = {
        row["room_uid"]: row
        for row in q("SELECT * FROM room_registry WHERE chat_id=?", (cid,))
    }

    upserts = []
    for rid, rdef in rooms.items():
        if not isinstance(rdef, dict):
            continue
        rid = str(rid)
        owner = rdef.get("parent_entity")
        book_id = anchor_books.get(owner) if owner else default_book
        if not book_id:
            continue
        name = str(rdef.get("name") or rid)
        row = existing.get(rid)
        # Aliases ACCUMULATE across renames (old names kept, new appended):
        # identity is the registry's whole job, so a room re-minted under a
        # name it carried three beats ago must still dedup onto its row.
        prior = []
        if row is not None:
            try:
                prior = list(json.loads(row["aliases"] or "[]"))
            except Exception:
                prior = []
        aliases = list(dict.fromkeys(
            [*prior, name, rid.replace("_", " ")]))
        if row is not None \
                and row["owning_book_id"] == book_id \
                and row["parent_entity"] == owner \
                and row["name"] == name \
                and row["aliases"] == json.dumps(aliases) \
                and row["retired_turn_id"] is None:
            continue  # already registered, identical, live
        upserts.append({
            "room_uid": rid, "owning_book_id": book_id,
            "parent_entity": owner, "name": name, "aliases": aliases,
        })

    prev_rooms = {str(r) for r in (prev_scene.get("rooms") or {})}
    retire = sorted(
        rid for rid in prev_rooms - {str(r) for r in rooms}
        if rid in existing and existing[rid]["retired_turn_id"] is None
    )
    return {"upserts": upserts, "retire": retire}


def _apply_room_registry(cid, turn_id, registry):
    """Write the prepared registry mutations (inside commit_scene's
    transaction). Upsert revives a retired row when the same key is
    genuinely re-minted live -- same key in the same chat is the same
    identity; the registry records that it exists again."""
    for rid in registry.get("retire") or []:
        qi(
            "UPDATE room_registry SET retired_turn_id=? "
            "WHERE chat_id=? AND room_uid=? AND retired_turn_id IS NULL",
            (turn_id, cid, rid),
        )
    for row in registry.get("upserts") or []:
        qi(
            "INSERT INTO room_registry"
            "(chat_id,room_uid,owning_book_id,parent_entity,name,aliases,"
            "payload,created_turn_id,retired_turn_id) "
            "VALUES(?,?,?,?,?,?,?,?,NULL) "
            "ON CONFLICT(chat_id,room_uid) DO UPDATE SET "
            "owning_book_id=excluded.owning_book_id,"
            "parent_entity=excluded.parent_entity,"
            "name=excluded.name,"
            "aliases=excluded.aliases,"
            "retired_turn_id=NULL",
            (cid, row["room_uid"], row["owning_book_id"],
             row["parent_entity"], row["name"], json.dumps(row["aliases"]),
             "{}", turn_id),
        )

def sync_room_registry_with_scene(cid, canon_book_id, prev_scene, scene):
    """Reconcile the room_registry projection with a scene blob replaced
    OUTSIDE commit_scene (the manual world editor in app.py's world_put --
    the one scene writer that historically bypassed the registry, leaving
    hand-added rooms unregistered until the next commit and hand-removed
    rooms live in the registry forever). Same prepare/apply pair the commit
    domain uses, so the projection semantics cannot fork.

    Rooms that lost live existence are retired stamped with the chat's
    latest turn (a manual edit has no turn of its own); with no turns yet
    there is nothing meaningful to retire against and the retire pass is a
    no-op, while registration still proceeds."""
    registry = _prepare_room_registry(cid, canon_book_id, prev_scene, scene)
    latest = q("SELECT id FROM turns WHERE chat_id=? ORDER BY idx DESC LIMIT 1",
               (cid,), one=True)
    if latest is None:
        registry["retire"] = []
    _apply_room_registry(cid, latest["id"] if latest else None, registry)
    return registry


def prepare_scene_commit(ctx):
    """Build the exact post-turn scene without mutating durable state.

    Keeping scene preparation pure lets the top-level commit prepare memory
    embeddings and other slow derived work before SQLite's outer write
    transaction begins.  It also gives every later commit domain one stable
    post-diff scene instead of independently reconstructing it.
    """
    chat = ctx.chat
    cid = chat.id
    res = ctx.director_resolve or ctx.director_establish or {}
    # Deep-copied before the dedup pass below rewrites room keys: the
    # resolve step/variant holding this diff was already persisted, and
    # mutating the shared dict would desync it from what was saved.
    diff = copy.deepcopy(res.get("state_diff") or {})
    prev_scene = wget(cid, "scene", {}) or {}
    destruction = _prepare_destruction(
        cid, prev_scene, diff, add_warning=ctx.add_warning)
    room_renames = dedup_minted_rooms(
        cid, prev_scene, diff, add_warning=ctx.add_warning)
    _guard_occupied_mover_removal(
        prev_scene, diff,
        doomed={destruction["target"]: destruction["doomed_rooms"]}
        if destruction else None)

    # Fold mapping's advisory MAP DETAIL (within-room `anchors`, `size`, and
    # compass `dir`/`vertical` on edges) into the Director's causal diff BEFORE
    # the merge -- so it passes through the merge's bearing reciprocity and
    # station-anchor normalization like any authored room, and a station keyed
    # to a mapping-authored anchor is not stranded by normalize_scene_stations
    # running on an anchorless room. Confirmed live: every model authored
    # anchors in scene_patch, but the Director drops them when echoing rooms
    # (like it drops remove_rooms below). Fill ONLY fields the Director's room
    # LACKS (it wins if it echoed them); apply room_renames so a rekeyed minted
    # room keeps its detail; never CREATE a room the Director itself didn't.
    _mapping_patch = ((ctx.mapping_stage or {}).get("scene_patch")
                      or (ctx.mapping_quick or {}).get("scene_patch") or {})
    _diff_rooms = diff.get("rooms")
    if isinstance(_diff_rooms, dict):
        for _rid, _mroom in (_mapping_patch.get("rooms") or {}).items():
            _droom = _diff_rooms.get(room_renames.get(_rid, _rid))
            if not isinstance(_droom, dict) or not isinstance(_mroom, dict):
                continue
            for _f in ("anchors", "size"):
                if _mroom.get(_f) and not _droom.get(_f):
                    _droom[_f] = _mroom[_f]
            _medges = {e.get("to"): e for e in (_mroom.get("adjacent") or [])
                       if isinstance(e, dict) and e.get("to")}
            for _edge in (_droom.get("adjacent") or []):
                _me = _medges.get(_edge.get("to")) if isinstance(_edge, dict) else None
                for _k in ("dir", "vertical"):
                    if _me and _me.get(_k) and not _edge.get(_k):
                        _edge[_k] = _me[_k]

    sc = merge_scene_with_diff(prev_scene, diff)
    if destruction:
        # Guard-approved departures (cast_changes) left stale positions
        # that merge's occupied-room refusal honored; vacate them and
        # drop the doomed rooms they kept alive (see the vacated note in
        # _prepare_destruction). The guard has already proven every
        # doomed-room occupant repositioned or departed, so this pop can
        # never lose a person.
        for name in destruction.get("vacated") or []:
            (sc.get("positions") or {}).pop(name, None)
        for rid in destruction.get("doomed_rooms") or []:
            (sc.get("rooms") or {}).pop(rid, None)

    staged = (
        (ctx.mapping_stage or {}).get("staged_lore") or []
    ) + (
        (ctx.mapping_quick or {}).get("staged_lore") or []
    )
    interp = ctx.director_interpret or {}
    mv = interp.get("movement")
    target_room = mv.get("to_room") if isinstance(mv, dict) else None
    target_room = room_renames.get(target_room, target_room)

    if target_room and target_room not in sc.get("rooms", {}):
        for entry in staged:
            if entry.get("category") == "layout" and entry.get("content"):
                sc.setdefault("rooms", {})[target_room] = {
                    "name": target_room.replace("_", " ").title(),
                    "desc": entry["content"],
                    "adjacent": [],
                    "notes": entry["content"][:500],
                }
                break

    # Mapping's scene_patch is advisory -- the Director is expected to fold
    # it into state_diff -- but models reliably echo room CREATIONS while
    # dropping remove_rooms cleanup (observed live: mapping proposed
    # remove_rooms for a duplicate room on two consecutive turns and the
    # resolve diff carried neither, so the stray room persisted forever).
    # Room removal is map curation, not causality, so the mapping agent's
    # removals apply deterministically here -- conservatively: never a room
    # this turn's diff (re)asserts, never an occupied room, never an entity
    # interior, never a room any transit state still targets.
    mapping_patch = ((ctx.mapping_stage or {}).get("scene_patch")
                     or (ctx.mapping_quick or {}).get("scene_patch") or {})
    proposed_removals = [str(r) for r in (mapping_patch.get("remove_rooms")
                                          or []) if r]
    if proposed_removals:
        rooms = sc.get("rooms") or {}
        protected = set((diff.get("rooms") or {}).keys())
        protected.update(str(v) for v in (sc.get("positions") or {}).values())
        if target_room:
            protected.add(str(target_room))
        for ent in (sc.get("entities") or {}).values():
            if not isinstance(ent, dict):
                continue
            protected.update(str(r) for r in (ent.get("interior_rooms") or []))
            state = ent.get("state")
            transit = state.get("transit") if isinstance(state, dict) else None
            if isinstance(transit, dict):
                protected.add(str(transit.get("destination_room") or ""))
                protected.add(str(transit.get("route_room") or ""))
        removed = set()
        for rid in proposed_removals:
            room = rooms.get(rid)
            if rid in protected or not isinstance(room, dict) \
                    or room.get("parent_entity"):
                continue
            rooms.pop(rid)
            removed.add(rid)
        for room in rooms.values():
            if removed and isinstance(room, dict) and room.get("adjacent"):
                room["adjacent"] = [
                    e for e in room["adjacent"]
                    if not (isinstance(e, dict) and e.get("to") in removed)
                ]

    for k, v in (diff.get("overlays") or {}).items():
        cur = sc.setdefault("overlays", {}).setdefault(k, [])
        for it in (v if isinstance(v, list) else [v]):
            if it not in cur:
                cur.append(it)
        sc["overlays"][k] = cur[-6:]

    att = sc.setdefault("attire", {})
    for name, d in (diff.get("attire") or {}).items():
        if not isinstance(d, dict):
            continue
        cur = att.setdefault(name, {"wearing": [], "state": []})
        cur.setdefault("wearing", [])
        cur.setdefault("state", [])
        if "wearing" in d and not any(k in d for k in ("add", "remove", "replace")):
            cur["wearing"] = sanitize_attire_items(list(d.get("wearing") or []))
            if d.get("state") is not None:
                cur["state"] = d["state"] if isinstance(d["state"], list) else [d["state"]]
            continue
        if isinstance(d.get("replace"), list):
            cur["wearing"] = sanitize_attire_items(list(d["replace"]))
        for it in d.get("add") or []:
            it = str(it).strip()
            if it and it not in cur["wearing"]:
                cur["wearing"].append(it)
        cur["wearing"] = sanitize_attire_items(cur["wearing"])
        for it in d.get("remove") or []:
            if it in cur["wearing"]:
                cur["wearing"].remove(it)
        if d.get("state") is not None:
            cur["state"] = d["state"] if isinstance(d["state"], list) else [d["state"]]

    est = ctx.director_establish
    if est:
        sc["location"] = est.get("location", sc.get("location"))
        sc["time"] = est.get("time", sc.get("time"))
        sc["description"] = est.get("scene_description", sc.get("description"))

    clock = None
    if diff.get("time"):
        td = diff["time"]
        if isinstance(td, dict):
            clock = wget(cid, "simulation_clock", {"elapsed_seconds": 0.0, "display": "now"})
            clock["elapsed_seconds"] = float(td.get("end_seconds", clock.get("elapsed_seconds", 0.0)))
            if td.get("display_advance"):
                clock["display"] = td["display_advance"]
            sc["time"] = td.get("display_advance", sc.get("time"))
        elif isinstance(td, str):
            sc["time"] = td

    infer_vehicle_zones(cid, ctx.turn.frame_id, prev_scene, sc)
    _carry_names = [character_name(json.loads(c["sheet"])) for c in ctx.cast]
    infer_companion_carry(
        cid, ctx.turn.frame_id, prev_scene, sc,
        _carry_names,
        diff.get("cast_changes") or [],
    )
    # Per-character orientation (came_from + focus + facing), read by
    # egocentric_frame. Runs AFTER companion-carry so a carried companion's
    # inferred new position is already in sc when its came_from is computed;
    # infer_focus runs after infer_came_from (which clears focus on a
    # disorienting jump); infer_facing runs LAST -- it reads the freshly-set
    # came_from and focus to derive the compass heading left/right depends on.
    infer_came_from(cid, ctx.turn.frame_id, prev_scene, sc, _carry_names)
    infer_focus(cid, ctx.turn.frame_id, prev_scene, sc,
                ctx.get("director_resolve") or {}, _carry_names)
    infer_facing(cid, ctx.turn.frame_id, prev_scene, sc, _carry_names)

    if destruction:
        base_clock = clock or wget(
            cid, "simulation_clock", {"elapsed_seconds": 0.0}) or {}
        _finalize_destruction_news(
            destruction, cid, ctx.turn.frame_id, ctx.turn,
            float(base_clock.get("elapsed_seconds") or 0.0))

    return {
        "scene": sc, "clock": clock,
        # The post-dedup, post-destruction diff -- the SAME truth the merged
        # scene was built from. commit_world_entities derives the normalized
        # entity rows from this copy (never the raw step diff), so a room
        # rekeyed by dedup_minted_rooms or an entity removed by a
        # destruction declaration can't leave the world_entities projection
        # disagreeing with the scene blob (Phase 3a: one source of truth,
        # normalized tables are derived projections of it).
        "diff": diff,
        "room_registry": _prepare_room_registry(
            cid, chat.lorebook_id, prev_scene, sc),
        "destruction": destruction,
    }


def commit_scene(ctx, nonce, *, prepared=None):
    prepared = prepared or prepare_scene_commit(ctx)
    sc = prepared["scene"]
    registry = prepared.get("room_registry") or {}
    with transaction():
        if prepared.get("clock") is not None:
            wset(ctx.chat.id, "simulation_clock", prepared["clock"])
        wset(ctx.chat.id, "scene", sc)
        sync_anchored_books(ctx.chat.id, sc)
        # Dual-write the room registry beside the scene blob, inside the
        # same commit domain (see the registry block comment): identity/
        # retirement bookkeeping, never a second authority over live rooms.
        _apply_room_registry(ctx.chat.id, ctx.turn.id, registry)
        if prepared.get("destruction"):
            _apply_destruction(
                ctx.chat.id, ctx.turn.id, prepared["destruction"])
    return sc

# ---- Mechanics sweep: timed arrivals, expiry, news, engine notices ----

def commit_transit_sweep(ctx, nonce, *, prepared=None):
    """Commit-domain wrapper around mechanics.mechanics_sweep, run FIRST
    among commit_all's domains -- the sweep mutates the PREPARED scene, and
    commit_scene (which runs after it) is what persists those effects.

    The ordered passes themselves -- (a) fire due scheduled events for THIS
    frame (transit arrivals + news arrivals), (b) schedule new arrivals,
    (c) condition expiry, (d) dock-edge recompute, (e) vehicle-zone/
    companion-carry inference -- live in mechanics.py (see its module
    docstring for the contract). This wrapper only feeds it the database
    rows and applies the event_ops it returns: all writes run inside the
    caller's transaction (nested transaction() is a savepoint), and
    checkpoint restore snapshots scheduled_events/world_conditions whole,
    so a rerolled turn reproduces the exact pending/fired state.
    """
    cid = ctx.chat.id
    frame_id = ctx.turn.frame_id
    prepared = prepared or prepare_scene_commit(ctx)
    sc = prepared["scene"]
    clock = prepared.get("clock") or wget(cid, "simulation_clock", {}) or {}
    res = ctx.director_resolve or ctx.director_establish or {}
    diff = res.get("state_diff") or {}
    cast_names = [character_name(json.loads(c["sheet"])) for c in ctx.cast]

    with transaction():
        pending = [dict(r) for r in q(
            "SELECT * FROM scheduled_events WHERE chat_id=? AND "
            "status='pending' AND kind IN ('transit_arrival','news_arrival') "
            "ORDER BY due_at",
            (cid,),
        )]
        conditions = [dict(r) for r in q(
            "SELECT condition_id, expires_at FROM world_conditions "
            "WHERE chat_id=? AND active=1",
            (cid,),
        )]
        prev_scene = wget(cid, "scene", {}) or {}

        _, event_ops, notices = mechanics_sweep(
            sc, clock, frame_id, pending,
            conditions=conditions, prev_scene=prev_scene, chat_id=cid,
            turn_id=ctx.turn.id, turn_idx=ctx.turn.idx,
            cast_names=cast_names,
            cast_changes=diff.get("cast_changes") or [],
        )

        kind_by_id = {row["event_id"]: row["kind"] for row in pending}
        fired = scheduled = expired = news_fired = 0
        for op in event_ops:
            if op[0] == "status":
                _, event_id, status = op
                # chat_id in the WHERE: event ids are per-chat since the
                # (chat_id, event_id) repartition -- a same-install import
                # keeps the source chat's ids verbatim, so an unscoped
                # update would flip BOTH chats' rows.
                qtx("UPDATE scheduled_events SET status=? "
                    "WHERE chat_id=? AND event_id=?",
                    (status, cid, event_id))
                if status == "fired":
                    if kind_by_id.get(event_id) == "news_arrival":
                        news_fired += 1
                    else:
                        fired += 1
            elif op[0] == "schedule":
                row = op[1]
                qtx(
                    "INSERT OR REPLACE INTO scheduled_events"
                    "(event_id,chat_id,due_at,kind,location_id,payload,seed,"
                    "status) VALUES(?,?,?,?,?,?,?,?)",
                    (row["event_id"], row["chat_id"], row["due_at"],
                     row["kind"], row["location_id"], row["payload"],
                     row["seed"], row["status"]),
                )
                scheduled += 1
            elif op[0] == "expire_condition":
                qtx("UPDATE world_conditions SET active=0 "
                    "WHERE chat_id=? AND condition_id=?", (cid, op[1]))
                expired += 1

        wset(cid, "engine_notices", notices)

    return {"fired": fired, "scheduled": scheduled, "expired": expired,
            "news_fired": news_fired, "notices": notices}

# ---- Cast changes ----

def commit_cast_changes(ctx, nonce):
    chat = ctx.chat
    cid = chat.id
    res = ctx.director_resolve or {}
    diff = res.get("state_diff") or {}
    name2id = {
        r["name"].lower(): r["id"]
        for r in q(
            "SELECT ch.id, ch.name FROM chat_chars cc "
            "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
            (cid,),
        )
    }
    frame_id = ctx.turn.frame_id
    with transaction():
        for chg in (diff.get("cast_changes") or []):
            who = str(chg.get("who") or "").lower().strip()
            stt = chg.get("status")
            if stt in ("active", "dormant") and who in name2id:
                set_char_status(cid, name2id[who], stt, frame_id=frame_id)

# ---- World entity commit ----

def commit_world_entities(ctx, nonce, *, prepared=None):
    """Commit world entities, conditions (and legacy placement cleanup).

    The normalized world_entities rows are a DERIVED projection of the
    scene commit: when the caller passes prepare_scene_commit's result
    (commit_all always does), the entity definitions come from its
    post-dedup/post-destruction diff -- the same truth the scene blob was
    merged from -- so the projection cannot disagree with the blob about
    rekeyed rooms or a destroyed entity. The raw step diff remains the
    fallback for direct callers that never prepared a scene commit.
    """
    chat = ctx.chat
    cid = chat.id
    if prepared is not None and isinstance(prepared.get("diff"), dict):
        diff = prepared["diff"]
    else:
        res = ctx.director_resolve or ctx.director_establish or {}
        diff = res.get("state_diff") or {}
    turn_id = ctx.turn.id

    with transaction() as c:
        for entity_id, entity_def in (diff.get("entities") or {}).items():
            if not isinstance(entity_def, dict):
                continue
            existing = q("SELECT entity_id FROM world_entities WHERE entity_id=? AND chat_id=?",
                         (entity_id, cid), one=True)
            payload = json.dumps(entity_def, ensure_ascii=False)
            if existing:
                c.execute(
                    "UPDATE world_entities SET kind=?,subtype=?,name=?,payload=? "
                    "WHERE entity_id=? AND chat_id=?",
                    (entity_def.get("kind", "object"),
                     entity_def.get("subtype", ""),
                     entity_def.get("name", ""),
                     payload, entity_id, cid),
                )
            else:
                c.execute(
                    """INSERT INTO world_entities(entity_id,chat_id,kind,subtype,name,payload,created_turn_id)
                    VALUES(?,?,?,?,?,?,?)""",
                    (entity_id, cid, entity_def.get("kind", "object"),
                     entity_def.get("subtype", ""), entity_def.get("name", ""),
                     payload, turn_id),
                )
                # Deterministic vehicle-lorebook creation -- an entity
                # with interior_rooms is an enterable mobile place (a
                # ship, a TARDIS), exactly what LOREBOOK_TYPES' "vehicle"
                # book type exists for. Found live: the model reliably
                # marks these entities kind="vehicle" with interior_rooms
                # but never proposes a lorebook for them on its own, so
                # everything about them piled up as flat entries in the
                # single chat-wide canon book instead of its own book.
                # Created here (deterministically, not model-proposed) so
                # it works at zero model compliance; sync_anchored_books
                # (called at the end of commit_scene, which runs before
                # this domain) then keeps it following the entity as it
                # moves, and commit_mapping's lorebook_manifest already
                # shows it to the model this same turn, so entries route
                # into it instead of canon without any extra plumbing.
                if entity_def.get("kind") == "vehicle" and entity_def.get("interior_rooms"):
                    # Canonical-anchor comparison, not raw id equality: a
                    # re-coined alias id for an existing vehicle
                    # ('tamsin_ferry_entity' vs 'ferry_tamsin') must find
                    # that vehicle's existing book, not mint a second one.
                    alias_map = _entity_alias_map(cid)
                    canon = _canonical_anchor(entity_id, alias_map)
                    has_book = any(
                        _canonical_anchor(r["anchor_entity_id"], alias_map)
                        == canon
                        for r in c.execute(
                            "SELECT anchor_entity_id FROM lorebooks "
                            "WHERE chat_id=? AND anchor_entity_id IS NOT NULL",
                            (cid,),
                        ).fetchall()
                    )
                    if not has_book:
                        c.execute(
                            "INSERT INTO lorebooks(name,chat_id,book_type,summary,parent_id,"
                            "anchor_entity_id,resource_uid) VALUES(?,?,?,?,?,?,?)",
                            (
                                entity_def.get("name") or entity_id, cid, "vehicle",
                                f"Everything concerning {entity_def.get('name') or entity_id}.",
                                chat.lorebook_id, entity_id, new_uid("book"),
                            ),
                        )

        for entity_id in (diff.get("remove_entities") or []):
            c.execute("DELETE FROM world_entities WHERE entity_id=? AND chat_id=?",
                      (entity_id, cid))
            c.execute("DELETE FROM world_placements WHERE subject_id=? AND chat_id=?",
                      (entity_id, cid))

        for cond_id, cond_list in (diff.get("conditions") or {}).items():
            if not isinstance(cond_list, list):
                cond_list = [cond_list]
            for cond in cond_list:
                if not isinstance(cond, dict):
                    continue
                cid_val = cond.get("condition_id") or cond_id
                existing = q("SELECT condition_id FROM world_conditions "
                             "WHERE condition_id=? AND chat_id=?",
                             (cid_val, cid), one=True)
                payload = json.dumps(cond, ensure_ascii=False)
                if existing:
                    c.execute(
                        """UPDATE world_conditions SET subject_id=?,kind=?,payload=?,active=?
                        WHERE condition_id=? AND chat_id=?""",
                        (cond.get("subject_id", ""), cond.get("kind", ""),
                         payload, int(cond.get("active", 1)), cid_val, cid),
                    )
                else:
                    c.execute(
                        """INSERT INTO world_conditions(condition_id,chat_id,subject_id,kind,
                        started_at,expires_at,next_tick,payload,active) VALUES(?,?,?,?,?,?,?,?,?)""",
                        (cid_val, cid, cond.get("subject_id", ""), cond.get("kind", ""),
                         cond.get("started_at_seconds", 0.0),
                         cond.get("expires_at_seconds"),
                         cond.get("next_tick_seconds"),
                         payload, 1),
                    )

    return {"entities_committed": len(diff.get("entities") or {}),
            "entities_removed": len(diff.get("remove_entities") or [])}

# ---- Mapping commit ----

def _known_name_roster(chat, cast):
    """Exact display names perception.py's recognition check requires:
    known[perceiver_name] must contain the OTHER actor's exact name string
    for `actor_name in recognized_sources` to ever match. The persona/player
    name and every cast member's character_name() output are the only
    strings that check will ever compare against.
    """
    from scene import persona_of
    pers = persona_of(chat)
    roster = []
    if isinstance(pers, dict):
        name = pers.get("identity", {}).get("name")
        if name:
            roster.append(name)
    for row in cast:
        roster.append(character_name(json.loads(row["sheet"])))
    return roster

def _resolve_roster_name(value, roster):
    """mapping_commit's prompt allows 'who'/'learns' to be 'a name or brief
    descriptor' -- free text like 'Dana Osei -- supply pilot, claims three
    days of unanswered radio contact' has been observed live, instead of the
    bare exact name perception.py's recognition check requires. Resolve to
    the roster's canonical spelling (exact match, or the value containing a
    roster name as a substring); if it doesn't resolve to anyone in the
    roster, drop it rather than write a value that can never match and would
    permanently leave that perceiver unable to recognize anyone.
    """
    text = str(value or "").strip()
    if not text:
        return None
    for name in roster:
        if text.casefold() == name.casefold():
            return name
    for name in roster:
        if name.casefold() in text.casefold():
            return name
    return None

# ---- Background-presence tracking (promotion candidates) ----

BACKGROUND_PROMOTION_DIALOGUE_THRESHOLD = 2
BACKGROUND_PROMOTION_MENTION_THRESHOLD = 4

_BACKGROUND_NAME_TITLE_WORDS = {
    "dr", "mr", "mrs", "ms", "the", "a", "an", "captain", "commander",
    "lieutenant", "sir", "madam", "professor", "doctor",
}

def _background_name_mentioned(name, text):
    """resolved_event prose almost never repeats someone's full tracked
    name after their first introduction -- "Crusher" carries a scene once
    "Dr. Crusher" has been established -- so a plain substring check
    against the full name would undercount real mentions. Fall back to
    any significant word of the name (title words and short filler
    stripped) appearing at a word boundary."""
    text_cf = text.casefold()
    name_cf = name.casefold()
    if re.search(rf"\b{re.escape(name_cf)}\b", text_cf):
        return True
    words = [w.strip(".,;:").casefold() for w in name.split()]
    significant = [
        w for w in words
        if w and w not in _BACKGROUND_NAME_TITLE_WORDS and len(w) >= 3
    ]
    return any(
        re.search(rf"\b{re.escape(w)}\b", text_cf) for w in significant
    )

def _character_address_of(dr_output, presence_name, roster, scene=None,
                          station_room=None):
    """Return the last hearable dialogue_log entry in which a roster speaker
    (a registered character or the player) aimed a line at this background
    presence, or None -- so a character speaking directly TO an extra can
    trigger that extra's reaction, which resolved_event-prose salience alone
    misses (a character's line rarely names its target in the prose).

    Fail-closed on concealment (metadata that rides every entry -- denying on
    it leaks nothing): a line marked visibility=concealed, or concealed FROM
    this presence, never triggers -- the same rule perception.py applies to
    the hear-level backstop. Audibility is enforced only when provable: with a
    known station_room and a resolvable speaker room, the line must be fully
    hearable (a fragment cannot be coherently replied to). When room data is
    absent (best-effort, unlike the always-present concealment flags) the
    address is allowed through on the same co-presence assumption
    background_react already makes about resolved_event -- the check
    self-tightens as sketch coverage grows.
    """
    found = None
    for d in (dr_output.get("dialogue_log") or []):
        speaker = str(d.get("speaker") or "").strip()
        if not speaker or speaker.casefold() not in roster:
            continue
        target = str(d.get("intended_target") or "").strip()
        if not target or not _background_name_mentioned(presence_name, target):
            continue
        if str(d.get("visibility") or "").casefold() == "concealed":
            continue
        if any(_background_name_mentioned(presence_name, str(c))
               for c in (d.get("conceal_from") or [])):
            continue
        if station_room and scene:
            sp_room = _room_of(scene, speaker)
            if sp_room:
                rel = spatial_rel(scene, sp_room, station_room)
                if hear_level(rel, d.get("volume") or "normal") != "full":
                    continue
        found = d  # last hearable address wins
    return found


def _valid_pending_reply(record, turn_idx):
    """The presence's owed reply if it has not yet expired, else None."""
    pr = record.get("pending_reply")
    if not isinstance(pr, dict):
        return None
    if turn_idx > (pr.get("expires_turn") if pr.get("expires_turn") is not None else -1):
        return None
    return pr


def _background_fired_reactions(br):
    """Normalize a background_react result into a list of fired reaction dicts
    ({name, dialogue_log_entry, action}) -- tolerating both the ensemble
    (`reactions` list) shape and the legacy single-entry shape."""
    if not isinstance(br, dict):
        return []
    reactions = br.get("reactions")
    if reactions:
        return [r for r in reactions
                if isinstance(r, dict) and r.get("dialogue_log_entry")]
    if br.get("fired") and br.get("dialogue_log_entry"):
        return [{"name": br.get("name"),
                 "dialogue_log_entry": br["dialogue_log_entry"],
                 "action": br.get("action", "")}]
    return []


# Entity kinds that are clearly NOT agents. Everything else with a name is
# treated as a potential background presence (see track_background_presences).
# Deny-list rather than allow-list because the model's `kind` string is
# freeform: a novel agent kind (monster, creature, robot, drone, spirit, ...)
# must not fall through, whereas a mistracked object is harmless -- it never
# qualifies to react. Ambiguous kinds ("machine", "device") are deliberately
# NOT listed, so a sentient robot tagged that way is still tracked.
_INERT_ENTITY_KINDS = frozenset({
    "object", "item", "fixture", "furniture", "furnishing", "appliance",
    "vehicle", "structure", "building", "terrain", "feature", "landmark",
    "door", "gate", "barrier", "wall", "container", "tool", "weapon",
    "armor", "clothing", "prop", "scenery", "decoration", "plant", "tree",
    "food", "drink", "substance", "material", "resource", "location",
    "room", "area", "zone", "region", "sign", "document", "book", "note",
    "panel", "console", "terminal", "screen", "light", "effect", "hazard",
    "trap", "corpse", "remains",
})

def track_background_presences(ctx, nonce):
    """Deterministic, LLM-free tracking of named entities the director
    keeps writing into resolved_event/dialogue_log who are NOT a
    registered cast member, a persona, or an extra player -- e.g. a
    ship's doctor the director has kept consistently present and active
    across many turns despite her having no character sheet, no
    character_step call, and no memory. This never invents a candidate
    from free prose (no NER over resolved_event) -- only from the same
    structured fields commit already trusts: dialogue_log speakers,
    state_diff.entities with any non-inert kind (see _INERT_ENTITY_KINDS --
    agents named by the model, whatever kind string it used), director_establish's
    top-level entities on the opening turn, and the deterministic
    background_react backstop's own authored line. Once a name is a
    tracked candidate, later resolved_event mentions of that exact name
    are counted (case-insensitive substring) so passing-mention
    frequency can also cross the promotion threshold, without ever
    discovering a new name that way. For structured person/npc defs it
    also harvests a small `sketch` ({role_hint, station_room}) from the
    director's own description/position -- self-knowledge the background
    reactor can be voiced with, never perceived-world state. Purely
    additive bookkeeping for the UI to surface promotion suggestions
    from -- writes nothing into `characters` or `chat_chars` itself.
    """
    chat = ctx.chat
    cid = chat.id
    res = ctx.director_resolve or ctx.director_establish or {}
    is_opening = not ctx.director_resolve  # res fell back to director_establish
    turn_idx = ctx.turn.idx

    roster = {n.casefold() for n in _known_name_roster(chat, ctx.cast)}
    roster |= {(e.get("name") or "").casefold() for e in (ctx.extra_players or [])}

    candidates = set()
    dialogue_speakers = set()  # names that spoke a dialogue_log line this beat
    sketches = {}              # name -> {role_hint, station_room} from structured defs

    # Scene entities are keyed by an opaque id ("char_guard_alpha") but carry
    # a human display name ("Security Guard Alpha"). The director normally
    # voices a background entity by its display name, but sometimes slips and
    # writes the raw entity id into dialogue_log.speaker. Tracked verbatim,
    # that id becomes a SECOND, duplicate presence alongside the real one --
    # fragmenting the figure's dialogue/mention history and, worse, orphaning
    # its owed-reply debt onto the ghost id (observed live: a guard challenges
    # the player under its id, then never gets to answer, because the debt is
    # keyed to the id while the reactor gate ranks the display name). Fold an
    # id-shaped speaker back to its display name before it is ever tracked.
    entity_id_to_name = {
        eid: str((edef or {}).get("name") or "").strip()
        for eid, edef in ((wget(cid, "scene", {}) or {}).get("entities") or {}).items()
        if isinstance(edef, dict) and str((edef or {}).get("name") or "").strip()
    }

    for d in (res.get("dialogue_log") or []):
        speaker = str(d.get("speaker") or "").strip()
        speaker = entity_id_to_name.get(speaker, speaker)
        if speaker and speaker.casefold() not in roster:
            candidates.add(speaker)
            dialogue_speakers.add(speaker.casefold())

    # Structured person/npc entity defs: state_diff.entities on a normal
    # turn, plus director_establish's TOP-LEVEL entities/positions on the
    # opening turn (DirectorEstablish carries them at top level, not inside
    # a state_diff -- so a location-implied presence established at idx 0
    # was previously never tracked until the director happened to restate
    # them). Same no-NER rule: only these already-trusted structured fields.
    diff = res.get("state_diff") or {}
    entity_sources = [((diff.get("entities") or {}), (diff.get("positions") or {}))]
    if is_opening:
        entity_sources.append(((res.get("entities") or {}), (res.get("positions") or {})))
    for entities, positions in entity_sources:
        for entity_def in entities.values():
            if not isinstance(entity_def, dict):
                continue
            # Track any named entity that is not CLEARLY inert. `kind` is a
            # freeform model string with no controlled vocabulary, so an
            # allowlist ("person"/"npc") silently dropped every other agent
            # the model names -- player-declared guards (kind:"actor"),
            # monsters, creatures, robots, spirits, drones -- leaving them
            # captured in the scene but tracked by neither the cast nor the
            # background-presence system: declared, then inert. Enumerating
            # agent kinds is an unwinnable treadmill; instead exclude the
            # clearly non-agent kinds and default to inclusion. A rare
            # mistracked object never reacts anyway (the pick_background_
            # reactors gate requires it to be addressed/owed/voiced), which
            # is far cheaper than an agent that can never act.
            kind = str(entity_def.get("kind") or "").strip().casefold()
            if not kind or kind in _INERT_ENTITY_KINDS:
                continue
            name = str(entity_def.get("name") or "").strip()
            if not name or name.casefold() in roster:
                continue
            candidates.add(name)
            sk = sketches.setdefault(name, {})
            desc = str(entity_def.get("description") or "").strip()
            if desc:
                sk["role_hint"] = desc[:160]
            room = positions.get(name)
            if room:
                sk["station_room"] = str(room)

    # The deterministic backstop (background_react) authored one or more lines
    # this beat for the gate-picked presence(s): persist each as a real
    # dialogue turn so the same figure accrues toward promotion and reads as
    # continuous, rather than being invisible to bookkeeping (it is otherwise
    # merged only for rendering, in agents/perception.py). Each speaker was
    # force-set to its gate-picked name in background_react.
    br = ctx.get("background_react") or {}
    for _r in _background_fired_reactions(br):
        br_name = str((_r.get("dialogue_log_entry") or {}).get("speaker") or "").strip()
        if br_name and br_name.casefold() not in roster:
            candidates.add(br_name)
            dialogue_speakers.add(br_name.casefold())

    presences = wget(cid, "background_presences", {})
    for name in candidates:
        record = presences.setdefault(name, {
            "first_turn": turn_idx, "last_turn": turn_idx,
            "dialogue_turns": [], "mention_turns": [],
        })
        record["last_turn"] = turn_idx
        if name.casefold() in dialogue_speakers:
            if turn_idx not in record["dialogue_turns"]:
                record["dialogue_turns"].append(turn_idx)
        sk = sketches.get(name)
        if sk:
            # Director restated this presence's own description/position ->
            # objective self-knowledge wins; overwrite the prior sketch.
            record.setdefault("sketch", {}).update(sk)

    resolved_event = str(res.get("resolved_event") or "")
    for name, record in presences.items():
        if name in candidates:
            continue
        if _background_name_mentioned(name, resolved_event):
            record["last_turn"] = turn_idx
            if turn_idx not in record["mention_turns"]:
                record["mention_turns"].append(turn_idx)

    # Owed-reply bookkeeping: a registered character (or the player) addressed
    # this presence this beat, but the single-winner gate spent the beat on
    # someone else -- persist a one-beat-grace debt so they can answer next
    # turn (the "if not during the turn, next turn" case). Discharged when the
    # presence is picked (answered, or its silence WAS the answer) and swept
    # when stale, so a reply never surfaces turns later.
    selected_names = {str(n).casefold() for n in ((ctx.get("background_react") or {}).get("selected") or [])}
    if not selected_names:  # legacy single-entry shape
        _sel = str((ctx.get("background_react") or {}).get("name") or "").strip().casefold()
        if _sel:
            selected_names = {_sel}
    sc = wget(cid, "scene", {}) or {}
    for name, record in presences.items():
        pr = record.get("pending_reply")
        if isinstance(pr, dict) and turn_idx > (pr.get("expires_turn")
                                                if pr.get("expires_turn") is not None else -1):
            record.pop("pending_reply", None)
        if name.casefold() in selected_names:
            record.pop("pending_reply", None)  # the moment was theirs; discharged
            continue
        entry = _character_address_of(
            res, name, roster, sc, (record.get("sketch") or {}).get("station_room"))
        if entry:
            record["pending_reply"] = {
                "from": entry.get("speaker"), "quote": entry.get("exact_quote", ""),
                "tone": entry.get("tone", ""), "turn": turn_idx,
                "expires_turn": turn_idx + 2,
            }

    wset(cid, "background_presences", presences)
    return {"tracked": len(presences)}

def _flow_addressed_refs(ctx):
    """Raw flow.addressed_to entries as the director emitted them, preserved
    as flow.addressed_to_refs in schemas.py before int coercion. The string
    entries are the only way the director can mark an UNREGISTERED background
    presence (which has no character id) as the player's addressee; int-like
    refs are registered-character ids and are ignored here (agents/loops.py
    resolves those against the cast)."""
    interp = ctx.get("director_interpret") or {}
    flow = interp.get("flow") if isinstance(interp, dict) else None
    if not isinstance(flow, dict):
        return []
    refs = []
    for ref in (flow.get("addressed_to_refs") or []):
        if isinstance(ref, str):
            text = ref.strip()
            if text and not text.isdigit():
                refs.append(text)
    return refs


def _presence_in_addressed_refs(name, refs):
    return any(
        name.casefold() == ref.casefold()
        or _background_name_mentioned(name, ref)
        for ref in refs
    )


def pick_background_reactor(ctx, dr_output):
    """Single-winner convenience wrapper over pick_background_reactors: the
    top-ranked qualifying background presence, or None. Preserves the original
    gate contract for the common (max_reactors == 1) case and all callers/tests
    that expect one name.
    """
    picks = pick_background_reactors(ctx, dr_output, cap=1)
    return picks[0] if picks else None


def pick_background_reactors(ctx, dr_output, cap=1):
    """Deterministic gate for the background_react stage: pick up to `cap`
    named, unregistered background presences to give an independent
    reaction this beat, when this beat has salience for them but the
    director's own resolved_event/dialogue_log authorship (see prompts.py's
    DIALOGUE LOG background-entity license) gave them nothing anyway. Each
    returned presence qualifies INDEPENDENTLY (addressed / character-addressed
    / owed / mentioned / has history) -- the list is never padded to `cap`.

    This mirrors infer_vehicle_zones' role in spatial_frames.py: a prompt
    clause exists and is sometimes followed, but live play showed it fails
    reliably enough under sustained narrative pressure (a background
    presence given direct orders, addressed by name, present at a caught
    theft and an alarm, still rendered as "motionless" for 25+ turns) that
    a deterministic backstop is needed rather than further prompt tuning
    alone -- the same lesson this codebase has already learned for zone
    tagging and speech concealment.

    Returns [] when no candidate qualifies (the common case -- most turns
    have no salient, un-voiced background presence at all). cap defaults to 1,
    reproducing the historical single-winner behavior exactly -- with one
    exception: a presence the director's flow.addressed_to named (a direct
    player address, see _flow_addressed_refs) is FORCED into the picks,
    bypassing `cap` if necessary, so a directly-addressed background NPC
    always gets to answer with its own line instead of being displaced by a
    merely-standing presence or a foreground character's interception.
    """
    chat = ctx.chat
    cid = chat.id

    roster = {n.casefold() for n in _known_name_roster(chat, ctx.cast)}
    roster |= {(e.get("name") or "").casefold() for e in (ctx.extra_players or [])}

    voiced_this_beat = {
        str(d.get("speaker") or "").casefold()
        for d in (dr_output.get("dialogue_log") or [])
    }
    diff = dr_output.get("state_diff") or {}
    for entity_def in (diff.get("entities") or {}).values():
        if isinstance(entity_def, dict) and entity_def.get("name"):
            voiced_this_beat.add(str(entity_def["name"]).casefold())

    resolved_event = str(dr_output.get("resolved_event") or "")
    player_input = str(ctx.get("input") or "")
    turn_idx = ctx.turn.idx
    sc = wget(cid, "scene", {}) or {}
    presences = wget(cid, "background_presences", {})

    addressed_refs = _flow_addressed_refs(ctx)

    candidates = []
    forced = 0
    for name, record in presences.items():
        cf = name.casefold()
        if cf in roster or cf in voiced_this_beat:
            continue
        # The director's own flow plan named this presence as the player's
        # addressee -- the strongest possible salience signal, and one the
        # raw-text checks below can miss entirely (an address by role or
        # epithet never mentions the tracked name).
        flow_addressed = _presence_in_addressed_refs(name, addressed_refs)
        addressed = _background_name_mentioned(name, player_input)
        # A registered character (or the player) who spoke directly TO this
        # presence this beat -- read-only here; the owed-reply debt is written
        # at commit (track_background_presences), never in this pre-commit gate.
        station_room = (record.get("sketch") or {}).get("station_room")
        char_addr = _character_address_of(dr_output, name, roster, sc, station_room)
        owed = _valid_pending_reply(record, turn_idx)
        mentioned = _background_name_mentioned(name, resolved_event)
        dialogue_turns = record.get("dialogue_turns") or []
        if not (flow_addressed or addressed or char_addr or owed
                or mentioned or dialogue_turns):
            continue
        if flow_addressed:
            forced += 1
        priority = (bool(flow_addressed), bool(addressed), bool(char_addr),
                    bool(owed), bool(mentioned), len(dialogue_turns),
                    record.get("last_turn") or -1)
        candidates.append((priority, name))

    if not candidates:
        return []
    candidates.sort(reverse=True)
    # Every flow-addressed presence sorts first (top priority bit) and must
    # answer THIS beat: widen the cap to fit them all, then fill any slots
    # left up to `cap` with the normally-ranked candidates.
    slots = max(forced, max(0, int(cap)))
    return [name for _, name in candidates[:slots]]

def promotable_background_presences(chat_id):
    presences = wget(chat_id, "background_presences", {})
    out = []
    for name, record in presences.items():
        promotable = (
            len(record.get("dialogue_turns") or []) >= BACKGROUND_PROMOTION_DIALOGUE_THRESHOLD
            or len(record.get("mention_turns") or []) >= BACKGROUND_PROMOTION_MENTION_THRESHOLD
        )
        out.append({
            "name": name,
            "first_turn": record.get("first_turn"),
            "last_turn": record.get("last_turn"),
            "dialogue_turns": record.get("dialogue_turns") or [],
            "mention_turns": record.get("mention_turns") or [],
            "promotable": promotable,
        })
    out.sort(key=lambda r: (-r["promotable"], -(r["last_turn"] or 0)))
    return out


def promote_background_character(cid, name, sheet=None, memory_seeds=None):
    """Attach a tracked background presence as a real character: mint the
    characters/chat_chars rows, seed her scene position, mutual recognition
    with the player and every registered cast member, and any starter
    memories, then drop the presence record. Forward-only: past turns'
    steps/variants are untouched -- she becomes character_step-eligible
    starting next turn, the same as manually attaching any other character
    mid-chat.

    `sheet`/`memory_seeds` are the reviewed draft when called from the
    confirm-promotion route (app.py); when omitted (the autonomous path,
    see auto_promote_background_characters) a sheet is minted from the
    chat's own events record via importers.draft_promoted_character -- an
    LLM call, so this must never run inside the turn's commit transaction.
    Returns the new character id.
    """
    from importers import draft_promoted_character
    from scene import persona_of

    if sheet is None:
        draft = draft_promoted_character(cid, name)
        sheet = draft["sheet"]
        if memory_seeds is None:
            memory_seeds = draft["memory_seeds"]

    sheet = normalize_character_data(sheet)
    memory_seeds = [str(m) for m in (memory_seeds or []) if str(m).strip()]

    char_id = qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        (
            character_name(sheet), json.dumps(sheet, ensure_ascii=False),
            json.dumps({"format": "promoted", "chat_id": cid}, ensure_ascii=False),
            time.time(),
        ),
    )
    qi(
        "INSERT INTO chat_chars(chat_id,char_id,status) VALUES(?,?,'active')",
        (cid, char_id),
    )

    chat_row = dict(q("SELECT * FROM chats WHERE id=?", (cid,), one=True))
    sc = wget(cid, "scene", None)
    if isinstance(sc, dict):
        positions = sc.setdefault("positions", {})
        if character_name(sheet) not in positions:
            player_name = persona_name(persona_of(chat_row))
            positions[character_name(sheet)] = positions.get(player_name)
        wset(cid, "scene", sc)

    # Seed mutual recognition with the player and with every other
    # already-registered cast member -- she's been part of the scene the
    # whole time, so treating her as a stranger to everyone else present
    # would be as wrong as it was to treat her as a stranger to the player.
    cast_rows = q(
        "SELECT ch.sheet FROM chat_chars cc JOIN characters ch ON ch.id=cc.char_id "
        "WHERE cc.chat_id=? AND cc.status='active' AND ch.id!=?",
        (cid, char_id),
    )
    roster = _known_name_roster(chat_row, cast_rows)
    known = wget(cid, "known", {})
    her_name = character_name(sheet)
    known.setdefault(her_name, [])
    for other in roster:
        if other not in known[her_name]:
            known[her_name].append(other)
        known.setdefault(other, [])
        if her_name not in known[other]:
            known[other].append(her_name)
    wset(cid, "known", known)

    if memory_seeds:
        add_memories_batch([
            {
                "chat_id": cid, "char_id": char_id, "turn_id": None,
                "kind": "episode", "provenance": "witnessed", "salience": 0.6,
                "content": seed, "turn_idx": None,
                "event_key": f"promotion:{cid}:{char_id}:{i}",
            }
            for i, seed in enumerate(memory_seeds)
        ])

    presences = wget(cid, "background_presences", {})
    presences.pop(name, None)
    wset(cid, "background_presences", presences)

    return char_id


# The autonomous path demands more accrued voice than the UI's "promotable"
# badge (dialogue threshold 2): auto-minting a full character is irreversible
# spend, so it waits for one more beat of demonstrated salience.
AUTO_PROMOTE_DIALOGUE_THRESHOLD = 3


def _auto_promote_enabled():
    value = str(get_setting("auto_promote") or "").strip().casefold()
    return value not in ("0", "off", "false", "no")


def auto_promote_background_characters(ctx):
    """Commit-side sweep: autonomously promote the single most-deserving
    tracked background presence that has crossed the auto-threshold --
    promotable (see promotable_background_presences) AND at least
    AUTO_PROMOTE_DIALOGUE_THRESHOLD dialogue turns AND present/addressed
    THIS beat. Promotion used to be UI-only (app.py's draft/confirm
    routes were promotable_background_presences' sole callers), so a
    deserving presence could stay shallow forever in hands-off play.

    At most one promotion per beat: each mints a sheet with an LLM call,
    and any remaining qualifiers stay tracked and promote on a later beat.
    Runs AFTER the turn's primary transaction (see _commit_all_locked) --
    it is additive and forward-only, so a failure is a warning, never a
    rollback. Gated by setting('auto_promote'), default on.
    """
    if not _auto_promote_enabled():
        return {"promoted": []}
    cid = ctx.chat.id
    turn_idx = ctx.turn.idx
    presences = wget(cid, "background_presences", {}) or {}
    if not presences:
        return {"promoted": []}

    promotable = {
        r["name"] for r in promotable_background_presences(cid) if r["promotable"]
    }
    selected = {
        str(n).casefold()
        for n in ((ctx.get("background_react") or {}).get("selected") or [])
    }
    addressed_refs = _flow_addressed_refs(ctx)

    candidates = []
    for name, record in presences.items():
        if name not in promotable:
            continue
        dialogue_turns = record.get("dialogue_turns") or []
        if len(dialogue_turns) < AUTO_PROMOTE_DIALOGUE_THRESHOLD:
            continue
        # "Present/addressed this beat": their record was touched this turn
        # (spoke / mentioned), the gate picked them, a character's address
        # left them an owed reply this turn, or the director's flow named
        # them as the player's addressee.
        active = (
            record.get("last_turn") == turn_idx
            or name.casefold() in selected
            or (record.get("pending_reply") or {}).get("turn") == turn_idx
            or _presence_in_addressed_refs(name, addressed_refs)
        )
        if not active:
            continue
        candidates.append(
            (len(dialogue_turns), record.get("last_turn") or -1, name))

    if not candidates:
        return {"promoted": []}
    candidates.sort(reverse=True)
    name = candidates[0][-1]
    char_id = promote_background_character(cid, name)
    return {"promoted": [{"name": name, "char_id": char_id}]}

# Filler tokens ignored when reducing an entity id / display name to its
# canonical token key ("ferry_tamsin" vs "tamsin_ferry_entity" must meet).
_GENERIC_ID_TOKENS = {"the", "a", "an", "entity", "obj", "object"}


def _canonical_token_key(text):
    tokens = [t for t in normalize_room_id(str(text or "")).split("_")
              if t and t not in _GENERIC_ID_TOKENS]
    return "_".join(sorted(tokens))


def _entity_alias_map(cid):
    """{normalized alias/name/id (slug AND sorted-token key): canonical
    entity_id} for this chat's live entities, from world_entities plus the
    current scene -- so a book proposal anchored to an ALIAS of a vehicle
    ('tamsin_ferry_entity' for 'ferry_tamsin') resolves to the same
    canonical entity as the book that already tracks it."""
    amap = {}

    def register(names, own_id):
        keys = []
        for value in names:
            value = str(value or "").strip()
            if not value:
                continue
            for key in (normalize_room_id(value),
                        _canonical_token_key(value)):
                if key and key not in keys:
                    keys.append(key)
        # Union semantics: if ANY of this entity's keys already resolves
        # to an earlier entity, this row is (for dedup purposes) another
        # spelling of THAT entity -- its own id inherits that canonical
        # rather than becoming its own. Row order is the deterministic
        # tiebreak (world_entities first, insertion order).
        canonical = next((amap[k] for k in keys if k in amap), own_id)
        for key in keys:
            amap.setdefault(key, canonical)

    for row in q(
        "SELECT entity_id, name, payload FROM world_entities "
        "WHERE chat_id=? AND retired_turn_id IS NULL",
        (cid,),
    ):
        try:
            payload = json.loads(row["payload"] or "{}")
        except Exception:
            payload = {}
        register([row["entity_id"], row["name"],
                  *(payload.get("aliases") or [])], row["entity_id"])
    scene = wget(cid, "scene", {}) or {}
    for eid, ent in (scene.get("entities") or {}).items():
        if isinstance(ent, dict):
            register([eid, ent.get("name"), *(ent.get("aliases") or [])],
                     str(eid))
    return amap


def _canonical_anchor(anchor, alias_map):
    if not anchor:
        return None
    return alias_map.get(normalize_room_id(anchor)) \
        or alias_map.get(_canonical_token_key(anchor)) \
        or anchor


def _apply_mapping_book_ops(cid, lb, book_ops):
    """Deterministically validates and creates the child lorebooks
    mapping_commit proposed this turn (schemas.py's BookOp, prompts.py's
    BOOK CREATION rule) -- the model proposes a subject and a place in
    the tree, this function is what actually decides whether that's
    trustworthy enough to write, mirroring how every other model
    proposal in this codebase (state_diff, lore_ops themselves) is
    validated deterministically rather than applied on the model's say.
    Returns {temp_id: real_book_id} so lore_ops filed against a book
    that didn't have a database id a moment ago can still resolve it.
    """
    temp_map = {}
    if not book_ops:
        return temp_map

    existing = {
        row["id"]: row
        for row in q("SELECT * FROM lorebooks WHERE chat_id=?", (cid,))
    }
    created = 0
    alias_map = None  # built lazily -- most turns propose no books
    for op in book_ops:
        if not isinstance(op, dict) or op.get("op") != "create":
            continue
        if created >= 3:
            # Cap per turn -- a single beat introducing dozens of new
            # subjects at once is almost always a validation failure
            # upstream, not a genuine worldbuilding moment; the rest
            # fall back to the canon book via the caller's normal
            # target_book_id resolution, not lost.
            continue
        name = str(op.get("name") or "").strip()
        if not name:
            continue
        book_type = op.get("book_type") if op.get("book_type") in LOREBOOK_TYPES else "general"
        anchor = str(op.get("anchor_entity_id") or "").strip() or None
        scope_loc = str(op.get("scope_location_id") or "").strip() or None
        # Anchor-alias + normalized-name dedup: comparing raw anchor ids
        # let two DIFFERENT entity-id aliases of ONE vehicle
        # ('ferry_tamsin' vs 'tamsin_ferry_entity') mint two books for the
        # same ship. Resolve both sides to a canonical entity first, and
        # compare names by slug so punctuation/case drift can't fork a
        # book either. One vehicle -> one book.
        if alias_map is None:
            alias_map = _entity_alias_map(cid)
        canon_anchor = _canonical_anchor(anchor, alias_map)
        name_slug = normalize_room_id(name)

        dup = next((
            row for row in existing.values()
            if normalize_room_id(row["name"]) == name_slug
            or (canon_anchor and _canonical_anchor(
                row["anchor_entity_id"], alias_map) == canon_anchor)
            or (scope_loc and row["book_type"] == book_type and row["scope_location_id"] == scope_loc)
        ), None)
        if dup:
            if op.get("temp_id"):
                temp_map[op["temp_id"]] = dup["id"]
            continue

        raw_parent = op.get("parent_id")
        parent_id = temp_map.get(raw_parent) if isinstance(raw_parent, str) else raw_parent
        if not isinstance(parent_id, int) or parent_id not in existing:
            parent_id = lb  # keeps the tree rooted under canon -- never an unreachable orphan

        inheritance_mode = op.get("inheritance_mode") if op.get("inheritance_mode") in (
            "inherit", "isolated") else "inherit"
        new_id = qi(
            "INSERT INTO lorebooks(name,chat_id,book_type,summary,parent_id,"
            "inheritance_mode,scope_world_id,scope_location_id,anchor_entity_id,resource_uid) "
            "VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                name, cid, book_type, str(op.get("summary") or "")[:500], parent_id,
                inheritance_mode,
                str(op.get("scope_world_id") or "").strip() or None,
                # Store the CANONICAL entity id (not the model's alias
                # spelling) so sync_anchored_books and future dedup all
                # agree on which entity this book tracks.
                scope_loc, canon_anchor, new_uid("book"),
            ),
        )
        created += 1
        existing[new_id] = {
            "id": new_id, "name": name, "book_type": book_type,
            "anchor_entity_id": canon_anchor, "scope_location_id": scope_loc,
        }
        if op.get("temp_id"):
            temp_map[op["temp_id"]] = new_id
    return temp_map

def prepare_mapping_commit(ctx):
    """Resolve and embed mapping operations without mutating durable state.

    Mapping commit may require a long LLM round-trip and one or more remote
    embedding calls.  Preparing those decisions before the outer turn
    transaction prevents network latency from holding SQLite's write lock and
    lets commit_all apply every durable domain atomically.
    """
    chat = ctx.chat
    turn = ctx.turn
    cid = chat.id
    res = ctx.director_resolve or ctx.director_establish or {}
    diff = res.get("state_diff") or {}
    book_ids = chat_lorebook_ids(cid)
    # Narration is a rendering layer, not a source of objective truth.
    # `new_specifics` is an audit field for unsupported details the narrator
    # accidentally introduced; never launder those details into canon through
    # the privileged mapping agent.
    narrator_specificity_flags = (ctx.narrator or {}).get("new_specifics") or []
    if narrator_specificity_flags:
        ctx.add_warning(
            "Narrator-originated specifics were excluded from canon: "
            + "; ".join(map(str, narrator_specificity_flags[:8]))
        )
    specifics = []
    staged = (ctx.mapping_stage or {}).get("staged_lore") or []
    world_facts = diff.get("world_facts") or []
    introductions = diff.get("introductions") or []
    seed = f"tick:{cid}:{turn.idx}"

    if not (staged or world_facts or introductions):
        return {
            "skipped": True,
            "mout": {"skipped": "nothing new to commit"},
            "ops": [],
            "book_ops": [],
            "book_ids": book_ids,
            "seed": seed,
        }

    lore_ctx = search_lore(
        chat_lorebook_weights(cid),
        " ".join(map(str, specifics)) or res.get("summary", ""), k=10,
    )
    dormant = [
        character_name(json.loads(r["sheet"]))
        for r in q(
            "SELECT ch.sheet FROM chat_chars cc JOIN characters ch ON ch.id=cc.char_id "
            "LEFT JOIN chat_char_frames ccf "
            "  ON ccf.chat_id=cc.chat_id AND ccf.char_id=cc.char_id AND ccf.frame_id IS ? "
            "WHERE cc.chat_id=? AND COALESCE(ccf.status, cc.status)='dormant'",
            (turn.frame_id, cid),
        )
    ]
    raw_shadow = wget(cid, "shadow_profile", "") or ""
    raw_intents = wget(cid, "standing_intentions", []) or []
    payload = {
        "proposed_specifics": specifics,
        "narrator_specificity_audit": narrator_specificity_flags,
        "staged_lore_to_confirm": staged,
        "world_facts": world_facts,
        "existing_lore": lore_ctx,
        "lorebook_manifest": lorebook_manifest(cid),
        "resolved_summary": res.get("summary") or (res.get("resolved_event") or "")[:400],
        "player_public_behavior": {
            "speech": (ctx.director_interpret or {}).get("speech"),
            "visible_action": ((ctx.director_interpret or {}).get("action") or {}).get("attempt"),
        },
        "current_shadow_profile": raw_shadow[:1200],
        "scene_changed": bool(ctx.director_establish),
        "dormant_actors": dormant,
        "standing_intentions": raw_intents[:12],
        "beat_introductions": diff.get("introductions") or [],
        "beat_dialogue_log": res.get("dialogue_log") or [],
        "beat_resolved_event": res.get("resolved_event") or "",
        "tick_seed": seed,
    }
    try:
        from llm_quality import complete_validated_json

        mout = complete_validated_json(
            role="mapping",
            step_key="mapping_commit",
            system=get_prompt("mapping_commit"),
            payload=payload,
            temperature=0.0,
            repair_attempts=1,
        )
    except Exception as e:
        ctx.add_warning(f"mapping_commit failed: {e}")
        mout = {
            "validated": [],
            "lore_ops": [],
            "coherence_notes": [f"mapping commit failed: {e}"],
        }

    validated_list = mout.get("validated") if isinstance(mout.get("validated"), list) else []
    ok_facts = [v for v in validated_list if isinstance(v, dict) and v.get("ok")]
    ops = mout.get("lore_ops") if isinstance(mout.get("lore_ops"), list) else []
    ops = [dict(o) for o in ops if isinstance(o, dict) and o.get("content")]
    book_ops = mout.get("book_ops") if isinstance(mout.get("book_ops"), list) else []
    book_ops = [dict(o) for o in book_ops if isinstance(o, dict)]

    if not ops:
        ops = _generate_fallback_ops(
            ok_facts, staged, world_facts, existing_lore=lore_ctx,
        )
    for o in ops:
        if "keys" in o:
            o["keys"] = _keys_str(o["keys"])

    # Lore embeddings are independent of final routing/book IDs. Compute them
    # in one batch now rather than one remote call per operation while the
    # database transaction is open.
    if ops:
        vectors = embed_texts([
            (str(o.get("keys") or "") + " " + str(o.get("content") or "")).strip()
            for o in ops
        ])
        if len(vectors) != len(ops):
            raise RuntimeError("Lore embedding provider returned an unexpected vector count")
        for op, vector in zip(ops, vectors):
            op["_embedding"] = vector

    return {
        "skipped": False,
        "mout": mout,
        "ops": ops,
        "book_ops": book_ops,
        "book_ids": book_ids,
        "seed": seed,
    }


def commit_mapping(ctx, nonce, *, prepared=None):
    chat = ctx.chat
    turn = ctx.turn
    cid = chat.id
    prepared = prepared or prepare_mapping_commit(ctx)
    mout = prepared["mout"]
    book_ids = prepared["book_ids"]
    seed = prepared["seed"]

    if prepared.get("skipped"):
        wset(cid, "lore_cache", _lore_for(ctx)[:12])
        mstep = ctx.mapping_stage or ctx.mapping_quick or {}
        if not mstep.get("cached") and isinstance(mstep.get("relevant_books"), list):
            wset(cid, "active_books", mstep["relevant_books"])
        return {
            "mout": mout,
            "applied": {"created": 0, "updated": 0},
            "book_ids": book_ids,
            "seed": seed,
        }

    ops = prepared["ops"]
    book_ops = prepared["book_ops"]
    applied = {"created": 0, "updated": 0}
    lb = chat.lorebook_id
    if (ops or book_ops) and not lb:
        lb = qi(
            "INSERT INTO lorebooks(name,chat_id,book_type,summary) VALUES(?,?,?,?)",
            (
                f"{chat.name} — canon", cid, "general",
                "Chat canon: facts, events and specifics established during this chat.",
            ),
        )
        qi("UPDATE chats SET lorebook_id=? WHERE id=?", (lb, cid))

    temp_book_map = _apply_mapping_book_ops(cid, lb, book_ops)
    valid_books = set(chat_lorebook_ids(cid))
    with transaction() as c:
        for o in ops:
            cat = o.get("category") if o.get("category") in LORE_CATEGORIES else "other"
            kloc = (
                json.dumps(o.get("knowledge_locations") or [])
                if o.get("knowledge_locations") else None
            )
            raw_book_id = o.get("book_id")
            if isinstance(raw_book_id, str):
                raw_book_id = temp_book_map.get(raw_book_id) or (
                    int(raw_book_id) if raw_book_id.isdigit() else None
                )
            target_book_id = raw_book_id or lb
            if target_book_id not in valid_books:
                target_book_id = lb

            if o.get("op") == "update" and o.get("id"):
                row = q("SELECT * FROM lore_entries WHERE id=?", (o["id"],), one=True)
                if row and row["lorebook_id"] in valid_books and not row["canon_locked"]:
                    update_lore(
                        o["id"], o.get("keys", row["keys"]), o["content"], cat,
                        title=o.get("title"), knowledge_tag=o.get("knowledge_tag"),
                        knowledge_range=o.get("knowledge_range"),
                        knowledge_locations=kloc,
                        embedding=o.get("_embedding"),
                    )
                    applied["updated"] += 1
                    continue
            add_lore(
                target_book_id, o.get("keys", ""), o["content"],
                turn_added=turn.idx, category=cat, title=o.get("title"),
                knowledge_tag=o.get("knowledge_tag"),
                knowledge_range=o.get("knowledge_range"),
                knowledge_locations=kloc,
                embedding=o.get("_embedding"),
            )
            applied["created"] += 1
        if lb:
            c.execute(
                "UPDATE lore_entries SET canon_locked=1 "
                "WHERE lorebook_id=? AND turn_added IS NOT NULL AND turn_added<=?",
                (lb, turn.idx - 20),
            )

    wset(cid, "lore_cache", _lore_for(ctx)[:12])
    mstep = ctx.mapping_stage or ctx.mapping_quick or {}
    if not mstep.get("cached") and isinstance(mstep.get("relevant_books"), list):
        wset(cid, "active_books", mstep["relevant_books"])
    if mout.get("shadow_profile"):
        sp = mout["shadow_profile"]
        if isinstance(sp, str) and len(sp) > 2000:
            sp = sp[:2000]
        wset(cid, "shadow_profile", sp)
    if mout.get("standing_intentions"):
        si = mout["standing_intentions"]
        if isinstance(si, list) and len(si) > 20:
            si = si[-20:]
        wset(cid, "standing_intentions", si)
    if mout.get("offscreen_events"):
        log = wget(cid, "offscreen_log", [])
        log.append({"turn": turn.idx, "seed": seed, "events": mout["offscreen_events"]})
        wset(cid, "offscreen_log", log)

    known = wget(cid, "known", {})
    roster = _known_name_roster(chat, ctx.cast)
    name_to_id = {character_name(json.loads(r["sheet"])): r["id"] for r in ctx.cast}
    for vi in (mout.get("validated_introductions") or []):
        if not isinstance(vi, dict) or not vi.get("ok"):
            continue
        who = _resolve_roster_name(vi.get("who"), roster)
        learns = _resolve_roster_name(
            vi.get("corrected_learns") or vi.get("learns"), roster,
        )
        if not (who and learns):
            continue
        learns_id = name_to_id.get(learns)
        if learns_id is not None and not is_recognized_in_frame(learns_id, turn.frame_id):
            continue
        known.setdefault(who, [])
        if learns not in known[who]:
            known[who].append(learns)
    wset(cid, "known", known)
    return {"mout": mout, "applied": applied, "book_ids": book_ids, "seed": seed}

# ---- Obligation ledger ----
#
# The world-KV `pending_obligations` ledger tracks open narrative debts --
# demands, promises, announced actions, unanswered questions -- registered by
# director_resolve's `obligations` ops and applied here deterministically
# (mirroring the standing_intentions machinery). Each entry:
# {id, who, what, kind, opened_turn}. director_resolve's payload surfaces
# pending_obligation_view, whose must_discharge_this_beat flag plus the
# prompt's hard rule forbid re-deferring an obligation past its window.

OBLIGATION_OVERDUE_AGE = 2   # beats after which an open obligation must discharge
OBLIGATION_CAP = 12

def pending_obligation_view(chat_id, turn_idx):
    """Payload-ready view of the obligation ledger: each entry with its
    deterministically computed age and must-discharge flag."""
    view = []
    for entry in (wget(chat_id, "pending_obligations", []) or [])[:OBLIGATION_CAP]:
        if not isinstance(entry, dict):
            continue
        try:
            age = max(0, int(turn_idx) - int(entry.get("opened_turn", turn_idx)))
        except (TypeError, ValueError):
            age = 0
        view.append({
            "id": entry.get("id"),
            "who": entry.get("who"),
            "what": entry.get("what"),
            "kind": entry.get("kind", "demand"),
            "age_beats": age,
            "must_discharge_this_beat": age >= OBLIGATION_OVERDUE_AGE,
        })
    return view

def _find_obligation(ledger, op):
    """Index of the ledger entry an op targets: exact id first, then a
    fuzzy same-debtor/overlapping-text fallback (models routinely echo the
    text but not the id)."""
    oid = str(op.get("id") or "").strip()
    if oid:
        for i, entry in enumerate(ledger):
            if str(entry.get("id") or "") == oid:
                return i
    who = _normalized_fact(op.get("who"))
    what = _normalized_fact(op.get("what"))
    if not what:
        return None
    for i, entry in enumerate(ledger):
        entry_who = _normalized_fact(entry.get("who"))
        entry_what = _normalized_fact(entry.get("what"))
        if who and entry_who and who != entry_who:
            continue
        if entry_what and (what in entry_what or entry_what in what):
            return i
    return None

def commit_obligations(ctx, nonce):
    """Apply director_resolve's obligation ops to the pending_obligations
    ledger. Deterministic: open appends (deduped -- re-demanding an open
    debt is not a second debt), discharge/refuse removes. The commit-side
    reminder: any entry still open past OBLIGATION_OVERDUE_AGE after this
    beat's ops was re-deferred against the prompt's hard rule -- warn, and
    leave it flagged for the next beat's payload."""
    cid = ctx.chat.id
    turn = ctx.turn
    res = ctx.director_resolve or {}
    ops = res.get("obligations") if isinstance(res.get("obligations"), list) else []
    ledger = [
        dict(entry)
        for entry in (wget(cid, "pending_obligations", []) or [])
        if isinstance(entry, dict) and entry.get("what")
    ]

    opened = discharged = 0
    for op in ops:
        if not isinstance(op, dict):
            continue
        op_kind = str(op.get("op") or "").strip().lower()
        if op_kind == "open":
            what = str(op.get("what") or "").strip()
            if not what or _find_obligation(ledger, op) is not None:
                continue
            ledger.append({
                "id": f"obl:{turn.idx}:{opened}",
                "who": str(op.get("who") or "").strip(),
                "what": what,
                "kind": str(op.get("kind") or "demand").strip() or "demand",
                "opened_turn": turn.idx,
            })
            opened += 1
        elif op_kind in ("discharge", "refuse"):
            idx = _find_obligation(ledger, op)
            if idx is None:
                ctx.add_warning(
                    f"obligation {op_kind} matched no open ledger entry: "
                    f"{(op.get('id') or op.get('what') or '')!r}"
                )
                continue
            ledger.pop(idx)
            discharged += 1

    overdue = []
    for entry in ledger:
        try:
            age = turn.idx - int(entry.get("opened_turn", turn.idx))
        except (TypeError, ValueError):
            age = 0
        if age >= OBLIGATION_OVERDUE_AGE:
            overdue.append(entry)
            ctx.add_warning(
                f"Obligation re-deferred past its window: {entry.get('who')!r} "
                f"still owes {entry.get('what')!r} (opened turn "
                f"{entry.get('opened_turn')}, age {age} beats). It MUST be "
                "discharged or explicitly refused on-page next beat."
            )

    if len(ledger) > OBLIGATION_CAP:
        ledger = ledger[-OBLIGATION_CAP:]
    wset(cid, "pending_obligations", ledger)
    return {"opened": opened, "discharged": discharged,
            "open": len(ledger), "overdue": len(overdue)}

# ---- Memory commit ----

# How many of a character's most recent physical tells (manifest cues) are
# kept on cstate as the anti-repetition ledger fed back into the character
# payload (see agents/character.py's TELL VARIETY block).
RECENT_TELLS_CAP = 6

def _durable_dialogue_category(text):
    lowered = (text or "").lower()
    if any(w in lowered for w in ("promise", "i swear", "i vow", "you have my word",
                                   "i'll return", "i will return")):
        return "promise"
    if any(w in lowered for w in ("my name is", "call me", "i confess", "the truth is",
                                   "i killed", "i betrayed", "i love you", "i hate you",
                                   "i'll kill", "i will kill")):
        return "dialogue"
    return None

def _quote_body(quote):
    return (quote or "").strip().strip('"' + "'" + "\u201c\u201d\u2018\u2019")

def _room_of(scene, name):
    positions = scene.get("positions") or {}
    if name in positions:
        return positions[name]
    lname = (name or "").lower().strip()
    for k, v in positions.items():
        if k.lower().strip() == lname:
            return v
    norm = re.sub(r"[^a-z0-9]", "", lname)
    if norm:
        for k, v in positions.items():
            if re.sub(r"[^a-z0-9]", "", k.lower().strip()) == norm:
                return v
    return None

def _is_player(speaker, chat):
    from agents import is_player_speaker
    return is_player_speaker(speaker, chat)

def _salience_of(text):
    s = 0.45 + min(len(text or ""), 400) / 1600.0
    for w in ("attack", "blood", "secret", "betray", "kiss", "dead",
              "weapon", "threat", "love", "steal", "scream", "knife",
              "confess", "liar", "promise"):
        if w in (text or "").lower():
            s += 0.08
    return round(min(s, 0.95), 3)

def prepare_memory_commit(ctx, *, scene=None):
    """Build and embed all per-character memory mutations without writes."""
    chat = ctx.chat
    turn = ctx.turn
    cid = chat.id
    res = ctx.director_resolve or ctx.director_establish or {}
    # Build a fresh list -- never mutate res["dialogue_log"], since the
    # director_resolve step/variant was already persisted before
    # background_react ran (see agents/perception.py's merge comment). The
    # deterministic backstop line is merged only for rendering there; fold
    # it into the persisted event record here too, so hearers mint dialogue
    # memories of it and it reaches _promotion_evidence.
    dlog = list(res.get("dialogue_log") or [])
    for _r in _background_fired_reactions(ctx.get("background_react")):
        dlog.append({**_r["dialogue_log_entry"], "source": "background_react"})
    views = (
        (ctx.perception_outcome or {}).get("views")
        or (ctx.perception_establish or {}).get("views")
        or {}
    )
    est = ctx.director_establish
    sc = scene if scene is not None else (wget(cid, "scene", {}) or {})
    pending_memories = []
    state_updates = []
    relationship_ops = []

    for char_row in ctx.cast:
        ccid = char_row["id"]
        sh = json.loads(char_row["sheet"])
        st = json.loads(char_row["cstate"] or "{}")
        v = views.get(str(ccid))
        cname = character_name(sh)
        char_room = _room_of(sc, cname)
        room_data = (sc.get("rooms") or {}).get(char_room, {})
        room_name = room_data.get("name") or char_room or ""
        own_result = ctx.character_results.get(ccid) or {}
        own_result = _normalize_character_output(own_result)
        active_state = own_result.get("active_state") or {}
        mood = str(active_state.get("mood") or "")
        # The character's blended surface affect this beat carries the numeric
        # valence/arousal that go with the `mood` label; without this the
        # emotional_context text was stored but valence/arousal stayed at their
        # 0.0 default on every memory (the memory editor showed them as always
        # zero). Mirror the label onto the numeric axes for this beat's memories.
        _surface = (active_state.get("affect") or {}).get("surface") or {}
        try:
            _mem_valence = float(_surface.get("valence") or 0.0)
            _mem_arousal = float(_surface.get("arousal") or 0.0)
        except (TypeError, ValueError):
            _mem_valence, _mem_arousal = 0.0, 0.0
        if est and not v:
            room_label = char_room or "the scene"
            room_data2 = (sc.get("rooms") or {}).get(room_label, {})
            room_name2 = room_data2.get("name") or room_label
            room_desc = room_data2.get("desc") or room_data2.get("notes") or ""
            v = f"The scene opens. You are in {room_name2}." + (
                f" {room_desc}" if room_desc else ""
            )
        if v:
            for d in dlog:
                spk = d.get("speaker", "")
                if _is_player(spk, chat):
                    spk = "the player"
                if spk == cname:
                    continue
                quote = d.get("exact_quote", "")
                qbody = _quote_body(quote)
                if qbody and (quote in v or qbody in v):
                    category = _durable_dialogue_category(qbody)
                    if category:
                        tgt = d.get("intended_target")
                        pending_memories.append({
                            "chat_id": cid, "char_id": ccid, "turn_id": turn.id,
                            "turn_idx": turn.idx, "kind": "dialogue", "category": category,
                            "provenance": "heard",
                            "salience": 0.9 if category == "promise" else 0.82,
                            "content": f"{spk} said {quote}" + (f" to {tgt}" if tgt else ""),
                            "gist": f"{spk}: {qbody}", "key_phrases": [qbody, spk],
                            "entities": [spk], "location": room_name,
                            "emotional_context": mood,
                            "valence": _mem_valence, "arousal": _mem_arousal,
                            "event_key": _stable_event_key(
                                turn.id, ccid, "dialogue", d.get("speaker"),
                                qbody, d.get("intended_target"),
                            ),
                        })
            episode_content = v
            pending_memories.append({
                "chat_id": cid, "char_id": ccid, "turn_id": turn.id,
                "turn_idx": turn.idx, "kind": "episodic", "category": "episode",
                "provenance": "witnessed", "salience": _salience_of(episode_content),
                "content": episode_content, "location": room_name,
                "emotional_context": mood,
                "valence": _mem_valence, "arousal": _mem_arousal,
                "event_key": _stable_event_key(turn.id, ccid, "episode"),
            })
        if own_result:
            seq = own_result.get("sequence") or []
            own_salience = float(own_result.get("salience", 0.0))
            should_store_own_acts = bool(seq) and (
                own_salience >= 0.7
                or any(event.get("type") == "speech" for event in seq)
            )
            if should_store_own_acts:
                desc = "; ".join(
                    f"said {e.get('text')!r}" if e.get("type") == "speech"
                    else f"attempted {e.get('attempt')!r}"
                    for e in seq
                )
                pending_memories.append({
                    "chat_id": cid, "char_id": ccid, "turn_id": turn.id,
                    "turn_idx": turn.idx, "kind": "episodic", "category": "self",
                    "provenance": "remembered", "salience": max(0.5, own_salience),
                    "content": f"I chose to {desc}",
                    "gist": f"I chose to {desc}"[:240],
                    "location": room_name, "emotional_context": mood,
                    "valence": _mem_valence, "arousal": _mem_arousal,
                    "event_key": _stable_event_key(turn.id, ccid, "own_acts"),
                })
            for update in own_result.get("mind_model_updates") or []:
                confidence = _clamp(update.get("confidence", 0.5))
                evidence = "; ".join(
                    str(item.get("fact") or "")
                    for item in update.get("evidence") or []
                    if isinstance(item, dict)
                )
                pending_memories.append({
                    "chat_id": cid, "char_id": ccid, "turn_id": turn.id,
                    "turn_idx": turn.idx, "kind": "inference", "category": "inference",
                    "provenance": "inferred", "salience": 0.45 + 0.3 * confidence,
                    "confidence": confidence,
                    "content": (
                        f"About {update.get('about_entity')}: "
                        f"{update.get('claim')}. Evidence: {evidence}"
                    ),
                    "gist": str(update.get("claim") or "")[:240],
                    "entities": [str(update.get("about_entity") or "")],
                    "location": room_name, "emotional_context": mood,
                    "event_key": _stable_event_key(
                        turn.id, ccid, "mind_model", update.get("about_entity"),
                        update.get("kind"), update.get("claim"),
                    ),
                })
            # --- Interior depth: deterministic floors over the model's proposed
            # active_state (goals + blended affect). All fields are optional;
            # absent ones degrade to the legacy {mood,goal}. affect.py is pure;
            # this is the single write point where the floors apply.
            if own_result.get("active_state") is not None:
                asv = own_result.get("active_state")
                if not isinstance(asv, dict):
                    asv = {"mood": str(asv), "goal": ""}
                prev_as = st.get("active_state") if isinstance(st.get("active_state"), dict) else {}
                interior = st.get("interior") if isinstance(st.get("interior"), dict) else {}
                intentions = interior.get("intentions") or []
                drive = (character_psychology(sh) or {}).get("drive") or {}

                # this beat's evidence pool: resolved event + spoken lines, for
                # gating intention satisfy/abandon (light floor: cited + present).
                _ev_text = (res.get("resolved_event") or "") + " " + " ".join(
                    str(d.get("exact_quote") or "") for d in dlog)

                def _evidence_ok(op, _t=_ev_text):
                    ev = op.get("evidence") or []
                    if not ev:
                        return False
                    return any(str(e) and str(e) in _t for e in ev) or bool(op.get("why"))

                intentions, _iwarn = affect.apply_intent_ops(
                    intentions, own_result.get("intent_ops") or [], turn.idx, _evidence_ok)
                for w in _iwarn:
                    ctx.add_warning(f"{cname}: intention -- {w}")
                valid_ids = {str(i.get("id")) for i in intentions if isinstance(i, dict)}

                def _priority(serves, _ids=valid_ids, _intents=intentions):
                    # Models emit serves as "intention:<id-or-text>"; resolve
                    # it to the bare id so a goal-serving impact scores at
                    # intention priority, not the situational default.
                    serves = affect.normalize_serves(serves, _intents)
                    if serves == "drive":
                        return 1.0
                    return 0.8 if str(serves) in _ids else 0.4

                wants, enacted, suppressed = affect.normalize_wants(
                    asv.get("wants") or [], valid_ids)

                appraisal_out = affect.appraise(
                    ((own_result.get("appraisal") or {}).get("goal_impacts")) or [], _priority)
                prev_affect = prev_as.get("affect") if isinstance(prev_as, dict) else None
                baseline = ((prev_affect or {}).get("baseline")
                            or character_initial_active_state(sh)["affect"]["baseline"])
                turns_since = max(1, turn.idx - int(prev_as.get("affect_turn") or (turn.idx - 1)))
                new_affect = affect.resolve_affect(
                    prev_affect, appraisal_out, baseline, turns_since,
                    proposed=asv.get("affect") or asv.get("mood"))

                # Leak tripwire: this character's OWN speech must not state a
                # suppressed want / the undercurrent / an unenacted intention.
                own_speech = [str(d.get("exact_quote") or "") for d in dlog
                              if d.get("speaker") == cname]
                for w in affect.leak_scan(own_speech, wants,
                                          new_affect.get("undercurrent"), intentions):
                    ctx.add_warning(f"{cname}: interior leak -- {w}")

                surface = new_affect.get("surface") or {}
                enacted_goal = (wants[enacted]["want"]
                                if (wants and enacted is not None
                                    and 0 <= enacted < len(wants)) else asv.get("goal") or "")
                st["active_state"] = {
                    "mood": surface.get("label") or str(asv.get("mood") or ""),
                    "goal": str(enacted_goal or ""),
                    # canonical valence/arousal, projected to the flat legacy keys.
                    "valence": float(surface.get("valence") or 0.0),
                    "arousal": float(surface.get("arousal") or 0.0),
                    "affect": new_affect,
                    "wants": wants,
                    "enacted_want": enacted,
                    "suppressed_want": suppressed,
                    "affect_turn": turn.idx,
                }
                # --- Drive rupture (Tier 1): a deterministic strain ledger and
                # two-key gate that can, rarely and earned, crack the core drive.
                def _serves_of(i):
                    return (str(wants[i].get("serves") or "")
                            if (isinstance(wants, list) and isinstance(i, int)
                                and 0 <= i < len(wants)) else "")
                strain = float(interior.get("drive_strain") or 0.0)
                strain_log = list(interior.get("strain_log") or [])
                _strain_turns = max(1, turn.idx - int(interior.get("strain_turn") or (turn.idx - 1)))
                strain, _slog = affect.update_drive_strain(
                    strain, strain_log, appraisal_out,
                    _serves_of(enacted), _serves_of(suppressed), _strain_turns)
                if _slog:
                    _slog["turn"] = turn.idx
                    strain_log = (strain_log + [_slog])[-12:]
                cur_drive = effective_drive(character_psychology(sh), interior)
                former = list(interior.get("former_drives") or [])
                last_shift = interior.get("last_shift_turn")
                override = interior.get("drive_override") if isinstance(interior.get("drive_override"), dict) else None
                rupture = interior.get("drive_rupture") if isinstance(interior.get("drive_rupture"), dict) else None
                window_open = bool(rupture and turn.idx <= int(rupture.get("window_expires") or -1))
                if not window_open:
                    _det = affect.detect_drive_rupture(strain, appraisal_out, turn.idx, last_shift)
                    if _det:
                        rupture = {"turn": turn.idx, "opened_turn": turn.idx,
                                   "why": _det.get("why"),
                                   "direction": _det.get("direction"), "window_expires": turn.idx + 3}
                        ctx.add_warning(f"{cname}: DRIVE RUPTURE window opened -- {_det.get('why')}")
                elif own_result.get("drive_shift"):
                    _norm, _kind, _vw = affect.validate_drive_shift(
                        own_result.get("drive_shift"), cur_drive, former, rupture)
                    for w in _vw:
                        ctx.add_warning(f"{cname}: drive_shift -- {w}")
                    if _norm and _kind == "break":
                        _rw = str(rupture.get("why") or "")
                        former = (former + [affect.former_drive_entry(cur_drive, turn.idx, _rw)])[-5:]
                        override = {**_norm, "since_turn": turn.idx, "by_event": _rw}
                        strain, last_shift, rupture = 0.0, turn.idx, None
                        ctx.add_warning(f"{cname}: DRIVE SHIFTED -> {_norm.get('essence')}")
                        pending_memories.append({
                            "chat_id": cid, "char_id": ccid, "turn_id": turn.id, "turn_idx": turn.idx,
                            "kind": "episode", "category": "self", "provenance": "remembered", "salience": 1.0,
                            "content": (f"Something in me broke when {_rw}. What I lived for -- "
                                        f"{cur_drive.get('essence')} -- no longer holds me. Now I live for: "
                                        f"{_norm.get('essence')}."),
                            "gist": f"drive shift -> {_norm.get('essence')}"[:240],
                            "entities": [cname], "location": room_name,
                            "emotional_context": surface.get("label") or "",
                            "event_key": _stable_event_key(turn.id, ccid, "drive_shift", cname,
                                                           _norm.get("essence"), ""),
                        })
                    elif _norm and _kind == "bend":
                        override = {**_norm, "since_turn": turn.idx, "by_event": str(rupture.get("why") or "")}
                        strain, last_shift, rupture = strain * 0.5, (turn.idx - 30), None
                if rupture and turn.idx > int(rupture.get("window_expires") or -1):
                    _opened_turn = int(rupture.get("opened_turn") or rupture.get("turn") or turn.idx)
                    _turns_open = turn.idx - _opened_turn
                    if strain >= affect.RUPTURE_STRAIN_MIN \
                            and _turns_open < affect.RUPTURE_MAX_OPEN:
                        # Strain still at rupture level and the hard cap not yet
                        # reached: the crisis is unresolved, so the window RE-OPENS
                        # (extends) instead of quietly closing -- denial is a phase,
                        # not an exit. (agents/character.py escalates the prompt to a
                        # FORCED resolution once the window has been open
                        # RUPTURE_FORCE_AFTER turns, so this extension is not the
                        # unpressured "you MAY" it used to be.)
                        rupture = {**rupture, "window_expires": turn.idx + 3}
                        ctx.add_warning(
                            f"{cname}: drive-rupture window extended -- "
                            f"strain {strain:.2f} still at rupture level")
                    else:
                        # Force-close: either strain finally decayed below the floor,
                        # OR the window has been open RUPTURE_MAX_OPEN turns with no
                        # shift. A model that will not shift within the forced window
                        # has, in effect, reaffirmed the drive under maximal pressure
                        # -- so resolve the crisis (pay strain down below the floor)
                        # rather than leaving the character in a permanent, never-
                        # resolving limbo (the 23-turn Vorne case).
                        if strain >= affect.RUPTURE_STRAIN_MIN:
                            strain = affect.RUPTURE_STRAIN_MIN * 0.75
                            ctx.add_warning(
                                f"{cname}: drive-rupture force-closed after "
                                f"{_turns_open} turns unresolved -- drive reaffirmed "
                                f"under pressure, strain paid down")
                        else:
                            strain = strain * 0.5   # weathered the crisis, no shift
                        rupture = None
                _interior_out = {
                    "intentions": intentions,
                    "drive_strain": round(float(strain), 4),
                    "strain_log": strain_log,
                    "former_drives": former,
                    "last_shift_turn": last_shift,
                    "strain_turn": turn.idx,
                }
                if rupture is not None:
                    _interior_out["drive_rupture"] = rupture
                if override is not None:
                    _interior_out["drive_override"] = override
                st["interior"] = _interior_out
            # --- Recent-tell ledger: the last few physical cues this
            # character has shown, kept on cstate and fed back into the
            # next character payload (self.recent_tells) so the model
            # stops reaching for the same gesture every beat.
            _cues = [str(t.get("cue") or "").strip()
                     for t in ((own_result.get("manifest") or {}).get("tells") or [])
                     if isinstance(t, dict)]
            _cues = [c for c in _cues if c]
            if _cues:
                _prev_cues = [str(c) for c in (st.get("recent_tells") or [])
                              if str(c).strip()]
                st["recent_tells"] = (_prev_cues + _cues)[-RECENT_TELLS_CAP:]
            stance = st.get("stance") or sh.get("stance") or {"axes": {}}
            for u in own_result.get("stance_updates") or []:
                ax = u.get("axis")
                if not ax:
                    continue
                try:
                    stance.setdefault("axes", {})
                    stance["axes"][ax] = round(
                        float(stance["axes"].get(ax, 0)) + float(u.get("delta", 0)),
                        3,
                    )
                    stance.setdefault("log", []).append({
                        "turn": turn.idx, "axis": ax,
                        "delta": u.get("delta"), "trigger": u.get("trigger"),
                    })
                except Exception:
                    pass
            st["stance"] = stance
            st = apply_mind_model_updates(
                st, own_result.get("mind_model_updates") or [], turn.idx,
            )
            explicit_updates = own_result.get("relationship_updates") or []
            if explicit_updates:
                relationship_ops.append(("explicit", ccid, explicit_updates))
            elif own_result.get("inference_updates"):
                relationship_ops.append(
                    ("inference", ccid, own_result.get("inference_updates") or [])
                )
        state_updates.append((cid, ccid, json.dumps(st)))

    event_content = json.dumps({
        "turn": turn.idx,
        "summary": res.get("summary") or "",
        "event": res.get("resolved_event") or "",
        "dialogue_log": dlog,
    })
    return {
        "memory_batch": prepare_memories_batch(pending_memories),
        "state_updates": state_updates,
        "relationship_ops": relationship_ops,
        "event_content": event_content,
    }


def _consolidate_committed_memories(ctx):
    """Update derived autobiographical summaries after the atomic commit.

    Summaries are reconstructible caches, not primary turn facts.  Keeping
    their LLM calls outside the transaction avoids deadlocks and ensures a
    consolidation failure can never roll back an otherwise valid turn.
    """
    cid = ctx.chat.id
    turn = ctx.turn
    notes = []

    def _consolidate_one(char_row):
        try:
            result = maybe_consolidate_character_memory(
                cid, char_row["id"], turn.idx, frame_id=turn.frame_id,
            )
            if result:
                return (
                    f"{character_name(json.loads(char_row['sheet']))}: "
                    "autobiographical summary updated"
                )
        except Exception as exc:
            ctx.add_warning(
                f"Memory consolidation failed for character {char_row['id']}: {exc}"
            )
        return None

    if ctx.cast:
        with ThreadPoolExecutor(max_workers=len(ctx.cast)) as pool:
            for note in pool.map(_consolidate_one, ctx.cast):
                if note:
                    notes.append(note)
    return notes


def commit_memories(ctx, nonce, *, prepared=None, consolidate=True):
    prepared = prepared or prepare_memory_commit(ctx)
    turn = ctx.turn
    cid = ctx.chat.id

    with transaction():
        delete_turn_memories(turn.id)
        memory_ids = add_memories_batch(
            prepared_batch=prepared["memory_batch"],
        )
        for kind, char_id, updates in prepared["relationship_ops"]:
            if kind == "explicit":
                apply_relationship_updates(cid, char_id, turn.idx, updates)
            else:
                update_relationships_from_inference(
                    cid, char_id, turn.idx, updates,
                )
        for chat_id, char_id, state_json in prepared["state_updates"]:
            set_char_state(
                chat_id, char_id, state_json, frame_id=turn.frame_id,
            )
        qi(
            """INSERT INTO events(chat_id,turn_id,content) VALUES(?,?,?)
            ON CONFLICT(chat_id,turn_id) WHERE turn_id IS NOT NULL
            DO UPDATE SET content=excluded.content""",
            (cid, turn.id, prepared["event_content"]),
        )

    committed = [f"memory:{mid}" for mid in memory_ids]
    if consolidate:
        committed.extend(_consolidate_committed_memories(ctx))
    return {"committed": committed}

# ---- Narration-person commit ----

_NARRATION_PERSONS = ("first", "second", "third")

def commit_narration_person(ctx, nonce):
    """Apply the narration-person detections the narrator stages recorded on
    their returned step content (`narration_person_writes`) but deliberately
    did not persist themselves -- commit.py is the sole persistence boundary,
    and the narrator previously did a durable wset mid-pipeline, before the
    turn was validated/committed (so an aborted or rolled-back turn had
    already flipped the campaign's narration voice). Deterministically
    validated: only `narration_person*` keys with a known person value are
    written, since step content is inspectable and manually editable.
    """
    cid = ctx.chat.id
    applied = 0
    sources = []
    if isinstance(ctx.narrator, dict):
        sources.append(ctx.narrator)
    extra = ctx.get("narrator_extra") or {}
    if isinstance(extra, dict):
        sources.extend(v for v in extra.values() if isinstance(v, dict))
    with transaction():
        for out in sources:
            writes = out.get("narration_person_writes")
            if not isinstance(writes, dict):
                continue
            for key, value in writes.items():
                if (isinstance(key, str) and key.startswith("narration_person")
                        and value in _NARRATION_PERSONS):
                    wset(cid, key, value)
                    applied += 1
    return {"applied": applied}

# ---- Top-level atomic commit ----

def commit_all(ctx, nonce):
    """Commit one turn exactly once and atomically.

    Expensive or failure-prone preparation (LLM validation and embeddings)
    happens before SQLite's write transaction.  Every durable mutation then
    runs under one outer transaction; a failure in any domain rolls back all
    earlier domains from the same turn.
    """
    lock = _commit_lock(ctx.turn.id)
    with lock:
        return _commit_all_locked(ctx, nonce)


def _prepare_turn_commit(ctx):
    """Prepare slow commit inputs without holding SQLite's write lock."""
    try:
        scene = prepare_scene_commit(ctx)
        mapping = prepare_mapping_commit(ctx)
        memories = prepare_memory_commit(ctx, scene=scene["scene"])
        return {"scene": scene, "mapping": mapping, "memories": memories}
    except Exception as exc:
        ctx.add_warning(f"commit preparation failed: {exc}")
        raise RuntimeError(f"Commit preparation failed: {exc}") from exc


def _commit_domain(ctx, results, name, operation):
    """Run one durable domain and preserve its name on rollback errors."""
    try:
        results[name] = operation()
    except Exception as exc:
        ctx.add_warning(f"commit_{name} failed; turn rolled back: {exc}")
        raise RuntimeError(f"{name}: {exc}") from exc


def _commit_all_locked(ctx, nonce):
    prepared = _prepare_turn_commit(ctx)
    results = {}

    try:
        with transaction():
            # Transit sweep first: it mutates the prepared scene (timed
            # arrivals, engine notices) that the scene domain then persists.
            _commit_domain(
                ctx, results, "transit",
                lambda: commit_transit_sweep(
                    ctx, nonce, prepared=prepared["scene"]),
            )
            _commit_domain(
                ctx, results, "scene",
                lambda: commit_scene(ctx, nonce, prepared=prepared["scene"]),
            )
            _commit_domain(
                ctx, results, "entities",
                lambda: commit_world_entities(
                    ctx, nonce, prepared=prepared["scene"]),
            )
            _commit_domain(
                ctx, results, "cast",
                lambda: commit_cast_changes(ctx, nonce),
            )
            # These checks intentionally run after scene/entity/cast writes so
            # they inspect this turn's projected world, while still remaining
            # inside the same rollback boundary.
            _commit_domain(
                ctx, results, "paradox",
                lambda: check_and_apply_paradox(ctx, nonce),
            )
            _commit_domain(
                ctx, results, "spatial",
                lambda: detect_and_reconcile_spatial(ctx, nonce),
            )
            _commit_domain(
                ctx, results, "mapping",
                lambda: commit_mapping(ctx, nonce, prepared=prepared["mapping"]),
            )
            _commit_domain(
                ctx, results, "memories",
                lambda: commit_memories(
                    ctx, nonce, prepared=prepared["memories"], consolidate=False,
                ),
            )
            _commit_domain(
                ctx, results, "background_presences",
                lambda: track_background_presences(ctx, nonce),
            )
            _commit_domain(
                ctx, results, "narration_person",
                lambda: commit_narration_person(ctx, nonce),
            )
            _commit_domain(
                ctx, results, "obligations",
                lambda: commit_obligations(ctx, nonce),
            )
            _commit_domain(
                ctx, results, "pending",
                lambda: wset(ctx.chat.id, "pending", []),
            )
    except Exception as exc:
        raise RuntimeError(
            f"Commit failed and was rolled back: {exc}"
        ) from exc

    # Autobiographical summaries are derived, reconstructible caches and may
    # invoke an LLM.  They therefore run only after primary facts are durable;
    # a summary failure becomes a warning rather than corrupting the turn.
    results["memories"]["committed"].extend(
        _consolidate_committed_memories(ctx)
    )

    # Autonomous background->cast promotion likewise runs after the primary
    # transaction: it mints a sheet with an LLM call and is additive and
    # forward-only (the new character becomes step-eligible next turn), so a
    # failure is a warning, never a turn rollback.
    try:
        results["promotions"] = auto_promote_background_characters(ctx)
    except Exception as exc:
        ctx.add_warning(f"auto-promotion failed: {exc}")
        results["promotions"] = {"promoted": [], "error": str(exc)}

    return {
        "summary": (
            f"Committed turn {ctx.turn.idx}: "
            f"{len(results.get('memories', {}).get('committed', []))} "
            "memory writes"
        ),
        "errors": [],
        "results": results,
    }

# ---- Fallback helpers ----

def _lore_for(ctx):
    return (ctx.mapping_stage or ctx.mapping_quick or {}).get("relevant_lore") or []

def _normalized_fact(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()

def _fact_is_covered(fact, existing_lore):
    normalized = _normalized_fact(fact)
    if not normalized:
        return True
    fact_tokens = set(normalized.split())
    for entry in existing_lore or []:
        candidate = _normalized_fact(entry.get("content") or "")
        if not candidate:
            continue
        if normalized in candidate or candidate in normalized:
            return True
        candidate_tokens = set(candidate.split())
        union = fact_tokens | candidate_tokens
        if union:
            similarity = len(fact_tokens & candidate_tokens) / len(union)
            if similarity >= 0.72:
                return True
    return False

def _generate_fallback_ops(ok_facts, staged, world_facts, existing_lore=None):
    existing_lore = existing_lore or []
    ops = []
    for fact in ok_facts:
        text = str(fact.get("fact") or "")
        if text and not _fact_is_covered(text, existing_lore):
            ops.append({"op": "create", "keys": "", "content": text, "category": "event", "book_id": None})
    for entry in staged:
        content = str(entry.get("content") or "")
        if not content or _fact_is_covered(content, existing_lore):
            continue
        ops.append({
            "op": "create", "keys": entry.get("keys", ""), "content": content,
            "category": entry.get("category", "other"), "title": entry.get("title"),
            "knowledge_tag": entry.get("knowledge_tag"),
            "knowledge_range": entry.get("knowledge_range"),
            "knowledge_locations": entry.get("knowledge_locations"),
            "book_id": entry.get("book_id"),
        })
    for world_fact in world_facts:
        if isinstance(world_fact, dict):
            text = str(world_fact.get("fact") or "")
            source_kind = (world_fact.get("source") or {}).get("kind")
        else:
            text = str(world_fact)
            source_kind = None
        if source_kind == "lore":
            continue
        if text and not _fact_is_covered(text, existing_lore):
            ops.append({"op": "create", "keys": "", "content": text, "category": "other", "book_id": None})
    return [o for o in ops if o.get("content")]