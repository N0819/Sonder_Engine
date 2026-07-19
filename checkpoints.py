import json, time, re, hashlib
from db import active_frame_id, q, qi, wget, wset
from memory import (
    dump_chat_memories, restore_chat_memories,
    dump_memory_summaries, restore_memory_summaries,
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
        qi("UPDATE lorebooks SET name=?,book_type=?,summary=?,parent_id=NULL,scope_world_id=?,scope_location_id=?,inheritance_mode=?,sort_order=? WHERE id=?",
           (snapshot.get("name") or row["name"],
            snapshot.get("book_type") or row["book_type"] or "general",
            snapshot.get("summary") if snapshot.get("summary") is not None else (row["summary"] or ""),
            snapshot.get("scope_world_id"),
            snapshot.get("scope_location_id"),
            snapshot.get("inheritance_mode") or "inherit",
            snapshot.get("sort_order") or 0,
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

def _restore_checkpoint_body(chat_id, r):
    b = json.loads(r["blob"])
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
    qi("DELETE FROM chat_char_frames WHERE chat_id=?", (chat_id,))
    for cf in b.get("char_frames") or []:
        qi("""INSERT INTO chat_char_frames(chat_id,char_id,frame_id,status,state)
            VALUES(?,?,?,?,?)""",
           (chat_id, cf["char_id"], cf["frame_id"], cf.get("status", "active"),
            json.dumps(cf.get("state") or {})))
    if "memories" in b:
        restore_chat_memories(chat_id, b.get("memories") or [])
    if "memory_summaries" in b:
        restore_memory_summaries(chat_id, b.get("memory_summaries") or [])
    if "lorebooks" in b:
        _restore_books(chat_id, b.get("lorebooks") or [], b.get("lorebook_links") or [])

    # Restore world entities
    qi("DELETE FROM world_entities WHERE chat_id=?", (chat_id,))
    for ent in b.get("world_entities") or []:
        qi("""INSERT INTO world_entities(entity_id,chat_id,kind,subtype,name,payload,
            created_turn_id,retired_turn_id) VALUES(?,?,?,?,?,?,?,?)""",
           (ent["entity_id"], chat_id, ent["kind"], ent.get("subtype", ""),
            ent.get("name", ""), ent.get("payload", "{}"),
            ent.get("created_turn_id"), ent.get("retired_turn_id")))

    qi("DELETE FROM world_placements WHERE chat_id=?", (chat_id,))
    for pl in b.get("world_placements") or []:
        qi("""INSERT INTO world_placements(chat_id,subject_id,relation,container_id,detail)
            VALUES(?,?,?,?,?)""",
           (chat_id, pl["subject_id"], pl["relation"], pl["container_id"], pl.get("detail", "{}")))

    qi("DELETE FROM world_conditions WHERE chat_id=?", (chat_id,))
    for cond in b.get("world_conditions") or []:
        qi("""INSERT INTO world_conditions(condition_id,chat_id,subject_id,kind,
            started_at,expires_at,next_tick,payload,active) VALUES(?,?,?,?,?,?,?,?,?)""",
           (cond["condition_id"], chat_id, cond["subject_id"], cond["kind"],
            cond["started_at"], cond.get("expires_at"), cond.get("next_tick"),
            cond.get("payload", "{}"), cond.get("active", 1)))

    qi("DELETE FROM scheduled_events WHERE chat_id=?", (chat_id,))
    for ev in b.get("scheduled_events") or []:
        qi("""INSERT INTO scheduled_events(event_id,chat_id,due_at,kind,location_id,
            payload,seed,status) VALUES(?,?,?,?,?,?,?,?)""",
           (ev["event_id"], chat_id, ev["due_at"], ev["kind"],
            ev.get("location_id"), ev.get("payload", "{}"),
            ev.get("seed", ""), ev.get("status", "pending")))

    qi("DELETE FROM fiction_worlds WHERE chat_id=?", (chat_id,))
    for fw in b.get("fiction_worlds") or []:
        qi("""INSERT INTO fiction_worlds(world_id,chat_id,parent_world_id,name,kind,payload)
            VALUES(?,?,?,?,?,?)""",
           (fw["world_id"], chat_id, fw.get("parent_world_id"),
            fw["name"], fw.get("kind", "world"), fw.get("payload", "{}")))

    qi("DELETE FROM fiction_locations WHERE chat_id=?", (chat_id,))
    for fl in b.get("fiction_locations") or []:
        qi("""INSERT INTO fiction_locations(location_id,chat_id,world_id,
            parent_location_id,kind,name,payload) VALUES(?,?,?,?,?,?,?)""",
           (fl["location_id"], chat_id, fl["world_id"],
            fl.get("parent_location_id"), fl.get("kind", "location"),
            fl["name"], fl.get("payload", "{}")))

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
    """Re-snapshot current state into the checkpoint at turn_idx.

    Called when lorebooks are attached/detached so the checkpoint
    reflects the updated book set.
    """
    blob = json.dumps(snapshot_state(chat_id))
    qi(
        "INSERT INTO checkpoints(chat_id, turn_idx, blob, created) "
        "VALUES(?,?,?,?) "
        "ON CONFLICT(chat_id, turn_idx) DO UPDATE SET "
        "blob=excluded.blob, created=excluded.created",
        (chat_id, turn_idx, blob, time.time()),
    )