"""Room identity across frames: the room_registry projection, mint dedup,
renames, retirement, and dangling-exit pruning.

Extracted verbatim from commit.py, which re-exports every name here.
See docs/experiments/AUDIT_COMMIT.md for the split record.
"""

import json
from core.db import q, qi
from story.character_schema import persona_name
from world.spatial import normalize_room_id
from persist.commit_common import _room_of


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
        payload = {}
        original_payload = {}
        if row is not None:
            try:
                payload = dict(json.loads(row["payload"] or "{}"))
                original_payload = dict(payload)
            except Exception:
                payload = {}
        planned = payload.get("planned")
        if isinstance(planned, dict):
            # Resolution is derived from actual mapped prose, never a second
            # state machine an author or model has to remember to flip.
            planned = dict(planned)
            planned["resolved"] = bool(str(
                rdef.get("desc") or rdef.get("description") or "").strip())
            payload["planned"] = planned
        if row is not None \
                and row["owning_book_id"] == book_id \
                and row["parent_entity"] == owner \
                and row["name"] == name \
                and row["aliases"] == json.dumps(aliases) \
                and payload == original_payload \
                and row["retired_turn_id"] is None:
            continue  # already registered, identical, live
        upserts.append({
            "room_uid": rid, "owning_book_id": book_id,
            "parent_entity": owner, "name": name, "aliases": aliases,
            "payload": payload,
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
            "payload=excluded.payload,"
            "retired_turn_id=NULL",
            (cid, row["room_uid"], row["owning_book_id"],
             row["parent_entity"], row["name"], json.dumps(row["aliases"]),
             json.dumps(row.get("payload") or {}), turn_id),
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


def _refresh_relocated_location(sc, prev_scene, diff, ctx):
    """Refresh scene.location when the player has CHANGED rooms this turn. See
    the DW-1 call site in prepare_scene_commit.

    Originally scoped to relocations into a NEWLY-MINTED room (DW-1: mapping
    coins a fresh destination and the label still names the old place). But a
    move into a room that ALREADY EXISTED needs the same refresh -- beaming
    back aboard from a planet surface (TR-3) left the label reading 'Sigma
    Draconis VII -- Surface' while every position was in the ship's transporter
    room. The trigger is therefore the player's room changing, not the room
    being new.
    """
    try:
        from story.scene import persona_of
        player_name = persona_name(persona_of(ctx.chat))
    except Exception:
        return
    player_room = _room_of(sc, player_name)
    if not player_room:
        return
    if player_room == _room_of(prev_scene, player_name):
        return  # no move -- label stays put
    rooms = sc.get("rooms") or {}
    cur_loc = str(sc.get("location") or "").strip()
    # Refresh only when the label is actually stale for the destination:
    #   - the destination room is BRAND NEW to the scene (DW-1: mapping minted
    #     it and the label still names the old place), or
    #   - the current label still names a SPECIFIC room the player has now LEFT
    #     (TR-3: 'Sigma Draconis VII -- Surface' while aboard the ship).
    # A venue-level label that matches no room (e.g. 'The Old Anchor' with rooms
    # 'Bar'/'Kitchen') is deliberately left alone on an in-venue room move.
    new_room = player_room not in (prev_scene.get("rooms") or {})
    names_left_room = any(
        cur_loc and cur_loc == str((r or {}).get("name") or "").strip()
        and rid != player_room
        for rid, r in rooms.items())
    if not (new_room or names_left_room):
        return
    # Prefer a location the Director named this turn, else the destination's name.
    new_loc = str(diff.get("location") or "").strip() \
        or str((rooms.get(player_room) or {}).get("name") or "").strip()
    if new_loc and new_loc != cur_loc:
        sc["location"] = new_loc
    # scene.description is the label's prose sibling and was only ever written
    # from director_establish -- i.e. once, on the opening turn, and then never
    # again. Live (Elevator Adventure branch 41) it still described the surface
    # elevator bay 92 turns later, with the party in a sub-basement chamber.
    # Nothing reads it back today, so this is a latent staleness rather than an
    # observed leak, but it is exactly what DW-1 fixed for `location` and the
    # same trigger applies.
    new_desc = str(diff.get("description") or "").strip() \
        or str((rooms.get(player_room) or {}).get("desc") or "").strip()
    if new_desc:
        sc["description"] = new_desc


def prune_dangling_exits(sc):
    """Drop room exits whose target room does not exist. Returns warnings.

    The merge already drops edges pointing at rooms it just REMOVED, but never
    checked that an edge's target exists in the first place, so a model naming
    a room it never defined committed a permanent broken exit. Found live in
    "The Doctor — Hinami": the janitor closet carried an exit to
    `enterprise_corridor` while only `enterprise_corridor_deck10` and
    `_deck14` existed.

    A dangling exit is not cosmetic. spatial.py treats `adjacent` as the
    authority on what leaves a room, so the exit is offered to the Director and
    the narrator as real, movement through it resolves against a room with no
    description or position, and pathing counts a neighbour that cannot be
    reached. Dropping is the conservative repair: the edge described a place
    the world never had.
    """
    warnings = []
    rooms = sc.get("rooms")
    if not isinstance(rooms, dict):
        return warnings
    for rid, room in rooms.items():
        if not isinstance(room, dict) or not isinstance(room.get("adjacent"), list):
            continue
        kept, dropped = [], []
        for edge in room["adjacent"]:
            if not isinstance(edge, dict):
                continue
            target = edge.get("to")
            if target in rooms:
                kept.append(edge)
            else:
                dropped.append(str(target))
        if dropped:
            room["adjacent"] = kept
            warnings.append(
                "scene: dropped exit(s) from %s to undefined room(s) %s"
                % (rid, ", ".join(sorted(set(dropped)))))
    return warnings
