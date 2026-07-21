"""Atomic world-state commit with mutation validation."""

import copy
import json, time, random, re, hashlib, threading, weakref
from concurrent.futures import ThreadPoolExecutor
from db import q, qi, qtx, transaction, wget, wset
from memory import (
    add_memories_batch, prepare_memories_batch, delete_turn_memories, search_lore, add_lore,
    update_lore, delete_lore, LORE_CATEGORIES, LOREBOOK_TYPES,
    chat_lorebook_ids, chat_lorebook_weights, lorebook_manifest, dump_chat_memories,
    add_lorebook_link,
    restore_chat_memories, dump_lorebook, restore_lorebook,
    knowledge_for_character, get_relationships,
    save_relationships, update_relationships_from_inference,
    apply_relationship_updates, maybe_consolidate_character_memory,
)
from providers import embed_texts
from prompts import get_prompt
from character_schema import character_name, new_uid
from frames import is_recognized_in_frame
from scene import set_char_state, set_char_status
from spatial import (apply_transit_dock_edges, merge_scene_with_diff,
                     normalize_room_id, spatial_rel, hear_level)
from theory_of_mind import apply_mind_model_updates
from paradox import check_and_apply_paradox
from spatial_frames import detect_and_reconcile as detect_and_reconcile_spatial
from spatial_frames import infer_companion_carry, infer_vehicle_zones

_COMMIT_LOCKS = weakref.WeakValueDictionary()
_COMMIT_LOCKS_GUARD = threading.Lock()

def _commit_lock(turn_id):
    with _COMMIT_LOCKS_GUARD:
        return _COMMIT_LOCKS.setdefault(turn_id, threading.Lock())

def _keys_str(value):
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(v) for v in value if v is not None)
    return str(value or "")

def _stable_event_key(*parts):
    raw = "\x1f".join(str(part or "") for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return f"event:{digest}"

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

def _guard_occupied_mover_removal(prev_scene, diff):
    """Deterministic refusal: removing an entity whose parent_entity-linked
    interior rooms still hold occupants, without the same beat repositioning
    every occupant (state_diff.positions, to a room OUTSIDE the doomed
    interior) or recording their departure (cast_changes), would leave
    people positioned inside rooms of a container that no longer exists.
    Raising here fails commit preparation, so the whole turn rolls back per
    the existing atomicity contract -- the same conservatism as
    merge_scene_with_diff's occupied-room removal refusal, made loud
    because losing PEOPLE is worse than losing a room."""
    removals = [str(e) for e in (diff.get("remove_entities") or []) if e]
    if not removals:
        return
    rooms = prev_scene.get("rooms") or {}
    positions = prev_scene.get("positions") or {}
    diff_positions = {
        str(k).casefold(): v for k, v in (diff.get("positions") or {}).items()
    }
    departed = {
        str(c.get("who") or "").casefold()
        for c in (diff.get("cast_changes") or []) if isinstance(c, dict)
    }
    for eid in removals:
        interior = {rid for rid, r in rooms.items()
                    if isinstance(r, dict) and r.get("parent_entity") == eid}
        if not interior:
            continue
        stranded = []
        for name, room in positions.items():
            if room not in interior or str(name) == eid:
                continue
            cf = str(name).casefold()
            new_room = diff_positions.get(cf)
            if new_room is not None and new_room not in interior:
                continue
            if cf in departed:
                continue
            stranded.append(name)
        if stranded:
            raise RuntimeError(
                f"remove_entities would strand occupant(s) {stranded!r} "
                f"inside removed entity {eid!r}'s interior room(s); "
                "reposition them via state_diff.positions or record their "
                "departure in cast_changes in the same beat"
            )

# ---- Room registry (derived) + commit-side structural dedup ----
#
# Two live failure classes share one root: nothing at commit time knew which
# rooms an owner (a vehicle, the current location) ALREADY has. (1) Two
# structurally identical vehicles minting the same interior key ("deck_3")
# silently merged one ship's deck into the other's. (2) The same owner's
# room re-minted under a fresh key ("deck_three" for an existing "Deck 3")
# created a live duplicate that only the advisory remove_rooms self-heal
# might later clean up. The registry below records each room as a DERIVED
# lore_entries row (category 'layout', entry_uid 'room:<book_id>:<room_key>')
# under its owning vehicle/location book, rewritten at every commit -- the
# scene JSON stays the sole authority for live rooms; the registry is a
# ledger, never a cage: a colliding mint is REDIRECTED or REKEYED, never
# rejected (invention is always allowed, duplication is not).

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

def _registry_alias_index(book_id):
    """{normalized name/alias: room_key} for every room registered under
    one owning book -- read from the derived registry rows themselves."""
    index = {}
    prefix = f"room:{book_id}:"
    for row in q(
        "SELECT entry_uid, keys FROM lore_entries "
        "WHERE lorebook_id=? AND category='layout' AND entry_uid LIKE ?",
        (book_id, prefix + "%"),
    ):
        room_key = row["entry_uid"][len(prefix):]
        for alias in str(row["keys"] or "").split(","):
            slug = normalize_room_id(alias)
            if slug:
                index.setdefault(slug, room_key)
        index.setdefault(normalize_room_id(room_key), room_key)
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
                registry_cache[book_id] = _registry_alias_index(book_id)
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

def _prepare_room_registry(cid, canon_book_id, sc):
    """Build the derived registry rows for this commit -- pure reads plus a
    batched embedding call, so it runs in preparation, before the write
    lock. Each room registers under its owning book: parent_entity rooms
    under the entity's anchored book; open-location rooms under the book
    whose scope_location_id matches the location (falling back to chat
    canon). Rows are DERIVED -- rewritten every commit, never a second
    authority over the scene JSON."""
    rooms = sc.get("rooms") or {}
    entities = sc.get("entities") or {}
    anchor_books = _anchored_book_ids(cid)
    location_slug = normalize_room_id(str(sc.get("location") or ""))
    location_book = None
    if location_slug:
        row = q(
            "SELECT id FROM lorebooks WHERE chat_id=? AND "
            "scope_location_id=? ORDER BY id LIMIT 1",
            (cid, location_slug), one=True,
        )
        location_book = row["id"] if row else None
    default_book = location_book or canon_book_id

    plan = {}
    for rid, rdef in rooms.items():
        if not isinstance(rdef, dict):
            continue
        owner = rdef.get("parent_entity")
        book_id = anchor_books.get(owner) if owner else default_book
        if not book_id:
            continue
        name = str(rdef.get("name") or rid)
        if owner:
            ent = entities.get(owner)
            owner_label = (ent.get("name") if isinstance(ent, dict) else "") \
                or owner
            place = f"aboard {owner_label}"
        else:
            place = f"at {sc.get('location') or 'this location'}"
        keys = ", ".join(dict.fromkeys(
            [name, str(rid).replace("_", " ")]))
        content = f"Room registry: {name} (room id '{rid}') {place}."
        plan.setdefault(book_id, {})[str(rid)] = {
            "entry_uid": f"room:{book_id}:{rid}",
            "keys": keys, "content": content,
        }

    upserts, stale_ids = [], []
    # Sweep every book that can hold registry rows, including one whose
    # last registered room disappeared this beat (it has no plan entry at
    # all -- exactly the case whose stale rows must still be removed).
    registry_books = set(anchor_books.values()) | set(plan)
    if default_book:
        registry_books.add(default_book)
    for book_id in sorted(registry_books):
        entries = plan.get(book_id, {})
        prefix = f"room:{book_id}:"
        existing = {
            row["entry_uid"]: row
            for row in q(
                "SELECT id, entry_uid, keys, content FROM lore_entries "
                "WHERE lorebook_id=? AND category='layout' "
                "AND entry_uid LIKE 'room:%'",
                (book_id,),
            )
        }
        for uid, row in existing.items():
            # Stale: a registered room no longer live, or a row carried in
            # under another book's uid prefix (chat import copies rows
            # verbatim; the registry is derived, so rewrite it wholesale).
            if not uid.startswith(prefix) or uid[len(prefix):] not in entries:
                stale_ids.append(row["id"])
        for entry in entries.values():
            old = existing.get(entry["entry_uid"])
            if old and old["keys"] == entry["keys"] \
                    and old["content"] == entry["content"]:
                continue
            upserts.append({
                "book_id": book_id,
                "existing_id": old["id"] if old else None,
                **entry,
            })
    if upserts:
        vectors = embed_texts(
            [f"{r['keys']} {r['content']}" for r in upserts])
        for row, vector in zip(upserts, vectors):
            row["embedding"] = vector
    return {"upserts": upserts, "stale_ids": stale_ids}

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
    room_renames = dedup_minted_rooms(
        cid, prev_scene, diff, add_warning=ctx.add_warning)
    _guard_occupied_mover_removal(prev_scene, diff)
    sc = merge_scene_with_diff(prev_scene, diff)

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
    infer_companion_carry(
        cid, ctx.turn.frame_id, prev_scene, sc,
        [character_name(json.loads(c["sheet"])) for c in ctx.cast],
        diff.get("cast_changes") or [],
    )

    return {
        "scene": sc, "clock": clock,
        "room_registry": _prepare_room_registry(cid, chat.lorebook_id, sc),
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
        # Rewrite the derived room registry (see the dedup block comment):
        # embeddings were prepared before the write lock; these rows are
        # reconstructible bookkeeping, never a second authority.
        for entry_id in registry.get("stale_ids") or []:
            delete_lore(entry_id)
        for row in registry.get("upserts") or []:
            if row.get("existing_id"):
                update_lore(
                    row["existing_id"], row["keys"], row["content"],
                    "layout", embedding=row.get("embedding"),
                )
            else:
                add_lore(
                    row["book_id"], row["keys"], row["content"],
                    category="layout", entry_uid=row["entry_uid"],
                    importance=0.2, embedding=row.get("embedding"),
                )
    return sc

# ---- Transit sweep: timed arrivals, condition expiry, engine notices ----

def commit_transit_sweep(ctx, nonce, *, prepared=None):
    """Deterministic mechanical follow-through for moving rooms, run FIRST
    among commit_all's domains -- it mutates the PREPARED scene, and
    commit_scene (which runs after it) is what persists those effects.

    1. Fire due scheduled 'transit_arrival' events for THIS frame. The
       frame id rides in each event's payload: scheduled_events has no
       frame column and simulation clocks are frame-scoped, so an event
       minted in one frame must never fire against another frame's clock.
       Firing = set the entity's position to the destination, phase to
       docked, and stage a mechanical notice (world key 'engine_notices',
       overwritten every sweep so notices self-expire after one beat) that
       the next director turn acknowledges rather than re-invents.
    2. Schedule new arrivals for any entity whose transit state carries
       eta_seconds + destination_room and has no pending event yet, with a
       deterministic event id so a rerun cannot double-schedule.
    3. Deactivate expired world_conditions (expires_at <= this frame's
       clock) -- reviving the dormant expires_at column so 'the fire burns
       out' is encodable as expiry rather than neglect. world_conditions is
       chat-scoped (no frame column); the committing frame's clock is used,
       matching how started_at is written.

    All writes run inside the caller's transaction (nested transaction() is
    a savepoint), and checkpoint restore snapshots scheduled_events whole,
    so a rerolled turn reproduces the exact pending/fired state.
    """
    cid = ctx.chat.id
    frame_id = ctx.turn.frame_id
    prepared = prepared or prepare_scene_commit(ctx)
    sc = prepared["scene"]
    clock = prepared.get("clock") or wget(cid, "simulation_clock", {}) or {}
    elapsed = float(clock.get("elapsed_seconds") or 0.0)

    notices = []
    fired = scheduled = 0
    entities = sc.get("entities") or {}
    positions = sc.setdefault("positions", {})

    with transaction():
        pending_entity_ids = set()
        for row in q(
            "SELECT * FROM scheduled_events WHERE chat_id=? AND "
            "status='pending' AND kind='transit_arrival' ORDER BY due_at",
            (cid,),
        ):
            try:
                payload = json.loads(row["payload"] or "{}")
            except Exception:
                payload = {}
            eid = str(payload.get("entity_id") or "")
            if payload.get("frame_id") != frame_id or row["due_at"] > elapsed:
                pending_entity_ids.add(eid)
                continue
            ent = entities.get(eid)
            state = ent.get("state") if isinstance(ent, dict) else None
            transit = state.get("transit") if isinstance(state, dict) else None
            if not isinstance(transit, dict) \
                    or str(transit.get("phase") or "").casefold() == "docked":
                # Entity gone, or the director already docked it by hand --
                # the event is moot, not fireable.
                qtx("UPDATE scheduled_events SET status='cancelled' "
                    "WHERE event_id=?", (row["event_id"],))
                continue
            destination = str(payload.get("destination_room")
                              or transit.get("destination_room") or "")
            if destination:
                positions[eid] = destination
            transit["phase"] = "docked"
            transit.pop("eta_seconds", None)
            transit.pop("destination_room", None)
            qtx("UPDATE scheduled_events SET status='fired' WHERE event_id=?",
                (row["event_id"],))
            fired += 1
            label = (ent.get("name") if isinstance(ent, dict) else "") or eid
            notices.append(
                f"{label} has arrived at "
                f"{destination or 'its destination'} and is docked there."
            )

        for eid, ent in entities.items():
            if not isinstance(ent, dict):
                continue
            state = ent.get("state")
            transit = state.get("transit") if isinstance(state, dict) else None
            if not isinstance(transit, dict):
                continue
            try:
                eta = float(transit.get("eta_seconds"))
            except (TypeError, ValueError):
                continue
            destination = str(transit.get("destination_room") or "")
            if eta <= 0 or not destination or str(eid) in pending_entity_ids:
                continue
            event_id = _stable_event_key(
                "transit_arrival", cid, frame_id, eid, ctx.turn.id)
            qtx(
                "INSERT OR REPLACE INTO scheduled_events"
                "(event_id,chat_id,due_at,kind,location_id,payload,seed,status)"
                " VALUES(?,?,?,?,?,?,?,?)",
                (event_id, cid, elapsed + eta, "transit_arrival",
                 positions.get(eid),
                 json.dumps({"entity_id": eid,
                             "destination_room": destination,
                             "frame_id": frame_id}, ensure_ascii=False),
                 f"transit:{cid}:{ctx.turn.idx}", "pending"),
            )
            scheduled += 1

        if fired:
            # An arrival changed the inputs the dock-edge rewrite derives
            # doorways from; recompute before commit_scene persists.
            apply_transit_dock_edges(sc)

        expired_row = q(
            "SELECT COUNT(*) AS n FROM world_conditions WHERE chat_id=? AND "
            "active=1 AND expires_at IS NOT NULL AND expires_at<=?",
            (cid, elapsed), one=True,
        )
        expired = int(expired_row["n"] or 0) if expired_row else 0
        if expired:
            qtx("UPDATE world_conditions SET active=0 WHERE chat_id=? AND "
                "active=1 AND expires_at IS NOT NULL AND expires_at<=?",
                (cid, elapsed))

        wset(cid, "engine_notices", notices)

    return {"fired": fired, "scheduled": scheduled, "expired": expired,
            "notices": notices}

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

def commit_world_entities(ctx, nonce):
    """Commit world entities, placements, conditions, and scheduled events."""
    chat = ctx.chat
    cid = chat.id
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
                    has_book = c.execute(
                        "SELECT 1 FROM lorebooks WHERE chat_id=? AND anchor_entity_id=?",
                        (cid, entity_id),
                    ).fetchone()
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


def track_background_presences(ctx, nonce):
    """Deterministic, LLM-free tracking of named entities the director
    keeps writing into resolved_event/dialogue_log who are NOT a
    registered cast member, a persona, or an extra player -- e.g. a
    ship's doctor the director has kept consistently present and active
    across many turns despite her having no character sheet, no
    character_step call, and no memory. This never invents a candidate
    from free prose (no NER over resolved_event) -- only from the same
    structured fields commit already trusts: dialogue_log speakers,
    state_diff.entities with kind person/npc, director_establish's
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

    for d in (res.get("dialogue_log") or []):
        speaker = str(d.get("speaker") or "").strip()
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
            if entity_def.get("kind") not in ("person", "npc"):
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
    reproducing the historical single-winner behavior exactly.
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

    candidates = []
    for name, record in presences.items():
        cf = name.casefold()
        if cf in roster or cf in voiced_this_beat:
            continue
        addressed = _background_name_mentioned(name, player_input)
        # A registered character (or the player) who spoke directly TO this
        # presence this beat -- read-only here; the owed-reply debt is written
        # at commit (track_background_presences), never in this pre-commit gate.
        station_room = (record.get("sketch") or {}).get("station_room")
        char_addr = _character_address_of(dr_output, name, roster, sc, station_room)
        owed = _valid_pending_reply(record, turn_idx)
        mentioned = _background_name_mentioned(name, resolved_event)
        dialogue_turns = record.get("dialogue_turns") or []
        if not (addressed or char_addr or owed or mentioned or dialogue_turns):
            continue
        priority = (bool(addressed), bool(char_addr), bool(owed),
                    bool(mentioned), len(dialogue_turns),
                    record.get("last_turn") or -1)
        candidates.append((priority, name))

    if not candidates:
        return []
    candidates.sort(reverse=True)
    return [name for _, name in candidates[:max(0, int(cap))]]

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

        dup = next((
            row for row in existing.values()
            if row["name"].casefold() == name.casefold()
            or (anchor and row["anchor_entity_id"] == anchor)
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
                scope_loc, anchor, new_uid("book"),
            ),
        )
        created += 1
        existing[new_id] = {
            "id": new_id, "name": name, "book_type": book_type,
            "anchor_entity_id": anchor, "scope_location_id": scope_loc,
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

# ---- Memory commit ----

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
            if own_result.get("active_state"):
                asv = own_result["active_state"]
                st["active_state"] = (
                    asv if isinstance(asv, dict)
                    else {"mood": str(asv), "goal": ""}
                )
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
                lambda: commit_world_entities(ctx, nonce),
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