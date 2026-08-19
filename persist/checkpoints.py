import json, time, re, hashlib, threading, logging
from core.db import active_frame_id, q, qi, transaction, wget, wset
logger = logging.getLogger(__name__)

from mind.memory import (
    put_memory_vector, get_memory_vectors, vector_address, _b64_to_blob,
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
    # Snapshot durable ownership, not only retrieval reachability. Isolated
    # descendants intentionally do not inherit/retrieve through their parent,
    # but they are still chat-owned state that a reroll must restore exactly.
    book_ids = []
    for lid in [
        canon,
        *(row["id"] for row in q(
            "SELECT id FROM lorebooks WHERE chat_id=? ORDER BY sort_order,id",
            (chat_id,),
        )),
        *(row["lorebook_id"] for row in q(
            "SELECT lorebook_id FROM chat_lorebooks WHERE chat_id=?",
            (chat_id,),
        )),
        *chat_lorebook_ids(chat_id, enabled_only=False),
    ]:
        if lid is not None and lid not in book_ids:
            book_ids.append(lid)
    books = []
    for lid in book_ids:
        lbrow = q("SELECT * FROM lorebooks WHERE id=?", (lid,), one=True)
        if not lbrow:
            continue
        att = q("SELECT enabled FROM chat_lorebooks WHERE chat_id=? AND lorebook_id=?",
                (chat_id, lid), one=True)
        books.append({
            "lorebook_id": lid, "origin_id": lbrow["origin_id"],
            # A book's PORTABLE identity, carried so a re-created book comes
            # back as the same resource rather than as a stranger with the
            # same name (see _recreate_snapshot_book). Absent from older
            # blobs, which is why every reader of it falls back to a mint.
            "resource_uid": lbrow["resource_uid"],
            "name": lbrow["name"], "book_type": lbrow["book_type"] or "general",
            "summary": lbrow["summary"] or "",
            "parent_id": lbrow["parent_id"],
            "scope_world_id": lbrow["scope_world_id"],
            "scope_location_id": lbrow["scope_location_id"],
            "inheritance_mode": lbrow["inheritance_mode"] or "inherit",
            "sort_order": lbrow["sort_order"] or 0,
            "anchor_entity_id": lbrow["anchor_entity_id"],
            "retired_turn_id": lbrow["retired_turn_id"],
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
    world_events = [
        {"event_id": r["event_id"], "turn_id": r["turn_id"],
         "frame_id": r["frame_id"], "occurred_at": r["occurred_at"],
         "duration_seconds": r["duration_seconds"], "kind": r["kind"],
         "location_id": r["location_id"], "payload": r["payload"],
         "seed": r["seed"], "committed": r["committed"]}
        for r in q("SELECT * FROM world_events WHERE chat_id=?", (chat_id,))
    ]
    # Why a stance is where it is. Snapshotted with the story because it IS
    # the story: a rewind past the argument must take the reason for it too,
    # or a character goes on holding a grudge about a thing that no longer
    # happened.
    relationship_events = [
        {"frame_id": r["frame_id"], "char_id": r["char_id"],
         "target": r["target"], "axis": r["axis"], "delta": r["delta"],
         "triggers": r["triggers"], "note": r["note"],
         "provenance": r["provenance"], "turn_idx": r["turn_idx"],
         "created": r["created"]}
        for r in q("SELECT * FROM relationship_events WHERE chat_id=?",
                   (chat_id,))
    ]
    room_registry = [
        {"room_uid": r["room_uid"], "owning_book_id": r["owning_book_id"],
         "parent_entity": r["parent_entity"], "name": r["name"],
         "aliases": r["aliases"], "payload": r["payload"],
         "created_turn_id": r["created_turn_id"],
         "retired_turn_id": r["retired_turn_id"]}
        for r in q("SELECT * FROM room_registry WHERE chat_id=?", (chat_id,))
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
        # Vectors by content address, not inline: they are 96.9% of a
        # checkpoint and identical in every checkpoint that contains the
        # same memory. The archive export still inlines them, because it
        # is imported into a database with no vector store.
        "memories": dump_chat_memories(chat_id, inline_vectors=False),
        "memory_summaries": dump_memory_summaries(chat_id),
        "lore": lore, "lorebooks": books,
        "lorebook_links": links,
        "world_entities": world_entities,
        "world_placements": world_placements,
        "world_conditions": world_conditions,
        "scheduled_events": scheduled,
        "world_events": world_events,
        "relationship_events": relationship_events,
        "room_registry": room_registry,
        "fiction_worlds": fiction_worlds,
        "fiction_locations": fiction_locations,
    }

def _recreated_book_uid(snapshot_uid):
    """The identity a re-created book comes back with.

    Its own, when the snapshot carried one and nothing else on this install
    has claimed it: a rewind past the turn that minted a book and forward
    again should leave the same resource, and an archive matching it later
    should recognise it.

    A fresh one otherwise, and never NULL. `resource_uid` is UNIQUE where not
    null, so reusing a name some other row now holds would abort the whole
    restore over a bookkeeping field; and leaving it empty hands the row to
    `db.init()`'s `_backfill_resource_uids`, which is a repair pass that
    should have nothing left to repair -- it runs on every open of every
    database precisely because writers kept leaving work for it.
    """
    from story.character_schema import new_uid

    uid = str(snapshot_uid or "").strip()
    if uid and not q("SELECT id FROM lorebooks WHERE resource_uid=?",
                     (uid,), one=True):
        return uid
    return new_uid("book")


def _recreate_snapshot_book(chat_id, snapshot):
    """Re-create a snapshot book this chat no longer has, or decline.

    A restore already DELETES the chat-owned books no snapshot book maps
    onto -- a book minted by a since-discarded timeline must not survive
    into canon. Without the inverse the pair is one-way: rolling back past
    the turn that minted a book and then forward again found nothing to
    match, and the book, its entries, the canon binding and every link
    between those books were gone for good. Rolling all of a chat's books
    away is only the extreme of that, not a separate case.

    Declines when the snapshot's id still names a live row: this chat does
    not own that book (the id-, origin- and name-matching above would have
    claimed it if it did), so it is a library book other chats read, and
    rewriting a shared resource from one chat's checkpoint is not this
    function's business. The re-created book is chat-owned and attached at
    the snapshot's `enabled`, which is also what makes the next restore
    match it by id instead of minting a second copy."""
    old_id = snapshot.get("lorebook_id")
    if old_id is not None and q(
            "SELECT id FROM lorebooks WHERE id=?", (old_id,), one=True):
        return None
    new_id = qi(
        "INSERT INTO lorebooks(chat_id,name,book_type,origin_id,resource_uid) "
        "VALUES(?,?,?,?,?)",
        (chat_id, snapshot.get("name") or "Lorebook",
         snapshot.get("book_type") or "general", snapshot.get("origin_id"),
         _recreated_book_uid(snapshot.get("resource_uid"))),
    )
    qi("INSERT OR IGNORE INTO chat_lorebooks(chat_id,lorebook_id,enabled) "
       "VALUES(?,?,?)",
       (chat_id, new_id, 1 if snapshot.get("enabled", 1) else 0))
    return new_id

def _restore_books(chat_id, books, links=None):
    """Restore lorebook rows/entries from a snapshot. Returns the
    {snapshot book id: current book id} map so the caller can remap other
    snapshot data that embeds book ids (room_registry.owning_book_id)."""
    current_ids = set(chat_lorebook_ids(chat_id, enabled_only=False))
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
            target = _recreate_snapshot_book(chat_id, snapshot)
            if target is None:
                continue
            current[target] = q(
                "SELECT * FROM lorebooks WHERE id=?", (target,), one=True)
        old_id = snapshot.get("lorebook_id")
        if old_id:
            old_to_new[old_id] = target
        row = current[target]
        qi("UPDATE lorebooks SET name=?,book_type=?,summary=?,parent_id=NULL,scope_world_id=?,scope_location_id=?,inheritance_mode=?,sort_order=?,anchor_entity_id=?,retired_turn_id=? WHERE id=?",
           (snapshot.get("name") or row["name"],
            snapshot.get("book_type") or row["book_type"] or "general",
            snapshot.get("summary") if snapshot.get("summary") is not None else (row["summary"] or ""),
            snapshot.get("scope_world_id"),
            snapshot.get("scope_location_id"),
            snapshot.get("inheritance_mode") or "inherit",
            snapshot.get("sort_order") or 0,
            snapshot.get("anchor_entity_id"),
            snapshot.get("retired_turn_id"),
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

    # Links between books represented by this snapshot are snapshot-owned
    # state too. Replace that managed subgraph even when the saved list is
    # empty: otherwise links created by a later, discarded timeline survive,
    # and add_lorebook_link's dedup means saved metadata never replaces an
    # existing row. Links involving books outside the snapshot mapping are
    # deliberately left alone.
    managed_ids = sorted(set(old_to_new.values()))
    if managed_ids:
        placeholders = ",".join("?" * len(managed_ids))
        qi(
            f"DELETE FROM lorebook_links "
            f"WHERE source_book_id IN ({placeholders}) "
            f"AND target_book_id IN ({placeholders})",
            tuple(managed_ids) + tuple(managed_ids),
        )
    restore_lorebook_links(chat_id, old_to_new, links or [])

    return old_to_new

def restore_checkpoint(chat_id, idx):
    r = q("SELECT * FROM checkpoints WHERE chat_id=? AND turn_idx=?", (chat_id, idx), one=True)
    if not r:
        return
    # Consolidation moved out of band (commit.schedule_memory_consolidation),
    # so an in-flight job can now overlap a restore -- and a summary computed
    # from rows this restore is about to roll back must not land afterward.
    # Cooperative and NARROW: only the consolidation job is asked to stop.
    # The offscreen ticks beside it are deliberately left running (a turn
    # starting must never cancel them -- see commit.py's tail), and their
    # writes are provisional at landing, which consolidation's are not.
    try:
        from core import jobs
        from persist.commit import MEMORY_CONSOLIDATION_JOB_KEY
        jobs.cancel(chat_id, MEMORY_CONSOLIDATION_JOB_KEY)
    except Exception:
        pass
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
    """Insert the normalized world-state arrays from blob dict `b` into
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
        qi("DELETE FROM world_events WHERE chat_id=?", (chat_id,))
    for ev in b.get("world_events") or []:
        qi("""INSERT INTO world_events(event_id,chat_id,turn_id,frame_id,
            occurred_at,duration_seconds,kind,location_id,payload,seed,committed)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
           (ev["event_id"], chat_id, ev.get("turn_id"), ev.get("frame_id"),
            ev["occurred_at"], ev.get("duration_seconds", 0.0), ev["kind"],
            ev.get("location_id"), ev.get("payload", "{}"), ev.get("seed"),
            ev.get("committed", time.time())))

    if delete_first:
        qi("DELETE FROM relationship_events WHERE chat_id=?", (chat_id,))
    for re_ in b.get("relationship_events") or []:
        qi("""INSERT INTO relationship_events(chat_id,frame_id,char_id,target,
            axis,delta,triggers,note,provenance,turn_idx,created)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
           (chat_id, re_.get("frame_id"), re_.get("char_id"),
            re_.get("target", ""), re_.get("axis", ""),
            float(re_.get("delta") or 0.0), re_.get("triggers", ""),
            re_.get("note", ""), re_.get("provenance", ""),
            int(re_.get("turn_idx") or 0),
            re_.get("created", time.time())))

    if delete_first:
        qi("DELETE FROM room_registry WHERE chat_id=?", (chat_id,))
    for rr in b.get("room_registry") or []:
        # owning_book_id must reference a live lorebooks row or the FK
        # fails and aborts the whole restore; an unmappable book (deleted
        # since the snapshot, or dropped by an import) degrades to NULL --
        # the row keeps its identity and self-heals owner on next commit.
        book_id = rr.get("owning_book_id")
        if book_id is not None and not q(
                "SELECT 1 FROM lorebooks WHERE id=?", (book_id,), one=True):
            book_id = None
        qi("""INSERT INTO room_registry(chat_id,room_uid,owning_book_id,
            parent_entity,name,aliases,payload,created_turn_id,retired_turn_id)
            VALUES(?,?,?,?,?,?,?,?,?)""",
           (chat_id, rr["room_uid"], book_id, rr.get("parent_entity"),
            rr.get("name", ""), rr.get("aliases", "[]"),
            rr.get("payload", "{}"), rr.get("created_turn_id"),
            rr.get("retired_turn_id")))

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

# World keys that are the READER's settings, not the fiction's state. They
# live in `world` because it is the chat-scoped KV store, but they answer to
# the person at the keyboard rather than to anything that happened in the
# story -- see _preserved_settings.
PRESERVED_SETTING_KEYS = (
    "dialogue_config",     # NPC autonomy, prose pacing, line budgets
    "background_config",   # background life / scene-manager dials
    "style_guide",         # genre, tone, register
    # Author-controlled story language. It changes prompt interpretation,
    # deterministic recognition and compositor rendering, so a reroll must
    # not silently return the story to the language selected beforehand.
    "story_language",
    # `narration_person` WAS on this list and does not belong on it. Every
    # other key here is a dial the reader can reach; that one is DETECTED from
    # how the player writes, and has no endpoint and no control in `static/`.
    # Preserving it meant one misdetection outlived the turn that caused it,
    # the restore meant to undo it, and every reroll after -- the single repair
    # available to the player was the one thing that could not touch it.
    # Observed live: a checkpoint holding "second" restored into a world still
    # holding "first", and the story stayed stuck in the wrong person. It is
    # story state and now rolls back with the story. If it ever gains a UI dial
    # it belongs back here, with a flag separating set-by-hand from detected.
    "paradox_policy",
    # The fixed points themselves, not just the policy for handling them. They
    # are declared and deleted through the UI -- an author's standing
    # constraint on the fiction ("this must exist"), in the same family as the
    # style guide. Rewinding past the turn one was declared on should not
    # quietly retract it; the paradoxes those points DETECT are story state and
    # roll back with everything else.
    "fixed_points",
    # The player's own secret history, edited through the persona lock in the
    # Cast tab. Authoring, not a turn fact -- without this, editing your
    # persona's secrets and then rerolling silently discarded the edit.
    "persona_private_history",
    # "background_presences" is deliberately NOT here. It is diegetic
    # bookkeeping written by every commit (conduct tails, write-once identity
    # blurbs, pending_reply debts, promotion counters) -- preserving it let a
    # DISCARDED run's spoken line stay in the 4-entry conduct tail voiced back
    # to the presence on the rerun, anchored identity to a rerolled beat
    # forever, and carried reply debts into a timeline where the address never
    # happened. It answers to what happened in the story, so it must roll
    # back with the story.
    # Whether this story tracks bodily condition at all. An authoring decision
    # about the fiction, not a fact about turn 40 -- rewinding to turn 12 must
    # not silently switch it off, and branching must not start the branch with
    # it in a different state from the story it came from. The VITALS
    # themselves are diegetic and live in the scene blob, so they correctly
    # roll back with everything else: rewind to before you were starving and
    # you are not starving.
    "survival_enabled",
)


def _preserved_settings(chat_id):
    """The current values of the reader's settings, to carry across a restore.

    restore_state wipes `world` and re-inserts the snapshot, which rolled
    every one of these back to whatever it was when the checkpoint was
    taken. Turn a dial and reroll that same turn and the dial sprang back --
    the checkpoint predates the change, so the change was never in it. The
    settings are not turn-scoped facts; nothing in the fiction depends on
    which pacing you prefer, and a reroll is supposed to re-run the beat,
    not undo your preferences.

    Only keys that currently EXIST are preserved. A fresh chat (branch,
    import) has none, so it still inherits the source's settings from the
    snapshot -- which is the behavior branching wants.

    A key that exists and will not parse is a different case, and it is the
    one this list was built to prevent: the restore falls through to the
    checkpoint's older dial and the reader's own value is gone. Left silent,
    that is indistinguishable from never having turned the dial, so it is
    logged. The restore still proceeds -- an unreadable preference is not a
    reason to refuse a rollback of the story.
    """
    preserved = {}
    for key in PRESERVED_SETTING_KEYS:
        row = q("SELECT value FROM world WHERE chat_id=? AND key=?",
                (chat_id, key), one=True)
        if row is not None:
            try:
                preserved[key] = json.loads(row["value"])
            except (TypeError, ValueError) as exc:
                logger.warning(
                    "checkpoints: chat %s setting %r is unreadable (%s); the "
                    "restore will roll it back to the checkpoint's value",
                    chat_id, key, exc)
    return preserved


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
    # Read before the wipe, written after it: the reader's settings are not
    # part of the beat being rolled back.
    preserved = _preserved_settings(chat_id)
    with transaction():
        qi("DELETE FROM world WHERE chat_id=?", (chat_id,))
        for k, v in (b.get("world") or {}).items():
            wset(chat_id, k, v)
        for k, v in preserved.items():
            wset(chat_id, k, v)
        # P4: membership is diegetic state too. A character AUTO-PROMOTED by
        # the discarded run must not survive as a hollow cast member after its
        # memories, recognition and scene state have rolled back.
        #
        # Two guards, both load-bearing. `"chars" in b` distinguishes a
        # snapshot that recorded an empty cast from a legacy blob that has no
        # chars key at all -- `b.get("chars") or {}` reads the same for both,
        # and on the legacy blob an unguarded sweep deletes the ENTIRE cast.
        # And a row carrying an authored per-story card is skipped: `sheet` is
        # Cast-tab authoring, not a turn fact (CLAUDE.md keeps it separate from
        # `state` for exactly this reason), it is not in the snapshot, and
        # DELETE would destroy it with nothing to restore it from. Note the
        # neighbouring _restore_frames explains at length why this file avoids
        # deleting rows other tables and the author depend on; the same caution
        # applies here.
        if "chars" in b:
            snapshot_char_ids = {
                int(cidk) for cidk in (b.get("chars") or {})
                if str(cidk).lstrip("-").isdigit()
            }
            for row in q(
                "SELECT char_id, sheet FROM chat_chars WHERE chat_id=?",
                (chat_id,),
            ):
                if int(row["char_id"]) in snapshot_char_ids:
                    continue
                if str(row["sheet"] or "").strip():
                    # Left attached deliberately: a visible cast member with
                    # rolled-back state beats silently discarding the card.
                    continue
                qi(
                    "DELETE FROM chat_chars WHERE chat_id=? AND char_id=?",
                    (chat_id, row["char_id"]),
                )
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
        book_map = {}
        if "lorebooks" in b:
            book_map = _restore_books(
                chat_id, b.get("lorebooks") or [], b.get("lorebook_links") or [])

        # room_registry rows embed book ids; a same-chat restore usually
        # maps books onto their original ids, but _restore_books can match
        # a snapshot book onto a differently-numbered current row (by
        # origin/name) -- follow that map so ownership survives.
        if book_map and b.get("room_registry"):
            b = dict(b)
            b["room_registry"] = [
                {**rr, "owning_book_id": book_map.get(
                    rr.get("owning_book_id"), rr.get("owning_book_id"))}
                for rr in b["room_registry"]
            ]

        insert_world_tables(chat_id, b, delete_first=True)

        current_book_ids = set(chat_lorebook_ids(chat_id, enabled_only=False))
        cache = wget(chat_id, "lore_cache", []) or []
        cache = [entry for entry in cache
                 if isinstance(entry, dict) and entry.get("book_id") in current_book_ids]
        seen = set()
        deduplicated = []
        for entry in cache:
            # Same key order as the merge in `agents/mapping.py`, and for the
            # same reason: `id` is the only field two revisions of one entry
            # are guaranteed to share, and a cached dict without `entry_uid`
            # cannot collide with one that has it.
            key = (entry.get("id") or entry.get("entry_uid")
                   or _lore_cache_fingerprint(entry))
            if key in seen:
                continue
            seen.add(key)
            deduplicated.append(entry)
        wset(chat_id, "lore_cache", deduplicated[:24])

    # A restore puts stored vectors back BYTE-IDENTICALLY -- deliberately, so
    # a reroll never re-embeds a whole memory bank and never risks a provider
    # hiccup silently downgrading it to the crc32 fallback. Correct in itself,
    # and it has one consequence nobody chose: a checkpoint taken BEFORE an
    # embedding rebuild carries the old vectors AND the old model key, so
    # restoring it silently UNDOES the rebuild.
    #
    # Measured live: rerolling one turn of a 642-memory story put 637 rows
    # back on `cheap:crc32:256` after a completed rebuild onto a real model.
    # The host saw only the rebuild prompt reappearing; the actual loss was
    # the rebuild itself.
    #
    # Re-embedding inline is the wrong fix -- it is exactly what the verbatim
    # restore exists to avoid, and it would put a provider call on the reroll
    # path. Instead, hand it to the reconciler that already does this work in
    # the background, resumably, and refuses to write a fallback over real
    # vectors. It costs one COUNT when there is nothing to do.
    try:
        from mind.memory import start_rebuild_if_needed
        start_rebuild_if_needed(chat_id)
    except Exception:
        pass    # a maintenance task must never fail a restore
def _lore_cache_fingerprint(entry):
    keys = re.sub(r"\s+", " ", str(entry.get("keys") or "").strip().casefold())
    content = re.sub(r"\s+", " ", str(entry.get("content") or "").strip().casefold())
    digest = hashlib.sha256(f"{keys}\x1f{content}".encode("utf-8")).hexdigest()
    return f"content:{digest}"

def checkpoint_storage_status(chat_id=None):
    """How much of the checkpoint store is still in the legacy inline-vector
    format, for the maintenance panel.

    "Legacy" here means exactly one thing: this checkpoint holds at least one
    entry `compact_checkpoints` would move. It asks with `_movable_entry`, the
    same predicate `_candidate_blob` decides by, because two spellings of one
    question is how the panel and the mover came to disagree in both
    directions -- a store whose first entry was already compacted reported
    done with inline vectors still in it, and a store whose vectors the mover
    refuses reported legacy forever while every run rewrote nothing. The entry
    scan stops at the first movable one, so it costs a single check on a store
    that has anything to convert.

    NOT cheap in the way this docstring used to claim. It selects and
    `json.loads` every checkpoint blob in scope -- on the corpus this module
    was written for (4.4 GB, 94.5% of it checkpoints) that is the whole store,
    and `start_compaction` calls it on every click before deciding whether
    there is anything to do. The claim was written for an implementation that
    read one entry's worth; this one reads all of it. Anyone making this
    cheaper wants a pre-filter that never says "no" to a blob holding an
    inline vector -- the entry scan below is the only thing allowed to answer
    that question.
    """
    where, args = ["1=1"], []
    if chat_id is not None:
        where.append("chat_id=?"); args.append(chat_id)
    clause = " AND ".join(where)
    rows = q("SELECT id, length(blob) sz FROM checkpoints WHERE " + clause, tuple(args))
    total_bytes = sum(r["sz"] or 0 for r in rows)
    legacy = legacy_bytes = 0
    for r in rows:
        blob = q("SELECT blob FROM checkpoints WHERE id=?", (r["id"],), one=True)
        try:
            mems = json.loads(blob["blob"]).get("memories") or []
        except (TypeError, ValueError):
            continue
        if any(_movable_entry(m) is not None for m in mems):
            legacy += 1
            legacy_bytes += r["sz"] or 0
    return {"checkpoints": len(rows), "legacy": legacy,
            "bytes": total_bytes, "legacy_bytes": legacy_bytes}


def _movable_entry(m):
    """The (full, cue) payload the compactor would move, or None.

    BOTH vectors have to decode. The store is addressed by the pair
    (`vector_address`), so an entry carrying half of one has no address to be
    filed under and there is nothing safe to move. Written once, and read by
    the storage panel as well as by the mover, so the answer to "is there
    anything left to convert" cannot depend on who is asking.
    """
    if not isinstance(m, dict) or not m.get("embedding"):
        return None
    full = _b64_to_blob(m.get("embedding"))
    cue = _b64_to_blob(m.get("cue_embedding"))
    if full is None or cue is None:
        return None
    return full, cue


def _candidate_blob(blob):
    """A compacted copy of one checkpoint, plus the vectors it now references.

    Returns (candidate, pending, moved) and mutates nothing: the original dict
    is left exactly as it was so it can be compared against afterwards.
    """
    candidate = json.loads(json.dumps(blob))     # deep copy, cheap enough here
    pending, moved = [], 0
    for m in candidate.get("memories") or []:
        payload = _movable_entry(m)
        if payload is None:
            continue
        full, cue = payload
        vkey = vector_address(full, cue)
        pending.append((vkey, full, cue, m.get("embedding_model"),
                        m.get("embedding_dim")))
        m.pop("embedding", None)
        m.pop("cue_embedding", None)
        m["vkey"] = vkey
        moved += 1
    return candidate, pending, moved


def _verify_no_loss(original, candidate, vectors):
    """Prove the candidate restores to exactly what the original held.

    Not a checksum of the file -- a field-by-field comparison of what a RESTORE
    would produce, because that is the only thing a checkpoint is for. Returns
    a reason string on the first discrepancy, or None when the two are
    equivalent.

    `vectors` is {vkey: (embedding_bytes, cue_bytes)} covering both what is
    already in the store and what this run is about to add, so verification
    asks the same question the restore path will: can every reference be
    resolved, and does it resolve to the same bytes.
    """
    if sorted(original) != sorted(candidate):
        return "top-level keys differ"
    for key in original:
        if key == "memories":
            continue
        if original[key] != candidate[key]:
            return "%s changed" % key
    o_mems = original.get("memories") or []
    c_mems = candidate.get("memories") or []
    if len(o_mems) != len(c_mems):
        return "memory count %d -> %d" % (len(o_mems), len(c_mems))
    for i, (o, c) in enumerate(zip(o_mems, c_mems)):
        if not isinstance(o, dict) or not isinstance(c, dict):
            if o != c:
                return "entry %d is not comparable" % i
            continue
        # Every field except the vectors themselves must survive untouched.
        for key in set(o) | set(c):
            if key in ("embedding", "cue_embedding", "vkey"):
                continue
            if o.get(key) != c.get(key):
                return "entry %d: %s changed" % (i, key)
        o_full, o_cue = _b64_to_blob(o.get("embedding")), _b64_to_blob(o.get("cue_embedding"))
        if o_full is None and o_cue is None:
            # Nothing was there to move; the entry must be unchanged.
            if c.get("vkey") and not o.get("vkey"):
                return "entry %d gained a reference to nothing" % i
            continue
        vkey = c.get("vkey")
        if not vkey:
            return "entry %d lost its vectors without a reference" % i
        got = vectors.get(vkey)
        if got is None:
            return "entry %d references a vector that is not stored" % i
        if got[0] != o_full or got[1] != o_cue:
            return "entry %d resolves to different vector bytes" % i
    return None


def compact_checkpoints(chat_id=None, *, dry_run=True, progress=None):
    """Convert legacy checkpoints to the leaner content-addressed format.

    A checkpoint used to carry every memory's two embedding vectors inline.
    Because a checkpoint is a full pre-turn snapshot of the bank, the same
    vector was re-stored on every turn for the life of the story. Measured on a
    live database: checkpoints were 94.5% of a 4.4 GB file, `memories` was
    98.9% of each checkpoint, and the vectors were 96.9% of that -- one story
    held 40,224 memory copies across 118 checkpoints and 529 distinct by
    content, a 76x duplication of 1.00 GB that needs 13 MB.

    Nothing is re-embedded. A vector is a pure function of the memory's
    content, so this changes where the bytes live, not what they are.

    **LOSS IS NOT ACCEPTED, and that is enforced rather than intended.** The
    work happens per STORY, on a duplicate, and the original is not touched
    until the duplicate has been proved equivalent:

    1. every checkpoint in the story is compacted into an in-memory candidate,
       leaving the stored blob untouched;
    2. each candidate is verified field-by-field against its original --
       including resolving every vector reference back to the exact bytes it
       replaced (`_verify_no_loss`), which is the question a restore will ask;
    3. only if EVERY checkpoint in the story verifies are the vectors and the
       blobs written, in ONE transaction;
    4. if any checkpoint fails, the story is reported by name, its candidates
       are discarded, its original blobs stand untouched, and the run moves on
       to the next story.

    The duplicate is held in memory rather than as a copied chat row: it gives
    the same guarantee -- the original is never mutated until the copy is
    proved -- without duplicating a gigabyte of story to do it, and with no
    half-written copy to clean up if the process dies.

    Resumable: an already-compacted checkpoint has no inline vectors left to
    move and is skipped.
    """
    where, args = ["1=1"], []
    if chat_id is not None:
        where.append("chat_id=?"); args.append(chat_id)
    clause = " AND ".join(where)
    chats = q("SELECT DISTINCT chat_id FROM checkpoints WHERE " + clause, tuple(args))
    total = q("SELECT COUNT(*) n FROM checkpoints WHERE " + clause, tuple(args),
              one=True)["n"]
    # No `error` key. A per-story failure is `skipped` -- named, with its
    # reason, which is the only failure this function has -- and a failure of
    # the RUN raises out of here into `_run_compaction`, which is where
    # `_COMPACT_STATE["error"]` is filled. The key used to sit here
    # initialized to "" and assigned by nothing, so a caller reading it was
    # told "no failure" by a run that had one.
    report = {"checkpoints": total, "rewritten": 0, "vectors_stored": 0,
              "bytes_before": 0, "bytes_after": 0, "stories": len(chats),
              "stories_done": 0, "skipped": [], "dry_run": bool(dry_run)}
    seen = 0
    for row in chats:
        cid = row["chat_id"]
        name = (q("SELECT name FROM chats WHERE id=?", (cid,), one=True)
                or {"name": "chat %s" % cid})["name"]
        cps = q("SELECT id, blob FROM checkpoints WHERE chat_id=? ORDER BY id", (cid,))
        candidates, pending_all, story_before, story_after = [], {}, 0, 0
        reason = None
        for cp in cps:
            raw = cp["blob"]
            story_before += len(raw or "")
            try:
                blob = json.loads(raw)
            except (TypeError, ValueError):
                story_after += len(raw or "")
                continue              # unreadable: left exactly as it is
            candidate, pending, moved = _candidate_blob(blob)
            if not moved:
                story_after += len(raw or "")
                continue
            for vkey, full, cue, model, dim in pending:
                pending_all[vkey] = (full, cue, model, dim)
            text = json.dumps(candidate, ensure_ascii=False)
            story_after += len(text)
            candidates.append((cp["id"], text, blob, candidate))

        if candidates:
            # Everything the verifier may need to resolve: what this run is
            # about to store, plus whatever is already stored.
            resolvable = {k: (v[0], v[1]) for k, v in pending_all.items()}
            for vkey, (full, cue, _m, _d) in get_memory_vectors(
                    [k for _i, _t, _o, c in candidates
                     for m in (c.get("memories") or [])
                     if isinstance(m, dict) and (k := m.get("vkey"))]).items():
                resolvable.setdefault(vkey, (full, cue))
            for _cid_, _text, original, candidate in candidates:
                reason = _verify_no_loss(original, candidate, resolvable)
                if reason:
                    break

        seen += len(cps)
        if reason:
            # The duplicate is discarded and the original stands. Nothing was
            # written for this story, so there is nothing to undo.
            report["skipped"].append(
                {"chat_id": cid, "name": name, "reason": reason})
            logger.warning("checkpoints: cannot compact %r (%s) -- original left "
                           "untouched", name, reason)
            report["bytes_before"] += story_before
            report["bytes_after"] += story_before
        elif candidates and not dry_run:
            with transaction():
                for vkey, (full, cue, model, dim) in pending_all.items():
                    if put_memory_vector(vkey, full, cue, model, dim):
                        report["vectors_stored"] += 1
                for cp_id, text, _o, _c in candidates:
                    qi("UPDATE checkpoints SET blob=? WHERE id=?", (text, cp_id))
            report["rewritten"] += len(candidates)
            report["bytes_before"] += story_before
            report["bytes_after"] += story_after
        else:
            if candidates:
                report["rewritten"] += len(candidates)
                report["vectors_stored"] += len(pending_all)
            report["bytes_before"] += story_before
            report["bytes_after"] += story_after
        report["stories_done"] += 1
        if progress:
            progress(seen, total, report)
    return report


_COMPACT_LOCK = threading.Lock()
_COMPACT_STATE = {"running": False, "done": 0, "total": 0, "rewritten": 0,
                  "bytes_before": 0, "bytes_after": 0, "finished_at": 0.0,
                  "error": "", "skipped": []}


def compaction_progress():
    with _COMPACT_LOCK:
        return dict(_COMPACT_STATE)


def _run_compaction(chat_id=None):
    with _COMPACT_LOCK:
        _COMPACT_STATE.update(running=True, done=0, total=0, rewritten=0,
                              bytes_before=0, bytes_after=0, error="",
                              finished_at=0.0, skipped=[])
    try:
        def _tick(done, total, rep):
            with _COMPACT_LOCK:
                _COMPACT_STATE.update(done=done, total=total,
                                      rewritten=rep["rewritten"],
                                      bytes_before=rep["bytes_before"],
                                      bytes_after=rep["bytes_after"],
                                      skipped=list(rep["skipped"]))
        rep = compact_checkpoints(chat_id, dry_run=False, progress=_tick)
        with _COMPACT_LOCK:
            _COMPACT_STATE.update(skipped=list(rep["skipped"]))
    except Exception as exc:            # never take the server down for this
        logger.warning("checkpoints: compaction failed: %s", exc)
        with _COMPACT_LOCK:
            _COMPACT_STATE.update(error=str(exc))
    finally:
        with _COMPACT_LOCK:
            _COMPACT_STATE.update(running=False, finished_at=time.time())


def start_compaction(chat_id=None):
    """Run the conversion in the background. One at a time.

    Refuses outright when there is no legacy data. A conversion that has
    nothing to convert still walks every checkpoint, parses every blob and
    holds the write lock per story -- expensive work whose only possible
    outcome is "nothing changed" -- and on the rollback path the safest run is
    the one that does not happen. A host who clicks it twice gets told so
    rather than watching a bar for a no-op.
    """
    with _COMPACT_LOCK:
        if _COMPACT_STATE["running"]:
            return {"started": False, "reason": "already running"}
    try:
        status = checkpoint_storage_status(chat_id)
    except Exception as exc:
        return {"started": False, "reason": "could not check: %s" % exc}
    if not status["checkpoints"]:
        return {"started": False, "reason": "no checkpoints stored",
                **status}
    if not status["legacy"]:
        return {"started": False, "reason": "nothing to convert",
                **status}
    threading.Thread(target=_run_compaction, args=(chat_id,),
                     daemon=True).start()
    return {"started": True, **status}


def ensure_checkpoint(chat_id, turn_idx, blob=None):
    """Ensure a checkpoint exists for the given turn index.

    Captures the current world/character/lore state so it can be
    restored if the turn is deleted or re-run.

    `blob` lets a caller that must run inside a transaction (the turn-creation
    route) hand in a snapshot it serialized BEFORE taking the write lock,
    instead of paying for the full snapshot while holding it. The caller owns
    the staleness question: pass a blob only when nothing that belongs in the
    checkpoint can have changed since it was built (app.py re-checks the
    latest turn id under the lock and rebuilds on a race).
    """
    # Cheap existence check FIRST. This runs twice for the same turn -- once
    # from the route (app.py) and once from the pipeline (agents/runtime.py) --
    # and building the blob before looking meant the second call assembled the
    # entire snapshot (every world KV, all chat_chars, all lorebooks and
    # entries, every memory and summary -- about half a megabyte on a long
    # chat) and then threw it away. An unindexed read outside the lock is the
    # right way to answer "is this already done".
    #
    # It is a fast path, not the guard: the authoritative check is still inside
    # the transaction below, because two concurrent callers can both pass this
    # one.
    existing = q(
        "SELECT id FROM checkpoints WHERE chat_id=? AND turn_idx=?",
        (chat_id, turn_idx),
        one=True,
    )
    if existing:
        return existing["id"]
    # Snapshot outside the transaction: snapshot_state makes many
    # read-only q() calls and does no writes, so it needs no lock.
    # Holding the write lock for the duration of a snapshot would
    # needlessly block other writers.
    if blob is None:
        blob = json.dumps(snapshot_state(chat_id))
    # Check-then-insert inside a transaction so two concurrent calls
    # for the same (chat_id, turn_idx) can't both pass the existence
    # check and race on the UNIQUE(chat_id, turn_idx) insert.
    with transaction():
        existing = q(
            "SELECT id FROM checkpoints WHERE chat_id=? AND turn_idx=?",
            (chat_id, turn_idx),
            one=True,
        )
        if existing:
            return existing["id"]
        return qi(
            "INSERT INTO checkpoints(chat_id, turn_idx, blob, created) "
            "VALUES(?,?,?,?)",
            (chat_id, turn_idx, blob, time.time()),
        )


def propagate_memory_summaries_to_checkpoints(chat_id, char_id=None):
    """Carry reconstructed legacy summary windows into saved pre-turn state.

    Backfill derives prose from memories that already existed in the old
    timeline. A later checkpoint restore must not erase that repair. Only a
    window that closed strictly before a checkpoint's turn is eligible, which
    preserves the same temporal firewall used by the live read seam. Existing
    snapshot rows win; this helper adds missing derived windows and mutates no
    other checkpoint state.
    """
    summaries = dump_memory_summaries(chat_id)
    if char_id is not None:
        summaries = [s for s in summaries if s.get("char_id") == char_id]
    if not summaries:
        return 0
    changed = 0
    candidates = []
    for row in q("SELECT id, turn_idx, blob FROM checkpoints WHERE chat_id=? "
                 "ORDER BY turn_idx, id", (chat_id,)):
        try:
            blob = json.loads(row["blob"])
        except Exception:
            logger.warning("checkpoint %s has invalid JSON; summary propagation skipped",
                           row["id"])
            continue
        existing = blob.get("memory_summaries") or []
        keys = {
            (s.get("char_id"), s.get("scope", "autobiographical"),
             int(s.get("end_turn_idx") or 0))
            for s in existing if isinstance(s, dict)
        }
        additions = []
        for summary in summaries:
            end = int(summary.get("end_turn_idx") or 0)
            key = (summary.get("char_id"),
                   summary.get("scope", "autobiographical"), end)
            if end < int(row["turn_idx"]) and key not in keys:
                additions.append(summary)
                keys.add(key)
        if additions:
            blob["memory_summaries"] = sorted(
                [*existing, *additions],
                key=lambda s: (s.get("char_id") or 0,
                               s.get("scope") or "",
                               int(s.get("end_turn_idx") or 0)))
            candidates.append((row["id"], json.dumps(blob)))
    if candidates:
        with transaction():
            for checkpoint_id, blob_text in candidates:
                qi("UPDATE checkpoints SET blob=? WHERE id=?",
                   (blob_text, checkpoint_id))
                changed += 1
    return changed

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
    # Snapshot outside the transaction: snapshot_state is read-only and
    # may take time; holding the write lock for its duration would
    # needlessly block other writers.
    fresh = snapshot_state(chat_id)
    # Read-modify-write inside a transaction so a concurrent
    # ensure_checkpoint or refresh_checkpoint can't interleave.
    with transaction():
        row = q(
            "SELECT blob FROM checkpoints WHERE chat_id=? AND turn_idx=?",
            (chat_id, turn_idx),
            one=True,
        )
        if not row:
            # No pre-turn checkpoint captured yet -- fall back to a full
            # snapshot (nothing to preserve).  The insert is already
            # inside this transaction; delegate to ensure_checkpoint
            # would nest a second transaction (savepoint) and re-snapshot,
            # so do the insert directly here instead.
            return qi(
                "INSERT INTO checkpoints(chat_id, turn_idx, blob, created) "
                "VALUES(?,?,?,?)",
                (chat_id, turn_idx, json.dumps(fresh), time.time()),
            )
        blob = json.loads(row["blob"])
        for key in ("lore", "lorebooks", "lorebook_links"):
            blob[key] = fresh.get(key)
        qi(
            "UPDATE checkpoints SET blob=?, created=? WHERE chat_id=? AND turn_idx=?",
            (json.dumps(blob), time.time(), chat_id, turn_idx),
        )
