"""The lorebook GRAPH: hierarchy, links, inheritance, per-chat attachment.

Books, not entries. What a book contains is `mind/memory_lore_entries.py`."""

import time
from collections import defaultdict
from core.db import q, qi, transaction
from core.logging_utils import logger

from mind.memory_common import LOREBOOK_LINK_TYPES

# ---- Hierarchical Lorebook Functions ----

def lorebook_descendants(root_id):
    rows = q(
        """WITH RECURSIVE tree(id) AS (
            SELECT id FROM lorebooks WHERE id=?
            UNION ALL
            SELECT child.id FROM lorebooks child JOIN tree parent ON child.parent_id=parent.id
        ) SELECT id FROM tree""",
        (root_id,),
    )
    return [row["id"] for row in rows]

def would_create_book_cycle(book_id, parent_id):
    if parent_id is None:
        return False

    if book_id == parent_id:
        return True

    current = parent_id
    visited = set()

    while current is not None:
        if current == book_id:
            return True

        if current in visited:
            return True

        visited.add(current)

        row = q(
            "SELECT parent_id FROM lorebooks WHERE id=?",
            (current,),
            one=True,
        )
        current = row["parent_id"] if row else None

    return False

def move_lorebook(book_id, parent_id, position=None):
    if would_create_book_cycle(book_id, parent_id):
        raise ValueError("Cannot move lorebook: would create a cycle")
    
    book = q("SELECT chat_id FROM lorebooks WHERE id=?", (book_id,), one=True)
    if not book:
        raise ValueError("Lorebook not found")
    chat_id = book["chat_id"]
    
    if parent_id is not None:
        parent = q("SELECT chat_id FROM lorebooks WHERE id=?", (parent_id,), one=True)
        if not parent:
            raise ValueError("Parent lorebook not found")
        if chat_id != parent["chat_id"]:
            raise ValueError("Cannot parent a lorebook to one in a different chat scope")
    
    with transaction():
        qi("UPDATE lorebooks SET parent_id=? WHERE id=?", (parent_id, book_id))
        
        if position is not None and parent_id is not None:
            siblings = q(
                "SELECT id FROM lorebooks WHERE parent_id=? AND id!=? ORDER BY sort_order, id",
                (parent_id, book_id),
            )
            siblings = [r["id"] for r in siblings]
            siblings.insert(max(0, min(position, len(siblings))), book_id)
            for idx, sid in enumerate(siblings):
                qi("UPDATE lorebooks SET sort_order=? WHERE id=?", (idx, sid))
        elif position is not None and parent_id is None:
            roots = q(
                "SELECT id FROM lorebooks WHERE parent_id IS NULL AND id!=? AND chat_id IS ? ORDER BY sort_order, id",
                (book_id, chat_id),
            )
            roots = [r["id"] for r in roots]
            roots.insert(max(0, min(position, len(roots))), book_id)
            for idx, rid in enumerate(roots):
                qi("UPDATE lorebooks SET sort_order=? WHERE id=?", (idx, rid))

def reorder_lorebook(book_id, direction="up"):
    book = q("SELECT parent_id, sort_order, chat_id FROM lorebooks WHERE id=?", (book_id,), one=True)
    if not book:
        raise ValueError("Lorebook not found")

    parent_id = book["parent_id"]
    sort_order = book["sort_order"]
    # Scope the swap partner to the same chat (mirrors move_lorebook's root
    # branch): without this, a root book (parent_id NULL) could swap
    # sort_order with a root book of a DIFFERENT chat or a global book.
    chat_id = book["chat_id"]

    if direction == "up":
        prev = q(
            "SELECT id FROM lorebooks WHERE parent_id IS ? AND chat_id IS ? AND sort_order < ? ORDER BY sort_order DESC LIMIT 1",
            (parent_id, chat_id, sort_order),
            one=True,
        )
        if prev:
            qi("UPDATE lorebooks SET sort_order=? WHERE id=?", (sort_order, prev["id"]))
            qi("UPDATE lorebooks SET sort_order=? WHERE id=?", (sort_order - 1, book_id))
    elif direction == "down":
        nxt = q(
            "SELECT id FROM lorebooks WHERE parent_id IS ? AND chat_id IS ? AND sort_order > ? ORDER BY sort_order ASC LIMIT 1",
            (parent_id, chat_id, sort_order),
            one=True,
        )
        if nxt:
            qi("UPDATE lorebooks SET sort_order=? WHERE id=?", (sort_order, nxt["id"]))
            qi("UPDATE lorebooks SET sort_order=? WHERE id=?", (sort_order + 1, book_id))

# ---- Lorebook Links ----


def add_lorebook_link(source_book_id, target_book_id, relation_type="related", **kwargs):
    if source_book_id == target_book_id:
        raise ValueError("Cannot link a lorebook to itself")
    if relation_type not in LOREBOOK_LINK_TYPES:
        relation_type = "related"

    source = q("SELECT chat_id FROM lorebooks WHERE id=?", (source_book_id,), one=True)
    target = q("SELECT chat_id FROM lorebooks WHERE id=?", (target_book_id,), one=True)

    if not source or not target:
        raise ValueError("Lorebook not found")

    if source["chat_id"] != target["chat_id"]:
        raise ValueError(
            "Lorebook links cannot cross ownership scopes "
            f"(source chat_id={source['chat_id']}, "
            f"target chat_id={target['chat_id']})"
        )

    existing = q(
        "SELECT id FROM lorebook_links WHERE source_book_id=? AND target_book_id=? AND relation_type=?",
        (source_book_id, target_book_id, relation_type),
        one=True,
    )
    if existing:
        return existing["id"]

    return qi(
        """INSERT INTO lorebook_links(
            source_book_id, target_book_id, relation_type, label, notes,
            bidirectional, follow_for_retrieval, weight, sort_order, created
        ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (
            source_book_id, target_book_id, relation_type,
            kwargs.get("label", ""),
            kwargs.get("notes", ""),
            int(bool(kwargs.get("bidirectional", True))),
            int(bool(kwargs.get("follow_for_retrieval", True))),
            float(kwargs.get("weight", 0.75)),
            int(kwargs.get("sort_order", 0)),
            time.time(),
        ),
    )

def update_lorebook_link(link_id, **kwargs):
    fields = []
    values = []
    for key in ("relation_type", "label", "notes", "bidirectional", "follow_for_retrieval", "weight", "sort_order"):
        if key in kwargs:
            fields.append(f"{key}=?")
            val = kwargs[key]
            if key in ("bidirectional", "follow_for_retrieval"):
                val = int(bool(val))
            elif key == "weight":
                val = float(val)
            values.append(val)
    if not fields:
        return False
    values.append(link_id)
    qi(f"UPDATE lorebook_links SET {','.join(fields)} WHERE id=?", tuple(values))
    return True

def delete_lorebook_link(link_id):
    qi("DELETE FROM lorebook_links WHERE id=?", (link_id,))

def get_lorebook_links(book_id):
    rows = q(
        """SELECT * FROM lorebook_links 
        WHERE source_book_id=? OR target_book_id=? 
        ORDER BY sort_order, id""",
        (book_id, book_id),
    )
    return [dict(r) for r in rows]

# ---- Lorebook Graph Resolution ----


def _inheriting_ancestors(book_id):
    """Walk up from book_id, one hop at a time, stopping the moment a
    book's OWN inheritance_mode isn't 'inherit' -- that book's edge to
    its parent is severed, so nothing further up should be pulled in on
    its behalf. lorebook_ancestors() (used pre-fix) returned the full
    chain unconditionally, which is what made inheritance_mode a column
    that was stored, edited, and copied everywhere but never actually
    consulted at read time -- 'isolated' behaved identically to 'inherit'.
    """
    out = []
    current_id = book_id
    while True:
        row = q(
            "SELECT parent_id, inheritance_mode FROM lorebooks WHERE id=?",
            (current_id,), one=True,
        )
        if not row or row["parent_id"] is None:
            break
        if (row["inheritance_mode"] or "inherit") != "inherit":
            break
        out.append(row["parent_id"])
        current_id = row["parent_id"]
    return out

def resolve_lorebook_graph(
    root_ids,
    *,
    chat_id=None,
    include_descendants=True,
    include_ancestors=True,
    follow_links=True,
    max_link_depth=2,
):
    def _owned(book_id):
        if book_id is None:
            return False
        row = q("SELECT chat_id FROM lorebooks WHERE id=?", (book_id,), one=True)
        if not row:
            return False
        if chat_id is None:
            return row["chat_id"] is None
        return row["chat_id"] == chat_id

    root_ids = [rid for rid in root_ids if _owned(rid)]
    visited = {}
    queue = [(rid, 0, 1.0, "attached") for rid in root_ids]

    while queue:
        book_id, depth, weight, reason = queue.pop(0)
        if book_id in visited:
            if visited[book_id]["weight"] >= weight:
                continue
        visited[book_id] = {"depth": depth, "weight": weight, "reason": reason}

        if depth >= max_link_depth + 2:
            continue

        if include_descendants:
            children = q(
                "SELECT id, inheritance_mode FROM lorebooks WHERE parent_id=? ORDER BY sort_order",
                (book_id,),
            )
            for r in children:
                if not _owned(r["id"]):
                    continue
                mode = r["inheritance_mode"] or "inherit"
                if mode == "isolated":
                    # Never surfaced through the parent at all -- a chat
                    # must attach it directly to see it.
                    continue
                child_weight = weight * (0.5 if mode == "reference_only" else 0.95)
                queue.append((r["id"], depth + 1, child_weight, "child" if mode == "inherit" else f"child:{mode}"))

        if include_ancestors and depth == 0:
            for aid in _inheriting_ancestors(book_id):
                if _owned(aid):
                    queue.append((aid, -1, weight * 0.9, "ancestor"))

        if follow_links and depth < max_link_depth:
            links = q(
                """SELECT target_book_id, relation_type, weight, bidirectional, follow_for_retrieval
                FROM lorebook_links
                WHERE source_book_id=? AND follow_for_retrieval=1""",
                (book_id,),
            )
            for r in links:
                if _owned(r["target_book_id"]):
                    queue.append((r["target_book_id"], depth + 1, weight * r["weight"], f"linked:{r['relation_type']}"))
            if depth == 0:
                back_links = q(
                    """SELECT source_book_id, relation_type, weight, bidirectional, follow_for_retrieval
                    FROM lorebook_links
                    WHERE target_book_id=? AND bidirectional=1 AND follow_for_retrieval=1""",
                    (book_id,),
                )
                for r in back_links:
                    if _owned(r["source_book_id"]):
                        queue.append((r["source_book_id"], depth + 1, weight * r["weight"], f"linked:{r['relation_type']}"))

    return [{"id": k, **v} for k, v in visited.items()]

# ---- Chat lorebook attachment resolution ----

def _chat_lorebook_root_ids(chat_id, enabled_only=True):
    root_ids = []
    chat = q("SELECT lorebook_id FROM chats WHERE id=?", (chat_id,), one=True)
    if chat and chat["lorebook_id"]:
        root_ids.append(chat["lorebook_id"])
    sql = "SELECT lorebook_id FROM chat_lorebooks WHERE chat_id=?"
    if enabled_only:
        sql += " AND enabled=1"
    for row in q(sql, (chat_id,)):
        if row["lorebook_id"] not in root_ids:
            root_ids.append(row["lorebook_id"])
    return root_ids

def chat_lorebook_ids(chat_id, enabled_only=True):
    resolved = resolve_lorebook_graph(
        _chat_lorebook_root_ids(chat_id, enabled_only),
        chat_id=chat_id,
        include_descendants=True,
        include_ancestors=True,
        follow_links=True,
        max_link_depth=2,
    )
    return [r["id"] for r in resolved]

def chat_lorebook_weights(chat_id, enabled_only=True):
    """Same resolution as chat_lorebook_ids, but keeping the per-book
    weight resolve_lorebook_graph already computes (attached=1.0, decayed
    per hop through children/ancestors/links, and now also per
    inheritance_mode) instead of discarding it down to a flat id list --
    for callers (search_lore) that want a distant ancestor's entries to
    rank below the chat's actually-attached books, not compete with them
    as equals.
    """
    resolved = resolve_lorebook_graph(
        _chat_lorebook_root_ids(chat_id, enabled_only),
        chat_id=chat_id,
        include_descendants=True,
        include_ancestors=True,
        follow_links=True,
        max_link_depth=2,
    )
    return {r["id"]: r["weight"] for r in resolved}

def lorebook_manifest(chat_id):
    chat = q("SELECT lorebook_id FROM chats WHERE id=?", (chat_id,), one=True)
    canon = chat["lorebook_id"] if chat else None
    attached_ids = set()
    
    all_ids = set()
    root_ids = []
    if chat and chat["lorebook_id"]:
        root_ids.append(chat["lorebook_id"])
    for r in q("SELECT lorebook_id FROM chat_lorebooks WHERE chat_id=?", (chat_id,)):
        root_ids.append(r["lorebook_id"])
    
    resolved = resolve_lorebook_graph(root_ids, chat_id=chat_id)
    all_ids = {r["id"] for r in resolved}
    
    for rid in root_ids:
        attached_ids.add(rid)
    
    books = []
    for lid in sorted(all_ids):
        lb = q("""SELECT id,parent_id,name,book_type,summary,scope_world_id,
                  scope_location_id,inheritance_mode,sort_order,anchor_entity_id
                  FROM lorebooks WHERE id=?""", (lid,), one=True)
        if not lb: continue
        n = q("SELECT COUNT(*) c FROM lore_entries WHERE lorebook_id=?", (lid,), one=True)["c"]
        att = q("SELECT enabled FROM chat_lorebooks WHERE chat_id=? AND lorebook_id=?", (chat_id, lid), one=True)
        books.append({
            "id": lid, "parent_id": lb["parent_id"], "name": lb["name"],
            "type": lb["book_type"] or "general", "summary": lb["summary"] or "",
            "scope_world_id": lb["scope_world_id"],
            "scope_location_id": lb["scope_location_id"],
            "inheritance_mode": lb["inheritance_mode"] or "inherit",
            "sort_order": lb["sort_order"],
            "anchor_entity_id": lb["anchor_entity_id"],
            "entry_count": n, "canon": lid == canon,
            "attached": lid in attached_ids,
            "enabled": bool(att["enabled"]) if att else True,
        })
    
    links = []
    if all_ids:
        ph = ",".join("?" * len(all_ids))
        rows = q(
            f"""SELECT * FROM lorebook_links 
            WHERE source_book_id IN ({ph}) OR target_book_id IN ({ph})""",
            tuple(all_ids) + tuple(all_ids),
        )
        for r in rows:
            links.append({
                "id": r["id"],
                "source_book_id": r["source_book_id"],
                "target_book_id": r["target_book_id"],
                "relation_type": r["relation_type"],
                "label": r["label"],
                "notes": r["notes"],
                "bidirectional": bool(r["bidirectional"]),
                "follow_for_retrieval": bool(r["follow_for_retrieval"]),
                "weight": r["weight"],
            })
    
    return {
        "books": books,
        "links": links,
        "roots": root_ids,
    }

def monitoring_subtree(chat_id, book_id, scene=None, max_depth=6):
    """Read-only "what's aboard/nested here right now" walk for one
    location/vehicle book (movement/space Phase 1, item 5).

    Two edge kinds, kept distinct on purpose:
    - parent_id children = canonical containment ("belongs to": crew logs,
      cabin books) -- reported under 'children';
    - inbound 'currently_within' links = live presence ("is at right now":
      a docked vehicle's book, rewritten from positions at every commit by
      commit.sync_anchored_books) -- reported under 'present', recursively,
      so a van aboard a ferry docked at the port nests three deep.

    When a scene dict is supplied, each anchored book is joined against it:
    'rooms' = the anchor entity's interior rooms (rooms whose parent_entity
    is the anchor), 'occupants' = every positions entry currently inside
    one of them.

    Monitoring/reporting ONLY (UI, ops, tests): this walk reads the
    lorebook graph and must never feed perception -- what an observer
    aboard perceives is scoped by the spatial layer (spatial.ambient_scope
    on scene containment), never by these links.
    """
    def _node(bid, depth, seen):
        row = q(
            "SELECT id, name, book_type, parent_id, anchor_entity_id "
            "FROM lorebooks WHERE id=?",
            (bid,), one=True,
        )
        if not row:
            return None
        node = {
            "id": row["id"], "name": row["name"],
            "book_type": row["book_type"],
            "anchor_entity_id": row["anchor_entity_id"],
            "rooms": [], "occupants": [],
            "children": [], "present": [],
        }
        anchor = row["anchor_entity_id"]
        if scene and anchor:
            interior = sorted(
                rid for rid, room in (scene.get("rooms") or {}).items()
                if isinstance(room, dict)
                and room.get("parent_entity") == anchor
            )
            node["rooms"] = interior
            interior_set = set(interior)
            node["occupants"] = sorted(
                str(name)
                for name, room in (scene.get("positions") or {}).items()
                if room in interior_set and str(name) != anchor
            )
        if depth >= max_depth:
            return node
        for child in q(
            "SELECT id FROM lorebooks WHERE parent_id=? AND chat_id IS ? "
            "ORDER BY sort_order, id",
            (bid, chat_id),
        ):
            if child["id"] in seen:
                continue
            sub = _node(child["id"], depth + 1, seen | {child["id"]})
            if sub:
                node["children"].append(sub)
        for link in q(
            "SELECT source_book_id FROM lorebook_links "
            "WHERE target_book_id=? AND relation_type='currently_within' "
            "ORDER BY sort_order, id",
            (bid,),
        ):
            if link["source_book_id"] in seen:
                continue
            sub = _node(link["source_book_id"], depth + 1,
                        seen | {link["source_book_id"]})
            if sub:
                node["present"].append(sub)
        return node

    return _node(book_id, 0, {book_id})

# ---- Lorebook link snapshot helpers ----

def dump_lorebook_links(book_ids):
    if not book_ids:
        return []
    ph = ",".join("?" * len(book_ids))
    rows = q(
        f"""SELECT * FROM lorebook_links
        WHERE source_book_id IN ({ph})
          AND target_book_id IN ({ph})""",
        tuple(book_ids) + tuple(book_ids),
    )
    return [dict(r) for r in rows]


def restore_lorebook_links(chat_id, old_to_new, links):
    """Put a chat's lorebook link graph back, and SAY what did not go back.

    Every way this can fail was silent. Four `continue`s drop a link whose
    books the id map never learned, whose endpoints collapsed onto one book, or
    whose endpoints now sit outside this chat; a bare `except Exception: pass`
    swallowed the insert itself. A restore that puts back half the graph and
    returns None is indistinguishable from one that put back all of it -- and
    the loss is not visible in the chat either, because a missing link is a
    retrieval edge that stops being followed, not an error anybody sees.

    Returns `{"restored": int, "dropped": int, "reasons": {...}}` and warns
    when anything was dropped. Restoration itself is unchanged: a link that
    cannot be put back is still skipped rather than allowed to take the rest
    of the graph down with it.
    """
    restored = 0
    reasons = defaultdict(int)

    for link in links or []:
        source = old_to_new.get(link.get("source_book_id"))
        target = old_to_new.get(link.get("target_book_id"))

        if source is None or target is None:
            reasons["book_not_in_id_map"] += 1
            continue
        if source == target:
            reasons["endpoints_merged"] += 1
            continue

        source_row = q("SELECT chat_id FROM lorebooks WHERE id=?", (source,), one=True)
        target_row = q("SELECT chat_id FROM lorebooks WHERE id=?", (target,), one=True)

        if not source_row or not target_row:
            reasons["book_missing"] += 1
            continue
        if source_row["chat_id"] != chat_id or target_row["chat_id"] != chat_id:
            reasons["book_outside_this_chat"] += 1
            continue

        try:
            add_lorebook_link(
                source, target, link.get("relation_type", "related"),
                label=link.get("label", ""),
                notes=link.get("notes", ""),
                bidirectional=link.get("bidirectional", True),
                follow_for_retrieval=link.get("follow_for_retrieval", True),
                weight=link.get("weight", 0.75),
                sort_order=link.get("sort_order", 0),
            )
        except Exception as exc:
            reasons["insert_failed"] += 1
            logger.warning(
                "memory: lorebook link %s->%s not restored for chat %s: %s",
                source, target, chat_id, exc)
            continue
        restored += 1

    dropped = sum(reasons.values())
    if dropped:
        logger.warning(
            "memory: restored %d of %d lorebook links for chat %s (%s)",
            restored, restored + dropped, chat_id,
            ", ".join(f"{name}={count}"
                      for name, count in sorted(reasons.items())))
    return {"restored": restored, "dropped": dropped, "reasons": dict(reasons)}

