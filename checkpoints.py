import json, time, re, hashlib
from db import active_frame_id, q, qi, transaction, wget, wset
from memory import (
    dump_chat_memories, restore_chat_memories,
    prepare_chat_memory_restore, apply_chat_memory_restore,
    dump_memory_summaries, restore_memory_summaries,
    prepare_memory_summary_restore, apply_memory_summary_restore,
    dump_lorebook, restore_lorebook, chat_lorebook_ids,
    dump_lorebook_links, restore_lorebook_links,
)

def snapshot_state(chat_id):
    chat = q("SELECT * FROM chats WHERE id=?", (chat_id,), one=True)
    world = {
        w["key"]: json.loads(w["value"])
        for w in q("SELECT * FROM world WHERE chat_id=?", (chat_id,))
    }
    chars = {
        str(c["char_id"]): {"state": json.loads(c["state"] or "{}"), "status": c["status"]}
        for c in q("SELECT * FROM chat_chars WHERE chat_id=?", (chat_id,))
    }
    char_frames = [
        {"char_id": r["char_id"], "frame_id": r["frame_id"],
         "status": r["status"], "state": json.loads(r["state"] or "{}")}
        for r in q("SELECT * FROM chat_char_frames WHERE chat_id=?", (chat_id,))
    ]
    # frames rows and persona stations are durably mutated by spatial
    # split/merge commits (spatial_frames.perform_split/perform_merge:
    # new frame rows, chat_personas.frame_id restationing, frames.
    # merged_turn_idx) -- without them in the snapshot, rerolling such a
    # turn leaves stranded personas and permanently-merged frames.
    frames = [
        {"id": r["id"], "label": r["label"], "ordinal": r["ordinal"],
         "kind": r["kind"], "travelers": r["travelers"],
         "nonexistent_cast": r["nonexistent_cast"], "created": r["created"],
         "parent_frame_id": r["parent_frame_id"],
         "split_turn_idx": r["split_turn_idx"],
         "merged_turn_idx": r["merged_turn_idx"]}
        for r in q("SELECT * FROM frames WHERE chat_id=? ORDER BY id", (chat_id,))
    ]
    chat_personas = [
        {"persona_id": r["persona_id"], "status": r["status"],
         "frame_id": r["frame_id"]}
        for r in q("SELECT * FROM chat_personas WHERE chat_id=?", (chat_id,))
    ]
    canon = chat["lorebook_id"] if chat else None
    book_ids = []
    books = []
    for lid in chat_lorebook_ids(chat_id, enabled_only=False):
        lbrow = q("SELECT * FROM lorebooks WHERE id=?", (lid,), one=True)
        if not lbrow:
            continue
        book_ids.append(lid)
        att = q("SELECT enabled FROM chat_lorebooks WHERE chat_id=? AND lorebook_id=?",
                (chat_id, lid), one=True)
        books.append({
            "lorebook_id": lid, "origin_id": lbrow["origin_id"],
            "name": lbrow["name"], "book_type": lbrow["book_type"] or "general",
            "summary": lbrow["summary"] or "",
            "parent_id": lbrow["parent_id"],
            "scope_world_id": lbrow["scope_world_id"],
            "scope_location_id": lbrow["scope_location_id"],
            "inheritance_mode": lbrow["inheritance_mode"] or "inherit",
            "sort_order": lbrow["sort_order"] or 0,
            "anchor_entity_id": lbrow["anchor_entity_id"],
            "canon": lid == canon,
            "enabled": att["enabled"] if att else 1,
            "entries": dump_lorebook(lid),
        })
    lore = None
    if canon:
        lore = {"lorebook_id": canon, "entries": dump_lorebook(canon)}

    # Snapshot links
    links = dump_lorebook_links(book_ids)

    world_entities = [
        {"entity_id": r["entity_id"], "kind": r["kind"], "subtype": r["subtype"],
         "name": r["name"], "payload": r["payload"],
         "created_turn_id": r["created_turn_id"],
         "retired_turn_id": r["retired_turn_id"]}
        for r in q("SELECT * FROM world_entities WHERE chat_id=?", (chat_id,))
    ]
    world_placements = [
        {"subject_id": r["subject_id"], "relation": r["relation"],
         "container_id": r["container_id"], "detail": r["detail"]}
        for r in q("SELECT * FROM world_placements WHERE chat_id=?", (chat_id,))
    ]
    world_conditions = [
        {"condition_id": r["condition_id"], "subject_id": r["subject_id"],
         "kind": r["kind"], "started_at": r["started_at"],
         "expires_at": r["expires_at"], "next_tick": r["next_tick"],
         "payload": r["payload"], "active": r["active"]}
        for r in q("SELECT * FROM world_conditions WHERE chat_id=?", (chat_id,))
    ]
    scheduled = [
        {"event_id": r["event_id"], "due_at": r["due_at"], "kind": r["kind"],
         "location_id": r["location_id"], "payload": r["payload"],
         "seed": r["seed"], "status": r["status"]}
        for r in q("SELECT * FROM scheduled_events WHERE chat_id=?", (chat_id,))
    ]
    fiction_worlds = [
        {"world_id": r["world_id"], "parent_world_id": r["parent_world_id"],
         "name": r["name"], "kind": r["kind"], "payload": r["payload"]}
        for r in q("SELECT * FROM fiction_worlds WHERE chat_id=?", (chat_id,))
    ]
    fiction_locations = [
        {"location_id": r["location_id"], "world_id": r["world_id"],
         "parent_location_id": r["parent_location_id"],
         "kind": r["kind"], "name": r["name"], "payload": r["payload"]}
        for r in q("SELECT * FROM fiction_locations WHERE chat_id=?", (chat_id,))
    ]

    return {
        "world": world, "chars": chars, "char_frames": char_frames,
        "frames": frames, "chat_personas": chat_personas,
        "memories": dump_chat_memories(chat_id),
        "memory_summaries": dump_memory_summaries(chat_id),
        "lore": lore, "lorebooks": books,
        "lorebook_links": links,
        "world_entities": world_entities,
        "world_placements": world_placements,
        "world_conditions": world_conditions,
        "scheduled_events": scheduled,
        "fiction_worlds": fiction_worlds,
        "fiction_locations": fiction_locations,
    }

def _restore_books(chat_id, books, links=None):
    current_ids = set(chat_lorebook_ids(chat_id, enabled_only=False))
    if not current_ids:
        return
    current = {
        row["id"]: row
        for row in q("SELECT * FROM lorebooks WHERE chat_id=?", (chat_id,))
        if row["id"] in current_ids
    }
    by_origin = {}
    by_name = {}
    for lid, row in current.items():
        if row["origin_id"] is not None:
            by_origin.setdefault(row["origin_id"], lid)
        by_name.setdefault(row["name"], lid)
    
    old_to_new = {}
    for snapshot in (books or []):
        target = snapshot.get("lorebook_id")
        if target not in current:
            origin = snapshot.get("origin_id")
            target = by_origin.get(origin) if origin is not None else None
        if target not in current:
            target = by_name.get(snapshot.get("name"))
        if target not in current:
            continue
        old_id = snapshot.get("lorebook_id")
        if old_id:
            old_to_new[old_id] = target
        row = current[target]
        qi("UPDATE lorebooks SET name=?,book_type=?,summary=?,parent_id=NULL,scope_world_id=?,scope_location_id=?,inheritance_mode=?,sort_order=?,anchor_entity_id=? WHERE id=?",
           (snapshot.get("name") or row["name"],
            snapshot.get("book_type") or row["book_type"] or "general",
            snapshot.get("summary") if snapshot.get("summary") is not None else (row["summary"] or ""),
            snapshot.get("scope_world_id"),
            snapshot.get("scope_location_id"),
            snapshot.get("inheritance_mode") or "inherit",
            snapshot.get("sort_order") or 0,
            snapshot.get("anchor_entity_id"),
            target))
        
        current_entries = dump_lorebook(target)
        snapshot_entries = snapshot.get("entries") or []
        if current_entries != snapshot_entries:
            restore_lorebook(target, snapshot_entries)
    
    for snapshot in books or []:
        old_id = snapshot.get("lorebook_id")
        target = old_to_new.get(old_id)
        parent = old_to_new.get(snapshot.get("parent_id"))
        if target is not None:
            qi("UPDATE lorebooks SET parent_id=? WHERE id=?", (parent, target))

    # The snapshot's canon book (if any) maps to this current id.
    snapshot_canon_target = None
    for snapshot in books or []:
        if snapshot.get("canon"):
            snapshot_canon_target = old_to_new.get(snapshot.get("lorebook_id"))
            break

    # Delete chat-OWNED books that no snapshot book maps onto: a book minted
    # by a since-discarded timeline (rerolled/deleted turn) must not survive
    # into canon, or the rerun would dedup against the stale book and its
    # rolled-back entries. `current` already holds only this chat's own
    # attached books (WHERE chat_id=?), so library/attached reusable books
    # are never touched. FK cascade removes the entries + chat_lorebooks row.
    matched = set(old_to_new.values())
    if snapshot_canon_target is not None:
        matched.add(snapshot_canon_target)
    for lid in list(current.keys()):
        if lid not in matched:
            qi("DELETE FROM lorebooks WHERE id=? AND chat_id=?", (lid, chat_id))

    # Restore the canon binding to the snapshot's -- and clear a canon bound
    # AFTER the snapshot (the snapshot had no canon) so discarded-timeline
    # canon can't linger on chats.lorebook_id.
    chat_row = q("SELECT lorebook_id FROM chats WHERE id=?", (chat_id,), one=True)
    if snapshot_canon_target is not None:
        qi("UPDATE chats SET lorebook_id=? WHERE id=?", (snapshot_canon_target, chat_id))
    elif chat_row and chat_row["lorebook_id"] is not None and chat_row["lorebook_id"] in current:
        qi("UPDATE chats SET lorebook_id=NULL WHERE id=?", (chat_id,))

    if links:
        restore_lorebook_links(chat_id, old_to_new, links)

def restore_checkpoint(chat_id, idx):
    r = q("SELECT * FROM checkpoints WHERE chat_id=? AND turn_idx=?", (chat_id, idx), one=True)
    if not r:
        return
    # Checkpoint blobs store fully-resolved storage keys already (see
    # snapshot_state, which dumps the `world` table's own key column
    # verbatim, suffix and all). Restoring them through wget/wset while
    # SOME frame's pipeline has active_frame_id set (recompute of a
    # framed turn runs restore mid-pipeline, after that frame was
    # already made active -- see agents/runtime.py's _run_pipeline)
    # would silently re-scope an already-resolved key a second time --
    # e.g. writing the present's bare "scene" entry into the active
    # frame's suffixed slot instead of back into its own row, wiping
    # the present's state on every reroll of a framed turn. Force the
    # raw, unscoped view for the whole restore regardless of which
    # frame's pipeline triggered it.
    token = active_frame_id.set(None)
    try:
        _restore_checkpoint_body(chat_id, r)
    finally:
        active_frame_id.reset(token)

def _restore_frames(chat_id, snap_frames):
    """Put the frames table back to snapshot state.

    Deliberately NOT delete-and-reinsert: frames.id is referenced with
    ON DELETE SET NULL by turns/memories/chat_personas and ON DELETE
    CASCADE by chat_char_frames (PRAGMA foreign_keys=ON), so deleting a
    surviving frame row -- even to reinsert it with the same id inside
    the same transaction -- would irreversibly null out the frame
    assignment of every PRE-checkpoint turn in that era. Instead:
    update rows that exist in both, reinsert snapshot rows that are
    missing under their original ids, and delete only frames that did
    not exist at snapshot time (e.g. a spatial split created by the
    very commit being rerolled -- exactly the rows whose FK fallout is
    the desired cleanup)."""
    existing = {row["id"] for row in q("SELECT id FROM frames WHERE chat_id=?", (chat_id,))}
    snap_ids = set()
    # Ascending id order inserts parents before children (frame ids are
    # allocated monotonically and parent_frame_id is set at creation),
    # keeping the immediate FK check satisfied.
    for f in sorted(snap_frames or [], key=lambda f: f["id"]):
        snap_ids.add(f["id"])
        vals = (f.get("label", ""), f.get("ordinal", 0), f.get("kind", "other"),
                f.get("travelers", "[]"), f.get("nonexistent_cast", "[]"),
                f.get("created") or time.time(), f.get("parent_frame_id"),
                f.get("split_turn_idx"), f.get("merged_turn_idx"))
        if f["id"] in existing:
            qi("""UPDATE frames SET label=?,ordinal=?,kind=?,travelers=?,
                nonexistent_cast=?,created=?,parent_frame_id=?,
                split_turn_idx=?,merged_turn_idx=? WHERE id=? AND chat_id=?""",
               vals + (f["id"], chat_id))
        else:
            qi("""INSERT INTO frames(id,chat_id,label,ordinal,kind,travelers,
                nonexistent_cast,created,parent_frame_id,split_turn_idx,merged_turn_idx)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
               (f["id"], chat_id) + vals)
    # Children before parents, for the same FK reason.
    for fid in sorted(existing - snap_ids, reverse=True):
        qi("DELETE FROM frames WHERE id=? AND chat_id=?", (fid, chat_id))

def _restore_chat_personas(chat_id, personas):
    # Delete-and-reinsert with same-chat ids, mirroring the
    # chat_char_frames restore just above it in the restore body.
    qi("DELETE FROM chat_personas WHERE chat_id=?", (chat_id,))
    for p in personas or []:
        if not q("SELECT id FROM personas WHERE id=?", (p["persona_id"],), one=True):
            # Persona deleted from the library since the snapshot; a
            # verbatim reinsert would fail FK enforcement and abort the
            # whole restore.
            continue
        qi("INSERT INTO chat_personas(chat_id,persona_id,status,frame_id) VALUES(?,?,?,?)",
           (chat_id, p["persona_id"], p.get("status", "active"), p.get("frame_id")))

def insert_world_tables(chat_id, b, delete_first=False):
    """Insert the six normalized world_* arrays from blob dict `b` into
    chat_id's tables. Ids in `b` are assumed already remapped for the
    target chat (checkpoint restore restores same-chat verbatim; branch/
    import remap first). `delete_first` clears the chat's existing rows
    (restore) -- branch/import build a fresh, empty chat and pass False.

    This is the single source of truth for populating the normalized
    world tables. Branch/import previously copied frames/turns/memories/
    world-KV but NOT these tables, leaving world.scene + fixed_points
    referencing entities that _entity_exists() couldn't find -> a false
    paradox on the first commit."""
    if delete_first:
        qi("DELETE FROM world_entities WHERE chat_id=?", (chat_id,))
    for ent in b.get("world_entities") or []:
        qi("""INSERT INTO world_entities(entity_id,chat_id,kind,subtype,name,payload,
            created_turn_id,retired_turn_id) VALUES(?,?,?,?,?,?,?,?)""",
           (ent["entity_id"], chat_id, ent["kind"], ent.get("subtype", ""),
            ent.get("name", ""), ent.get("payload", "{}"),
            ent.get("created_turn_id"), ent.get("retired_turn_id")))

    if delete_first:
        qi("DELETE FROM world_placements WHERE chat_id=?", (chat_id,))
    for pl in b.get("world_placements") or []:
        qi("""INSERT INTO world_placements(chat_id,subject_id,relation,container_id,detail)
            VALUES(?,?,?,?,?)""",
           (chat_id, pl["subject_id"], pl["relation"], pl["container_id"], pl.get("detail", "{}")))

    if delete_first:
        qi("DELETE FROM world_conditions WHERE chat_id=?", (chat_id,))
    for cond in b.get("world_conditions") or []:
        qi("""INSERT INTO world_conditions(condition_id,chat_id,subject_id,kind,
            started_at,expires_at,next_tick,payload,active) VALUES(?,?,?,?,?,?,?,?,?)""",
           (cond["condition_id"], chat_id, cond["subject_id"], cond["kind"],
            cond["started_at"], cond.get("expires_at"), cond.get("next_tick"),
            cond.get("payload", "{}"), cond.get("active", 1)))

    if delete_first:
        qi("DELETE FROM scheduled_events WHERE chat_id=?", (chat_id,))
    for ev in b.get("scheduled_events") or []:
        qi("""INSERT INTO scheduled_events(event_id,chat_id,due_at,kind,location_id,
            payload,seed,status) VALUES(?,?,?,?,?,?,?,?)""",
           (ev["event_id"], chat_id, ev["due_at"], ev["kind"],
            ev.get("location_id"), ev.get("payload", "{}"),
            ev.get("seed", ""), ev.get("status", "pending")))

    if delete_first:
        qi("DELETE FROM fiction_worlds WHERE chat_id=?", (chat_id,))
    for fw in b.get("fiction_worlds") or []:
        qi("""INSERT INTO fiction_worlds(world_id,chat_id,parent_world_id,name,kind,payload)
            VALUES(?,?,?,?,?,?)""",
           (fw["world_id"], chat_id, fw.get("parent_world_id"),
            fw["name"], fw.get("kind", "world"), fw.get("payload", "{}")))

    if delete_first:
        qi("DELETE FROM fiction_locations WHERE chat_id=?", (chat_id,))
    for fl in b.get("fiction_locations") or []:
        qi("""INSERT INTO fiction_locations(location_id,chat_id,world_id,
            parent_location_id,kind,name,payload) VALUES(?,?,?,?,?,?,?)""",
           (fl["location_id"], chat_id, fl["world_id"],
            fl.get("parent_location_id"), fl.get("kind", "location"),
            fl["name"], fl.get("payload", "{}")))

def _restore_checkpoint_body(chat_id, r):
    b = json.loads(r["blob"])
    # Any embedding work (only needed for legacy blobs that predate
    # vectors traveling inside the dump) happens here, BEFORE the write
    # transaction opens: a remote provider call must never hold SQLite's
    # write lock, and a provider failure must leave the chat untouched.
    mem_plan = (prepare_chat_memory_restore(chat_id, b.get("memories") or [])
                if "memories" in b else None)
    summary_plan = (prepare_memory_summary_restore(b.get("memory_summaries") or [])
                    if "memory_summaries" in b else None)
    # One transaction for the whole restore: previously ~15 autocommit
    # statements meant a crash mid-way left world state restored but
    # memories/entities half-gone. Now any failure rolls the entire
    # restore back and the chat stays exactly as it was.
    with transaction():
        qi("DELETE FROM world WHERE chat_id=?", (chat_id,))
        for k, v in (b.get("world") or {}).items():
            wset(chat_id, k, v)
        for cidk, st in (b.get("chars") or {}).items():
            if isinstance(st, dict) and "status" in st and "state" in st:
                qi("UPDATE chat_chars SET state=?,status=? WHERE chat_id=? AND char_id=?",
                   (json.dumps(st["state"]), st["status"], chat_id, int(cidk)))
            else:
                qi("UPDATE chat_chars SET state=? WHERE chat_id=? AND char_id=?",
                   (json.dumps(st), chat_id, int(cidk)))
        # Frames must be restored before chat_char_frames/chat_personas
        # (whose rows FK-reference frame ids) and before memories (whose
        # frame_id stamps must land on existing frames).
        if "frames" in b:
            _restore_frames(chat_id, b.get("frames") or [])
        qi("DELETE FROM chat_char_frames WHERE chat_id=?", (chat_id,))
        for cf in b.get("char_frames") or []:
            qi("""INSERT INTO chat_char_frames(chat_id,char_id,frame_id,status,state)
                VALUES(?,?,?,?,?)""",
               (chat_id, cf["char_id"], cf["frame_id"], cf.get("status", "active"),
                json.dumps(cf.get("state") or {})))
        if "chat_personas" in b:
            _restore_chat_personas(chat_id, b.get("chat_personas") or [])
        if mem_plan is not None:
            apply_chat_memory_restore(chat_id, mem_plan)
        if summary_plan is not None:
            apply_memory_summary_restore(chat_id, summary_plan)
        if "lorebooks" in b:
            _restore_books(chat_id, b.get("lorebooks") or [], b.get("lorebook_links") or [])

        insert_world_tables(chat_id, b, delete_first=True)

        current_book_ids = set(chat_lorebook_ids(chat_id, enabled_only=False))
        cache = wget(chat_id, "lore_cache", []) or []
        cache = [entry for entry in cache
                 if isinstance(entry, dict) and entry.get("book_id") in current_book_ids]
        seen = set()
        deduplicated = []
        for entry in cache:
            key = entry.get("entry_uid") or _lore_cache_fingerprint(entry)
            if key in seen:
                continue
            seen.add(key)
            deduplicated.append(entry)
        wset(chat_id, "lore_cache", deduplicated[:24])
def _lore_cache_fingerprint(entry):
    keys = re.sub(r"\s+", " ", str(entry.get("keys") or "").strip().casefold())
    content = re.sub(r"\s+", " ", str(entry.get("content") or "").strip().casefold())
    digest = hashlib.sha256(f"{keys}\x1f{content}".encode("utf-8")).hexdigest()
    return f"content:{digest}"

def ensure_checkpoint(chat_id, turn_idx):
    """Ensure a checkpoint exists for the given turn index.

    Captures the current world/character/lore state so it can be
    restored if the turn is deleted or re-run.
    """
    existing = q(
        "SELECT id FROM checkpoints WHERE chat_id=? AND turn_idx=?",
        (chat_id, turn_idx),
        one=True,
    )
    if existing:
        return existing["id"]
    blob = json.dumps(snapshot_state(chat_id))
    return qi(
        "INSERT INTO checkpoints(chat_id, turn_idx, blob, created) "
        "VALUES(?,?,?,?)",
        (chat_id, turn_idx, blob, time.time()),
    )

def refresh_checkpoint(chat_id, turn_idx):
    """Patch ONLY the lorebook-related sections of the checkpoint at
    turn_idx to reflect a lorebook attach/detach.

    A checkpoint is a PRE-turn snapshot: it must keep the world/character/
    memory/frame state as it was BEFORE that turn ran, so that a later
    reroll/delete restores to a clean pre-turn baseline. The previous
    implementation re-snapshotted the WHOLE chat POST-turn, which broke
    "a checkpoint precedes durable mutation": rerolling that turn would
    then re-apply its already-applied relationship deltas, keep discarded
    known/lore/background bookkeeping, and re-diff the scene. Attach/detach
    only changes the book set, so only the book sections are refreshed;
    everything else in the existing blob is left untouched.
    """
    row = q(
        "SELECT blob FROM checkpoints WHERE chat_id=? AND turn_idx=?",
        (chat_id, turn_idx),
        one=True,
    )
    if not row:
        # No pre-turn checkpoint captured yet -- fall back to a full
        # snapshot (nothing to preserve).
        return ensure_checkpoint(chat_id, turn_idx)
    blob = json.loads(row["blob"])
    fresh = snapshot_state(chat_id)
    for key in ("lore", "lorebooks", "lorebook_links"):
        blob[key] = fresh.get(key)
    qi(
        "UPDATE checkpoints SET blob=?, created=? WHERE chat_id=? AND turn_idx=?",
        (json.dumps(blob), time.time(), chat_id, turn_idx),
    )