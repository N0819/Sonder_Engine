"""Memory system with hierarchical lorebook support and expanded categories."""

import base64
import hashlib
import json, re, threading, time, math
import numpy as np
from collections import defaultdict
from db import q, qi, wget, wset, transaction
from providers import embed_texts, embed_texts_meta, chat_complete
from prompts import get_prompt
from dataclasses import dataclass, field, asdict
from typing import Optional
import frames as _frames
from logging_utils import logger
from theory_of_mind import belief_credence
from db import active_frame_id as _active_frame_id

_UNSET = object()

LORE_CATEGORIES = [
    "location", "layout", "event", "mechanic", "myth",
    "character", "faction", "species", "culture", "technology",
    "knowledge", "other",
]

LOREBOOK_TYPES = [
    "general", "world", "knowledge", "location", "system",
    "characters", "events", "vehicle",
]

LOREBOOK_LINK_TYPES = [
    "related",
    "references",
    "depends_on",
    "supplements",
    "overlaps",
    "supersedes",
    "contradicts",
    "alternate_version",
    "same_setting",
    "portal",
    # "is at right now": a mobile (anchored) book's live presence link to
    # the book of wherever its anchor entity currently is, rewritten from
    # scene positions at every commit (commit.sync_anchored_books).
    # Distinct from parent_id, which is canonical "belongs to" and is
    # never mutated by commit. Retrieval follows it so docked-location
    # lore stays reachable; it is NEVER perception authorization.
    "currently_within",
]

KNOWLEDGE_TAGS = ["common", "scholarly", "esoteric"]
KNOWLEDGE_RANGES = ["local", "global"]

LORE_INHERITANCE_MODES = ["inherit", "isolated", "reference_only"]

MEMORY_CATEGORIES = [
    "episode", "dialogue", "promise", "relationship",
    "person", "place", "semantic", "intention",
    "emotion", "self", "inference",
]

MEMORY_PROVENANCE = [
    "witnessed", "heard", "told", "read",
    "inferred", "remembered",
]

# P8: which rolling summary a memory folds into.
#
# Consolidation used to melt every provenance into ONE autobiographical string
# that was then fed back wholesale each turn -- so the distinction this engine's
# thesis rests on, between what a character SAW, what they were TOLD, and what
# they GUESSED, did not survive the summary layer. A belief they inferred came
# back a few turns later indistinguishable from something they had witnessed,
# which is belief laundering into knowledge inside a single mind.
#
# Three scopes rather than a provenance tag per sentence, because the summary is
# prose written by a model and a tag inside prose is a convention it can drop.
# A separate row cannot be dropped. `memory_summaries` is already keyed
# (chat_id, char_id, scope) and every dump/restore/archive path iterates rows
# generically, so this needs no migration and rides existing round-trips.
SUMMARY_SCOPE_FIRSTHAND = "autobiographical"
SUMMARY_SCOPE_HEARSAY = "hearsay"
SUMMARY_SCOPE_SURMISE = "surmise"

_PROVENANCE_SCOPE = {
    "witnessed": SUMMARY_SCOPE_FIRSTHAND,
    "remembered": SUMMARY_SCOPE_FIRSTHAND,
    "heard": SUMMARY_SCOPE_HEARSAY,
    "told": SUMMARY_SCOPE_HEARSAY,
    "read": SUMMARY_SCOPE_HEARSAY,
    "inferred": SUMMARY_SCOPE_SURMISE,
}

# Keyed by scope: the model field carrying it, and how the character's own
# context labels it back to them.
_SUMMARY_SCOPES = (
    (SUMMARY_SCOPE_FIRSTHAND, "summary", "what_i_experienced"),
    (SUMMARY_SCOPE_HEARSAY, "hearsay_summary", "what_i_was_told"),
    (SUMMARY_SCOPE_SURMISE, "surmise_summary", "what_i_concluded"),
)


def summary_scope_for(provenance):
    return _PROVENANCE_SCOPE.get(
        str(provenance or "").strip().casefold(), SUMMARY_SCOPE_FIRSTHAND)

def _blob(v): return np.asarray(v, dtype=np.float32).tobytes()
def _vec(b):  return np.frombuffer(b, dtype=np.float32) if b else None

def _blob_to_b64(b):
    """Raw embedding BLOB -> JSON-safe base64 string (None if absent).

    Snapshot/export dumps are stored as JSON, so raw bytes must be
    encoded. The round trip through base64 is byte-identical, which is
    what lets checkpoint restore put embeddings back verbatim instead
    of re-embedding (and risking a silent crc32-fallback downgrade)."""
    if not b:
        return None
    return base64.b64encode(bytes(b)).decode("ascii")

def _b64_to_blob(s):
    """Inverse of _blob_to_b64; returns None on anything malformed so
    callers fall back to re-embedding rather than storing garbage."""
    if not s or not isinstance(s, str):
        return None
    try:
        raw = base64.b64decode(s, validate=True)
    except Exception:
        return None
    # Stored vectors are float32 arrays; anything that can't be one is
    # not a usable embedding.
    if not raw or len(raw) % 4 != 0:
        return None
    return raw
def _storage_json(value):
    if value is None or isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)

def _ids(lorebook_ids):
    if lorebook_ids is None: return []
    if isinstance(lorebook_ids, int): return [lorebook_ids]
    out = []
    for i in lorebook_ids:
        if i and i not in out: out.append(i)
    return out

def _fts_query(text):
    toks = re.findall(r"[A-Za-z0-9]{3,}", text or "")[:12]
    return " OR ".join(f'"{t}"' for t in toks) if toks else None

def _kw_scores(fts_table, query, limit=50):
    fq = _fts_query(query)
    if not fq: return {}
    try:
        rows = q(f"SELECT rowid FROM {fts_table} WHERE {fts_table} MATCH ? ORDER BY rank LIMIT ?", (fq, limit))
        return {r["rowid"]: 1.0 - i / max(len(rows), 1) for i, r in enumerate(rows)}
    except Exception:
        return {}

def _cos(a, b):
    if a is None or b is None or len(a) != len(b): return 0.0
    return float(np.dot(a, b) / ((np.linalg.norm(a) * np.linalg.norm(b)) + 1e-8))

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

# ---- Memory normalization and storage helpers ----

_STOPWORDS = {
    "about", "after", "again", "against", "because", "before", "being",
    "could", "does", "from", "have", "into", "itself", "might", "other",
    "should", "something", "their", "there", "these", "they", "this",
    "through", "under", "what", "when", "where", "which", "while", "with",
    "would", "your", "said", "says", "then", "that", "were", "been",
}

_OLD_CUES = (
    r"\blong ago\b", r"\byears? ago\b", r"\bmonths? ago\b",
    r"\bback then\b", r"\bearliest\b", r"\bfirst time\b", r"\boriginally\b",
)
_RECENT_CUES = (
    r"\brecently\b", r"\bjust now\b", r"\ba moment ago\b",
    r"\blast turn\b", r"\bjust happened\b",
)

def _json_list(value) -> list:
    if isinstance(value, list):
        return value
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []

def _clamp(value, lo=0.0, hi=1.0):
    try:
        return max(lo, min(hi, float(value)))
    except Exception:
        return lo

def _clamp_signed(value, lo=-1.0, hi=1.0):
    try:
        return max(lo, min(hi, float(value)))
    except Exception:
        return 0.0

def _turn_idx_for(turn_id):
    if turn_id is None:
        return None
    row = q("SELECT idx FROM turns WHERE id=?", (turn_id,), one=True)
    return row["idx"] if row else None

def _default_category(kind: str) -> str:
    mapping = {
        "episodic": "episode", "episode": "episode",
        "dialogue": "dialogue", "inference": "inference",
        "semantic": "semantic", "relationship": "relationship",
        "promise": "promise", "intention": "intention",
    }
    return mapping.get(str(kind or "").lower(), "episode")

def _gist(text: str, limit: int = 240) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(text) <= limit:
        return text
    parts = re.split(r"(?<=[.!?])\s+", text)
    out = ""
    for part in parts:
        candidate = (out + " " + part).strip()
        if len(candidate) > limit:
            break
        out = candidate
    return out or text[:limit].rsplit(" ", 1)[0]

def _extract_entities(text: str, limit: int = 12) -> list[str]:
    candidates = re.findall(r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b", text or "")
    blocked = {"You", "The", "This", "That", "Then", "Your", "They", "Something"}
    out = []
    for c in candidates:
        c = c.strip()
        if c in blocked or c in out:
            continue
        out.append(c)
        if len(out) >= limit:
            break
    return out

def _extract_key_phrases(text: str, entities: list[str] | None = None, limit: int = 12) -> list[str]:
    text = str(text or "")
    phrases = []
    for quote in re.findall(r'["\u201c](.{3,100}?)[\u201d"]', text):
        quote = re.sub(r"\s+", " ", quote).strip()
        if quote and quote.lower() not in {p.lower() for p in phrases}:
            phrases.append(quote)
    words = re.findall(r"[A-Za-z0-9'-]{3,}", text.lower())
    counts = defaultdict(int)
    for i, w in enumerate(words):
        if w in _STOPWORDS:
            continue
        counts[w] += 1
        if i + 1 < len(words) and words[i + 1] not in _STOPWORDS:
            counts[f"{w} {words[i + 1]}"] += 1.5
    ranked = sorted(counts, key=lambda item: (-counts[item], -len(item.split()), item))
    for e in entities or []:
        if e.lower() not in {p.lower() for p in phrases}:
            phrases.append(e)
    for p in ranked:
        if p.lower() in {x.lower() for x in phrases}:
            continue
        phrases.append(p)
        if len(phrases) >= limit:
            break
    return phrases[:limit]

def _memory_document(data: dict) -> str:
    phrases = ", ".join(data.get("key_phrases") or [])
    entities = ", ".join(data.get("entities") or [])
    return "\n".join(p for p in (
        f"category: {data.get('category', 'episode')}",
        f"turn: {data.get('turn_idx', '')}",
        f"location: {data.get('location', '')}",
        f"people: {entities}",
        f"key phrases: {phrases}",
        f"gist: {data.get('gist', '')}",
        f"details: {data.get('content', '')}",
        f"source: {data.get('provenance', 'witnessed')}",
        f"emotion: {data.get('emotional_context', '')}",
    ) if not p.endswith(": "))

def _memory_cues(data: dict) -> str:
    return "\n".join(p for p in (
        data.get("gist") or "",
        ", ".join(data.get("key_phrases") or []),
        ", ".join(data.get("entities") or []),
        data.get("location") or "",
        data.get("category") or "",
    ) if p)

def _replace_memory_fts(memory_id: int, data: dict):
    qi("DELETE FROM memory_retrieval_fts WHERE memory_id=?", (str(memory_id),))
    qi(
        "INSERT INTO memory_retrieval_fts(memory_id,chat_id,char_id,gist,content,key_phrases,entities) VALUES(?,?,?,?,?,?,?)",
        (str(memory_id), str(data.get("chat_id") or ""), str(data.get("char_id") or ""),
         data.get("gist") or "", data.get("content") or "",
         ", ".join(data.get("key_phrases") or []), ", ".join(data.get("entities") or [])),
    )

def _delete_memory_fts(memory_id: int):
    qi("DELETE FROM memory_retrieval_fts WHERE memory_id=?", (str(memory_id),))

# How far one consequence moves a memory's importance, and the ceiling it
# climbs toward. Deliberately small and asymptotic: importance is evidence
# accumulating that a memory mattered, and one relationship change is evidence,
# not proof. Nothing here is driven by RETRIEVAL -- a memory that gets recalled
# a lot would then get recalled more, which is a popularity loop wearing the
# word "importance". Only consequences the engine can point at move it, which
# is also why `access_count` stays written and unread.
_IMPORTANCE_STEP = 0.12
_IMPORTANCE_CEILING = 0.97
# A memory the character has re-read moves further, because being wrong about
# something is a bigger fact about it than being cited once.
_IMPORTANCE_DISPUTE_STEP = 0.2
_MAX_DISPUTE_READING = 300


def _dispute_of(raw):
    """The stored re-reading, or None. Never raises on a malformed blob -- a
    corrupt dispute must not make a memory unreadable."""
    if not raw:
        return None
    try:
        out = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return out if isinstance(out, dict) and out.get("reading") else None


def effective_importance(mem) -> float:
    """How much this memory matters NOW: its revised importance if it has one,
    else the salience it was minted with. The single place that fallback is
    decided, so a reader cannot accidentally rank on the raw column and see
    NULL for every row that has never been revised."""
    if isinstance(mem, dict):
        value = mem.get("importance")
        if value is None:
            value = mem.get("salience")
    else:
        value = mem["importance"]
        if value is None:
            value = mem["salience"]
    return _clamp(value)


def _row_memory(row) -> dict:
    return {
        "id": row["id"], "chat_id": row["chat_id"], "char_id": row["char_id"],
        "turn_id": row["turn_id"], "turn_idx": row["turn_idx"],
        "frame_id": row["frame_id"],
        "kind": row["kind"],
        "category": row["category"] or _default_category(row["kind"]),
        "provenance": row["provenance"], "salience": row["salience"],
        "content": row["content"], "gist": row["gist"] or _gist(row["content"]),
        "key_phrases": _json_list(row["key_phrases"]),
        "entities": _json_list(row["entities"]),
        "location": row["location"] or "",
        "emotional_context": row["emotional_context"] or "",
        "valence": row["valence"] or 0.0, "arousal": row["arousal"] or 0.0,
        "confidence": row["confidence"] or 0.0,
        "access_count": row["access_count"] or 0,
        "last_accessed": row["last_accessed"],
        # How central it BECAME. Distinct from salience, which records how much
        # it mattered when formed and is never revised -- a minor moment can
        # turn out to have been the important one, and the two facts are
        # different. NULL (never revised) reads as the salience, so an
        # untouched bank behaves exactly as it did.
        "importance": (row["salience"] if row["importance"] is None
                       else row["importance"]),
        "importance_revised": row["importance"] is not None,
        # The character's own later re-reading, if they have made one.
        "disputed": _dispute_of(row["disputed"]),
        "archived": bool(row["archived"]),
        "event_key": row["event_key"] or "",
        "embedding_model": row["embedding_model"] or "",
        "embedding_dim": row["embedding_dim"],
    }

def prepare_memory(chat_id, char_id, turn_id, kind, provenance, salience, content, *,
                   turn_idx=None, category=None, gist=None, key_phrases=None,
                   entities=None, location="", emotional_context="",
                   valence=0.0, arousal=0.0, confidence=1.0, event_key="",
                   frame_id=_UNSET, importance=None, disputed="") -> dict:
    content = re.sub(r"\s+", " ", str(content or "")).strip()
    entities = list(dict.fromkeys(entities if entities is not None else _extract_entities(content)))
    key_phrases = list(dict.fromkeys(key_phrases if key_phrases is not None else _extract_key_phrases(content, entities)))
    # frame_id defaults to whatever era this chat is CURRENTLY being
    # portrayed at -- almost always None (the present), so ordinary chats
    # that never time-travel see zero behavior change. _UNSET (not None)
    # is the "caller didn't specify" sentinel, since None is itself the
    # valid, meaningful "present" value a caller might deliberately pass.
    resolved_frame_id = _active_frame_id.get() if frame_id is _UNSET else frame_id
    return {
        "chat_id": chat_id, "char_id": char_id, "turn_id": turn_id,
        "turn_idx": turn_idx if turn_idx is not None else _turn_idx_for(turn_id),
        "frame_id": resolved_frame_id,
        "kind": kind or "episodic",
        "category": category if category in MEMORY_CATEGORIES else _default_category(kind),
        "provenance": provenance if provenance in MEMORY_PROVENANCE else "witnessed",
        "salience": _clamp(salience), "content": content,
        "gist": (gist or _gist(content)).strip(),
        "key_phrases": key_phrases[:16], "entities": entities[:16],
        "location": str(location or "").strip(),
        "emotional_context": str(emotional_context or "").strip(),
        "valence": _clamp(valence, -1.0, 1.0), "arousal": _clamp(arousal),
        "confidence": _clamp(confidence),
        "event_key": str(event_key or "").strip(),
        # None, not 0.0: NULL is "never revised" and reads as the salience.
        # Defaulting to a number here would freeze every new memory at its
        # mint value and silently kill the fallback.
        "importance": None if importance is None else _clamp(importance),
        "disputed": _storage_json(disputed) if isinstance(disputed, dict)
                    else str(disputed or ""),
    }

def _embed_memory(data: dict):
    docs = [_memory_document(data), _memory_cues(data) or _memory_document(data)]
    embedded = embed_texts_meta(docs)
    return embedded.vectors[0], embedded.vectors[1], embedded

def _upsert_memory(data: dict, full_vec, cue_vec, embedded):
    existing = None
    if data["event_key"]:
        existing = q("SELECT id FROM memories WHERE chat_id=? AND char_id=? AND event_key=?",
                     (data["chat_id"], data["char_id"], data["event_key"]), one=True)
    values = (
        data["turn_id"], data["turn_idx"], data["kind"], data["category"],
        data["provenance"], data["salience"], data["content"], data["gist"],
        json.dumps(data["key_phrases"], ensure_ascii=False),
        json.dumps(data["entities"], ensure_ascii=False),
        data["location"], data["emotional_context"], data["valence"],
        data["arousal"], data["confidence"], _blob(full_vec), _blob(cue_vec),
        embedded.model_key, embedded.dimensions, data.get("frame_id"),
        data.get("importance"), data.get("disputed") or "",
    )
    if existing:
        mid = existing["id"]
        qi("""UPDATE memories SET turn_id=?,turn_idx=?,kind=?,category=?,provenance=?,
            salience=?,content=?,gist=?,key_phrases=?,entities=?,location=?,
            emotional_context=?,valence=?,arousal=?,confidence=?,embedding=?,
            cue_embedding=?,embedding_model=?,embedding_dim=?,frame_id=?,
            importance=?,disputed=?,archived=0 WHERE id=?""",
           values + (mid,))
    else:
        mid = qi("""INSERT INTO memories(chat_id,char_id,turn_id,turn_idx,kind,category,
            provenance,salience,content,gist,key_phrases,entities,location,
            emotional_context,valence,arousal,confidence,embedding,cue_embedding,
            embedding_model,embedding_dim,frame_id,importance,disputed,event_key)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
           (data["chat_id"], data["char_id"]) + values + (data["event_key"],))
    _replace_memory_fts(mid, data)
    return mid

def add_memory(chat_id, char_id, turn_id, kind, provenance, salience, content, *,
               turn_idx=None, category=None, gist=None, key_phrases=None,
               entities=None, location="", emotional_context="",
               valence=0.0, arousal=0.0, confidence=1.0, event_key="",
               frame_id=_UNSET):
    data = prepare_memory(chat_id, char_id, turn_id, kind, provenance, salience, content,
                          turn_idx=turn_idx, category=category, gist=gist,
                          key_phrases=key_phrases, entities=entities, location=location,
                          emotional_context=emotional_context, valence=valence,
                          arousal=arousal, confidence=confidence, event_key=event_key,
                          frame_id=frame_id)
    full_vec, cue_vec, embedded = _embed_memory(data)
    return _upsert_memory(data, full_vec, cue_vec, embedded)

def prepare_memories_batch(memories: list[dict]) -> dict:
    """Normalize and embed a memory batch without mutating the database.

    Turn commit uses this before opening its outer write transaction so a
    remote embedding request can never hold SQLite's write lock.  The result
    is intentionally opaque to callers outside this module; pass it back to
    :func:`add_memories_batch` through ``prepared_batch``.
    """
    prepared = [prepare_memory(**item) for item in memories]
    if not prepared:
        return {"prepared": [], "embedded": None}
    texts = []
    for data in prepared:
        texts.extend([_memory_document(data), _memory_cues(data) or _memory_document(data)])
    embedded = embed_texts_meta(texts)
    return {"prepared": prepared, "embedded": embedded}


def add_memories_batch(
    memories: list[dict] | None = None,
    *,
    prepared_batch: dict | None = None,
) -> list[int]:
    if prepared_batch is None:
        prepared_batch = prepare_memories_batch(memories or [])
    prepared = prepared_batch.get("prepared") or []
    embedded = prepared_batch.get("embedded")
    if not prepared:
        return []
    if embedded is None or len(embedded.vectors) != len(prepared) * 2:
        raise ValueError("Invalid prepared memory embedding batch")
    ids = []
    with transaction():
        for i, data in enumerate(prepared):
            full_vec = embedded.vectors[i * 2]
            cue_vec = embedded.vectors[i * 2 + 1]
            ids.append(_upsert_memory(data, full_vec, cue_vec, embedded))
    return ids

def delete_turn_memories(turn_id):
    for r in q("SELECT id FROM memories WHERE turn_id=?", (turn_id,)):
        _delete_memory_fts(r["id"])
    qi("DELETE FROM memories WHERE turn_id=?", (turn_id,))

# ---- The one seam a mind reads its own memory through -------------------
#
# Two filters decide what a character may legitimately retrieve, and both must
# run BEFORE any ranking:
#
#   the turn cutoff   -- a mind deciding turn N must never read a memory of how
#                        turn N turned out (audit F1). Not hypothetical: a
#                        reroll or rerun-from-stage replays the onset of a turn
#                        whose outcome memories are already committed.
#   frame visibility  -- a memory formed in another era is not this mind's to
#                        have yet (frames.is_memory_visible).
#
# They used to be written out again at every read path -- search_memories,
# contrast_memory, recent_memory_buffer, list_memories,
# consolidate_character_memory -- and docs/MEMORY.md claimed that repetition
# was what stopped a new path forgetting them. That reasoning is backwards:
# repetition is precisely how a sixth path forgets, because nothing makes it
# reproduce five filters it may not know exist.
#
# So the rules live here, once, and every argument that carries one is
# REQUIRED and has no default. A caller cannot omit `before_turn_idx` or
# `viewer_frame_id`; it can only state them, including stating None. Forgetting
# becomes a TypeError instead of a leak.
#
# The remaining parameters only ever NARROW the result. None of them can
# readmit a row the two filters excluded, which is what keeps this a seam
# rather than a configurable query builder.


def visible_memory_rows(chat_id, char_id, *, before_turn_idx, viewer_frame_id,
                        include_archived, since_turn_idx=None,
                        require_turn_idx=False):
    """Raw rows this character may legitimately read. The only way to get them.

    `before_turn_idx` is the turn being decided, and the cutoff is strict:
    turn N itself and every later play-order turn go. Pass None only where
    there is no turn being decided -- a host browsing the memory panel, not a
    mind deciding a beat. `turn_idx IS NULL` rows (imported or authored, with
    no place in play order) are always kept: they belong to no turn, so they
    cannot be this turn's leaked outcome.

    `viewer_frame_id` may be `_UNSET` to read the ambient contextvar, which is
    what almost every caller wants; it is still passed explicitly so the
    decision is visible at the call site. A caller on a worker thread must
    pass the real value -- contextvars do not propagate into
    ThreadPoolExecutor workers (see maybe_consolidate_character_memory).
    """
    clauses = ["chat_id=?", "char_id=?"]
    args = [chat_id, char_id]
    if not include_archived:
        clauses.append("archived=0")
    if require_turn_idx:
        clauses.append("turn_idx IS NOT NULL")
    if since_turn_idx is not None:
        clauses.append("turn_idx>=?")
        args.append(since_turn_idx)
    if before_turn_idx is not None:
        # Stated once, in SQL. An earlier draft also re-filtered in Python
        # "so the rule is an invariant, not an optimisation" -- but two copies
        # of one rule is the thing this seam exists to stop, and mutation
        # testing proved the point: deleting the Python half left all 21 seam
        # tests green, because the SQL half was already doing the work. A
        # guard nothing can observe failing is not a guard.
        #
        # NULL turn_idx is kept explicitly. Those rows are imported or
        # authored, belong to no turn, and so cannot be this turn's leaked
        # outcome -- and SQL's three-valued logic would silently drop them
        # from a bare `turn_idx < ?`.
        clauses.append("(turn_idx IS NULL OR turn_idx<?)")
        args.append(before_turn_idx)
    rows = q("SELECT * FROM memories WHERE " + " AND ".join(clauses), tuple(args))
    vf = _active_frame_id.get() if viewer_frame_id is _UNSET else viewer_frame_id
    return [r for r in rows
            if _frames.is_memory_visible(char_id, r["frame_id"], vf, r["turn_idx"])]


# ---- Host-facing reads, which deliberately cross character boundaries ----
#
# These answer a question ABOUT the cast rather than a question a character
# asks itself, so they are not scoped to one char_id and must never feed a
# character's context. They are named here so the crossing is a listed
# exception rather than an oversight, and
# tests/test_memory_read_seam.py::test_no_unlisted_cross_character_reader
# fails if the list grows without a decision.
HOST_SCOPE_READERS = ("dramatic_irony_feed", "promise_ledger")


def dramatic_irony_feed(chat_id, limit=100):
    """Every character's memories that did NOT come from directly
    witnessing the thing themselves (heard/told/inferred/read) -- a
    transparency window into what each character currently believes on
    secondhand or inferred grounds, for a reader to judge for themselves
    whether it's actually wrong. Deliberately does not claim to know
    a belief IS false (that would need comparing it against objective
    world state with its own LLM call); it surfaces exactly the
    provenance distinction the engine already tracks per memory and
    leaves the judgment to whoever's reading it -- the same distinction
    that already gates what a character legitimately knows.
    """
    rows = q(
        """SELECT m.*, ch.name AS char_name FROM memories m
        JOIN characters ch ON ch.id = m.char_id
        WHERE m.chat_id=? AND m.archived=0 AND m.provenance != 'witnessed'
        ORDER BY CASE WHEN m.turn_idx IS NULL THEN 1 ELSE 0 END, m.turn_idx DESC, m.id DESC
        LIMIT ?""",
        (chat_id, max(1, min(int(limit), 500))),
    )
    out = []
    for r in rows:
        entry = _row_memory(r)
        entry["char_name"] = r["char_name"]
        out.append(entry)
    return out

def promise_ledger(chat_id, limit=200):
    """Every promise-category memory across the whole chat (any
    character, not one at a time like list_memories), in chronological
    order -- a running ledger of what's been promised, to whom, without
    claiming to auto-detect kept/broken status (that's a real judgment
    call left to whoever reads it, not something to fabricate from a
    keyword match).
    """
    rows = q(
        """SELECT m.*, ch.name AS char_name FROM memories m
        JOIN characters ch ON ch.id = m.char_id
        WHERE m.chat_id=? AND m.category='promise' AND m.archived=0
        ORDER BY CASE WHEN m.turn_idx IS NULL THEN 1 ELSE 0 END, m.turn_idx ASC, m.id ASC
        LIMIT ?""",
        (chat_id, max(1, min(int(limit), 500))),
    )
    out = []
    for r in rows:
        entry = _row_memory(r)
        entry["char_name"] = r["char_name"]
        out.append(entry)
    return out

def list_memories(chat_id, char_id, *, include_archived=False, category=None,
                  provenance=None, limit=500, offset=0, viewer_frame_id=_UNSET):
    """The host's memory panel for one character. No turn cutoff, deliberately:
    nobody is deciding a beat here, so there is no future to withhold.

    Paging now happens AFTER frame filtering. It used to be `LIMIT ? OFFSET ?`
    in SQL with the visibility pass applied to whatever came back, so a page
    could return fewer rows than asked for -- or none -- while plenty of
    visible memories sat behind it, and the panel had no way to tell "the end"
    from "this page happened to be another era's".
    """
    rows = visible_memory_rows(
        chat_id, char_id,
        before_turn_idx=None,
        viewer_frame_id=viewer_frame_id,
        include_archived=include_archived,
    )
    if category in MEMORY_CATEGORIES:
        rows = [r for r in rows if r["category"] == category]
    if provenance in MEMORY_PROVENANCE:
        rows = [r for r in rows if r["provenance"] == provenance]
    rows.sort(key=lambda r: (r["turn_idx"] is None,
                            -(r["turn_idx"] if r["turn_idx"] is not None else 0),
                            -r["id"]))
    start = max(0, int(offset))
    stop = start + max(1, min(int(limit), 1000))
    return [_row_memory(r) for r in rows[start:stop]]

def update_memory(mid, content=None, salience=None, kind=None, provenance=None, *,
                  category=None, gist=None, key_phrases=None, entities=None,
                  location=None, emotional_context=None, valence=None,
                  arousal=None, confidence=None, archived=None):
    row = q("SELECT * FROM memories WHERE id=?", (mid,), one=True)
    if not row:
        return False
    current = _row_memory(row)
    data = prepare_memory(
        current["chat_id"], current["char_id"], current["turn_id"],
        kind if kind is not None else current["kind"],
        provenance if provenance is not None else current["provenance"],
        salience if salience is not None else current["salience"],
        content if content is not None else current["content"],
        turn_idx=current["turn_idx"],
        category=category if category is not None else current["category"],
        gist=gist if gist is not None else current["gist"],
        key_phrases=key_phrases if key_phrases is not None else current["key_phrases"],
        entities=entities if entities is not None else current["entities"],
        location=location if location is not None else current["location"],
        emotional_context=emotional_context if emotional_context is not None else current["emotional_context"],
        valence=valence if valence is not None else current["valence"],
        arousal=arousal if arousal is not None else current["arousal"],
        confidence=confidence if confidence is not None else current["confidence"],
        event_key=current["event_key"],
        frame_id=current["frame_id"],
    )
    full_vec, cue_vec, embedded = _embed_memory(data)
    qi("""UPDATE memories SET kind=?,category=?,provenance=?,salience=?,content=?,gist=?,
        key_phrases=?,entities=?,location=?,emotional_context=?,valence=?,arousal=?,
        confidence=?,embedding=?,cue_embedding=?,embedding_model=?,embedding_dim=?,archived=?
        WHERE id=?""",
       (data["kind"], data["category"], data["provenance"], data["salience"],
        data["content"], data["gist"],
        json.dumps(data["key_phrases"], ensure_ascii=False),
        json.dumps(data["entities"], ensure_ascii=False),
        data["location"], data["emotional_context"], data["valence"],
        data["arousal"], data["confidence"], _blob(full_vec), _blob(cue_vec),
        embedded.model_key, embedded.dimensions,
        int(bool(archived)) if archived is not None else int(current["archived"]),
        mid))
    _replace_memory_fts(mid, data)
    return True

def record_dispute(chat_id, char_id, gist, reading, turn_idx):
    """The character has re-read one of their own memories.

    The event stays exactly as it was -- "I saw this" is still true, and the
    row's `content`, `gist`, `provenance` and `salience` are untouched. What is
    recorded beside it is that the character no longer reads it the way they
    first did, which is what deception, disguise, staging and plain
    misidentification actually do to a mind: they do not delete the
    experience, they change what it meant.

    Deliberately NOT an edge to the memory that superseded it. Checkpoint
    restore is delete-and-reinsert, so every row id changes and an id-keyed
    edge would be shredded by the first rollback; stored on the row it rides
    the existing round-trip verbatim.

    Matched on the character's OWN rows only, by gist, exactly-then-loosely --
    a character may only re-read something they remember. Returns the ids
    updated.
    """
    needle = " ".join(str(gist or "").split()).casefold()
    reading = " ".join(str(reading or "").split())[:_MAX_DISPUTE_READING]
    if not needle or not reading:
        return []
    rows = q("SELECT id, gist, content, disputed, salience, importance "
             "FROM memories WHERE chat_id=? AND char_id=?", (chat_id, char_id))
    hits = [r for r in rows
            if " ".join((r["gist"] or "").split()).casefold() == needle]
    if not hits:
        hits = [r for r in rows
                if needle in " ".join((r["gist"] or "").split()).casefold()
                or needle in " ".join((r["content"] or "").split()).casefold()]
    updated = []
    for row in hits:
        prior = _dispute_of(row["disputed"]) or {}
        blob = _storage_json({
            "turn_idx": turn_idx,
            "reading": reading,
            # A memory re-read twice has been genuinely unstable, and that is
            # worth being able to see.
            "count": int(prior.get("count") or 0) + 1,
        })
        # Being wrong about something is a larger fact about it than being
        # cited once, so a dispute moves importance further than an ordinary
        # consequence -- and it moves UP: a memory whose meaning changed is
        # more central to this mind, not less.
        base = effective_importance(row)
        raised = min(_IMPORTANCE_CEILING, base + _IMPORTANCE_DISPUTE_STEP)
        qi("UPDATE memories SET disputed=?, importance=? WHERE id=?",
           (blob, raised, row["id"]))
        updated.append(row["id"])
    return updated


def raise_importance(chat_id, char_id, memory_ids=(), *, event_keys=(),
                     only_unrevised=False, step=_IMPORTANCE_STEP):
    """Nudge memories toward the ceiling because something happened that they
    turned out to matter for.

    Asymptotic rather than additive so repetition cannot run away: each
    consequence closes a fraction of the remaining distance. Never lowers, and
    never touches `salience` -- how much it mattered when it was FORMED is a
    different fact, and the one consolidation and archiving still read.

    `chat_id`/`char_id` are required and are applied in the WHERE clause, so a
    model that cites a memory id belonging to another mind moves nothing. The
    ids arrive from model output; ownership is not negotiable, and the same
    lesson as the read seam applies -- the scoping belongs in the query, not
    in whoever remembers to check first.

    `only_unrevised` bumps a row exactly once ever, which is how a signal that
    is itself downstream of retrieval is stopped from compounding.
    """
    ids = [int(i) for i in (memory_ids or []) if i is not None]
    keys = [str(k) for k in (event_keys or []) if str(k or "").strip()]
    if not ids and not keys:
        return 0
    # Either handle resolves the same rows. `event_key` is what a character
    # actually cites (see commit._cited_memory_ids); the row id is what
    # internal callers have.
    where, args = [], [chat_id, char_id]
    if ids:
        where.append("id IN (%s)" % ",".join("?" for _ in ids)); args += ids
    if keys:
        where.append("event_key IN (%s)" % ",".join("?" for _ in keys)); args += keys
    clause = "chat_id=? AND char_id=? AND (%s)" % " OR ".join(where)
    args = tuple(args)
    if only_unrevised:
        clause += " AND importance IS NULL"
    rows = q(f"SELECT id, salience, importance FROM memories WHERE {clause}", args)
    changed = 0
    for row in rows:
        base = effective_importance(row)
        raised = min(_IMPORTANCE_CEILING, base + step * (1.0 - base))
        if raised - base > 1e-6:
            qi("UPDATE memories SET importance=? WHERE id=?", (raised, row["id"]))
            changed += 1
    return changed


def delete_memory(mid):
    _delete_memory_fts(mid)
    qi("DELETE FROM memories WHERE id=?", (mid,))

# ---- Hybrid retrieval ----

def _memory_fts_query(text):
    tokens = [t.lower() for t in re.findall(r"[A-Za-z0-9'-]{3,}", text or "") if t.lower() not in _STOPWORDS]
    tokens = list(dict.fromkeys(tokens))[:16]
    if not tokens:
        return None
    return " OR ".join(f'"{t.replace(chr(34), chr(34)+chr(34))}"' for t in tokens)

def _lexical_memory_ranking(chat_id, char_id, query_text, limit=60):
    fq = _memory_fts_query(query_text)
    if not fq:
        return []
    try:
        rows = q("""SELECT CAST(memory_id AS INTEGER) AS mid, bm25(memory_retrieval_fts) AS score
            FROM memory_retrieval_fts WHERE memory_retrieval_fts MATCH ? AND chat_id=? AND char_id=?
            ORDER BY score LIMIT ?""", (fq, str(chat_id), str(char_id), limit))
        return [r["mid"] for r in rows]
    except Exception:
        return []

def _temporal_mode(query_text):
    text = (query_text or "").lower()
    if any(re.search(p, text) for p in _OLD_CUES):
        return "old"
    if any(re.search(p, text) for p in _RECENT_CUES):
        return "recent"
    return "neutral"

def _exact_cue_score(memory, query_text):
    ql = (query_text or "").lower()
    if not ql:
        return 0.0
    score = 0.0
    for phrase in memory.get("key_phrases") or []:
        pl = phrase.lower().strip()
        if pl and pl in ql:
            score = max(score, 1.0)
        elif pl and ql in pl and len(ql) >= 4:
            score = max(score, 0.8)
    for entity in memory.get("entities") or []:
        if entity.lower() in ql:
            score = max(score, 0.7)
    loc = (memory.get("location") or "").lower()
    if loc and loc in ql:
        score = max(score, 0.7)
    return score

def _jaccard_text(a, b):
    la = set(re.findall(r"[a-z0-9']{3,}", (a or "").lower()))
    lb = set(re.findall(r"[a-z0-9']{3,}", (b or "").lower()))
    if not la or not lb:
        return 0.0
    return len(la & lb) / len(la | lb)

def _memory_similarity(a, b):
    av, bv = a.get("_vector"), b.get("_vector")
    if av is not None and bv is not None and len(av) == len(bv):
        return max(0.0, _cos(av, bv))
    return _jaccard_text(f"{a.get('gist','')} {a.get('content','')}",
                         f"{b.get('gist','')} {b.get('content','')}")

# The bridge between two score scales that were being added together as though
# they shared one.
#
# RRF's output is arbitrary in magnitude -- `weight / (60 + rank)` is about
# 0.02 at rank 1, and only its ORDER carries meaning. The bonuses that follow
# (salience, recency, presence) are hand-tuned on a 0..1 utility scale. Summed
# raw, the four relevance rankings could contribute at most 0.074 combined,
# while the recency bonus alone reaches 0.12 -- so a recent, salient memory
# with NO relevance to the query outranked the single best match on every
# relevance signal the engine has.
#
# It was invisible until alpha 6.3. With the crc32 fallback the vector
# rankings were lexical noise, so nobody could tell they were being ignored;
# configuring a real embeddings provider made the signal real and the
# imbalance measurable. Measured on a live 441-memory story: end-to-end
# retrieval of a paraphrased memory ran at 1/16, and 88% of the memories
# handed to a character carried no vector match at all.
#
# Scaled rather than re-tuning the bonuses, because the bonuses' RELATIVE
# values are meaningful and their absolute band is the one that was chosen
# deliberately. 12 puts the four rankings at ~0.9 combined against a ~0.4
# bonus band: relevance leads, and salience/recency/presence still decide
# between comparably relevant memories, which is what they are for. Measured
# across 12 real perception views, the share of retrieved memories with an
# actual vector match goes 12% -> ~50% and plateaus by 16, so this sits at the
# top of the useful range rather than past it.
_RRF_SCALE = 12.0


# How many retrieved memories reach a character each beat.
#
# Was 8, and measured too low once relevance actually worked. Every result set
# is padded with chronological neighbours of what was recalled, so at 8 those
# four padding entries were a third of what the character saw. Raising the
# limit dilutes them with relevance-selected memories instead -- measured on
# real perception views, mean relevance of the whole set RISES from 0.608 to
# 0.640 while the least relevant slot does not move, i.e. the added memories
# are better than the padding they displace, not filler.
#
# 16 rather than 24: end-to-end recall of a paraphrased memory goes 7/16 ->
# 11/16 -> 13/16 across 8/16/24, but relevance flattens (0.640 -> 0.649) while
# the payload keeps growing (~890 -> ~1242 tokens per character per beat). The
# attention budget is real -- see docs/UNBUILT.md 1.12 on nine payload keys --
# so this stops where the curve does.
_RECALL_LIMIT = 16


# Mood-congruent recall: what you feel shapes what comes back.
#
# `memories.valence` is written on every row and, until alpha 6.3.1, fed the
# ranking nowhere -- its only consumer was `contrast_memory`, and there as
# `abs(valence)`, which is emotional INTENSITY ("this memory is charged"), not
# congruence ("this matches how you feel now"). The signed half of an affect
# signal the engine already tracked had never been used for anything.
#
# It was also unbuildable until the same release, and that is worth recording
# rather than repeating: memories were taking the character's raw self-report
# instead of their resolved affect, which measured 0% negative against a true
# 22%. Ranking on it then was ranking on a constant -- built once, measured as
# inert, and withdrawn. It works now because the axis does.
#
# Deliberately small, and in the same band as the salience term for the reason
# the belief-credence comment beside it already gives: this should break a tie
# between comparably relevant memories, never outrank an actual match. And
# deliberately bounded, because congruence is a FEEDBACK loop -- a character in
# despair recalling only despair deepens the despair. That may be exactly right
# for fiction (it is what rumination is), but it should be a chosen intensity
# rather than an emergent one.
_MOOD_CONGRUENCE = 0.05

_MOOD_VALENCE = (
    (("afraid", "fear", "fearful", "terrified", "scared", "anxious", "dread",
      "panic", "angry", "furious", "rage", "resentful", "bitter", "grief",
      "grieving", "ashamed", "humiliated", "guilty", "miserable", "despair",
      "hopeless", "lonely", "hurt", "sad", "sick", "desperate", "wary",
      "distrustful", "uneasy", "unease", "tense", "shaken"), -1.0),
    (("happy", "glad", "delighted", "elated", "warm", "fond", "affectionate",
      "content", "calm", "safe", "relieved", "hopeful", "proud", "amused",
      "playful", "curious", "eager", "tender", "grateful", "trusting",
      "composed", "steady"), 1.0),
)


def _mood_axis(text):
    """The signed valence a mood/goal string implies, or None if it implies
    none. Word-matched against a small closed vocabulary rather than embedded:
    this is a tiebreak, and a wrong sign is worse than no sign."""
    words = set(re.split(r"[^a-z']+", str(text or "").casefold()))
    if not words:
        return None
    score = 0.0
    for vocab, sign in _MOOD_VALENCE:
        score += sign * len(words & set(vocab))
    return None if score == 0 else (1.0 if score > 0 else -1.0)


def _rrf_add(scores, reasons, ranking, weight, reason):
    for rank, mid in enumerate(ranking, 1):
        scores[mid] += (weight * _RRF_SCALE) / (60.0 + rank)
        if rank <= 12 and reason not in reasons[mid]:
            reasons[mid].append(reason)

# (chat_id, char_id, model_key) already reported. Retrieval runs for every
# character on every beat, so the warning has to be once per situation rather
# than once per call, or it becomes the noise it exists to cut through.
_STRANDED_REPORTED = set()


def _warn_stranded_embeddings(chat_id, char_id, stranded, total, model_key):
    """Say so when stored vectors no longer match the live embedding model.

    A row whose `embedding_model`/`embedding_dim` differ from the current
    provider's scores 0.0 on BOTH vector rankings -- forever, because nothing
    re-embeds. That is correct behaviour (a vector from another model is not
    comparable) and it is silent, which is the problem: configure an
    `embeddings` provider on a story with history and every memory written
    before that moment quietly drops to keyword-and-exact-match only, while
    new ones get the full four signals. The bank splits into two eras and
    nothing says a word.

    Retrieval still WORKS -- BM25 and exact-match are unaffected, so this
    degrades rather than breaks, which is exactly why it needs announcing.
    The fix when it fires is a re-embed pass; see docs/UNBUILT.md §1.15.
    """
    if not stranded or not total:
        return
    key = (chat_id, char_id, model_key)
    if key in _STRANDED_REPORTED:
        return
    _STRANDED_REPORTED.add(key)
    logger.warning(
        "memory: %d of %d stored memories for chat %s char %s were embedded by "
        "a different model than the live one (%s); their semantic and "
        "cue-vector rankings score 0 and only keyword/exact matching reaches "
        "them. Re-embed to restore semantic recall (docs/UNBUILT.md 1.15).",
        stranded, total, chat_id, char_id, model_key,
    )


# How hard an aspect ranking pulls, against 1.0/1.15 for the main query's own
# semantic and cue rankings. Deliberately below both: an aspect is a nudge
# from what the character wants or feels, and it must be able to break a tie
# between two comparably relevant memories without outranking what the beat is
# actually about.
_ASPECT_WEIGHT = 0.55


def search_memories(chat_id, char_id, query, k=8, *, include_archived=True,
                    current_turn_idx=None, chronological=True, viewer_frame_id=_UNSET,
                    here=None, in_sight=None, aspects=None):
    """Retrieve, fusing the main query with any `aspects` given alongside it.

    `aspects` is [(label, text), ...] -- short, separate facets of what the
    character is bringing to the beat (their mood, their goal, the threads
    they have not resolved). Each gets its OWN ranking fused into the same
    RRF, rather than being concatenated onto the query string.

    That distinction is the whole point, and it is measured. The caller used
    to join everything into one string, where the character's current view
    ran a median 1,015 characters against a mood fragment of 10-60 -- so
    `cosine(query_with_mood, view_alone)` came out at 0.994. The mood moved
    the query vector by essentially nothing and reached recall only as
    whichever stray n-grams the word happened to share. A short facet cannot
    compete for influence inside a long string; given its own rank list it
    does not have to.
    """
    # Audit F1 (a mind deciding turn N must not read how turn N turned out)
    # and frame visibility both live in visible_memory_rows, applied before any
    # ranking so no scoring path can resurrect what they dropped. The turn
    # cutoff used to feed only the recency scoring below, which RANKED those
    # rows highly instead of removing them.
    rows = visible_memory_rows(
        chat_id, char_id,
        before_turn_idx=current_turn_idx,
        viewer_frame_id=viewer_frame_id,
        include_archived=include_archived,
    )
    here_set = {str(here).strip().casefold()} if here else set()
    in_sight_set = {
        str(p).strip().casefold() for p in (in_sight or ()) if str(p or "").strip()
    } - here_set
    if not rows:
        return []
    query_text = str(query or "").strip()
    # One embedding call for the query AND every aspect: the aspects are short
    # and the round trip is what costs, so separating the rankings is free.
    _aspects = [(str(lbl), str(txt).strip()) for lbl, txt in (aspects or [])
                if str(txt or "").strip()]
    embedded = embed_texts_meta([query_text or "memory"]
                                + [txt for _lbl, txt in _aspects])
    qv = embedded.vectors[0]
    aspect_vectors = list(zip((lbl for lbl, _t in _aspects),
                              embedded.vectors[1:]))
    memories = {}
    sem_scores, cue_scores = [], []
    stranded = 0
    comparable = {}
    for row in rows:
        mem = _row_memory(row)
        fv, cv = _vec(row["embedding"]), _vec(row["cue_embedding"])
        compatible = row["embedding_model"] == embedded.model_key and row["embedding_dim"] == embedded.dimensions
        if not compatible:
            stranded += 1
        sem = _cos(qv, fv) if compatible and fv is not None else 0.0
        cue = _cos(qv, cv) if compatible and cv is not None else 0.0
        mem["_vector"] = fv if compatible else None
        memories[mem["id"]] = mem
        sem_scores.append((sem, mem["id"]))
        cue_scores.append((cue, mem["id"]))
        if compatible and aspect_vectors:
            # Kept only while the aspect rankings are built, a few lines down.
            comparable[mem["id"]] = (fv, cv)
    _warn_stranded_embeddings(chat_id, char_id, stranded, len(rows), embedded.model_key)
    sem_rank = [mid for s, mid in sorted(sem_scores, reverse=True) if s > 0][:60]
    cue_rank = [mid for s, mid in sorted(cue_scores, reverse=True) if s > 0][:60]
    lex_rank = _lexical_memory_ranking(chat_id, char_id, query_text)
    exact_rank = [mid for mid in sorted(memories, key=lambda x: _exact_cue_score(memories[x], query_text), reverse=True)
                  if _exact_cue_score(memories[mid], query_text) > 0]
    fused = defaultdict(float)
    reasons = defaultdict(list)
    _rrf_add(fused, reasons, sem_rank, 1.0, "semantic match")
    _rrf_add(fused, reasons, cue_rank, 1.15, "cue-vector match")
    _rrf_add(fused, reasons, lex_rank, 1.1, "keyword match")
    _rrf_add(fused, reasons, exact_rank, 1.25, "exact phrase or entity match")
    # One ranking per aspect, at a weight that can break a tie but not win an
    # argument with what the beat is about.
    for label, av in aspect_vectors:
        scored = []
        for mid, (fv, cv) in comparable.items():
            best = max(_cos(av, fv) if fv is not None else 0.0,
                       _cos(av, cv) if cv is not None else 0.0)
            if best > 0:
                scored.append((best, mid))
        if scored:
            ranked = [mid for _s, mid in sorted(scored, reverse=True)][:60]
            _rrf_add(fused, reasons, ranked, _ASPECT_WEIGHT, label)
    tmode = _temporal_mode(query_text)
    # From the aspects when the caller supplied them (that is where mood
    # actually travels), falling back to the query itself.
    mood_axis = None
    for label, text in _aspects:
        if "feel" in label.casefold():
            mood_axis = _mood_axis(text)
            break
    if mood_axis is None:
        mood_axis = _mood_axis(query_text)
    known_turns = [m["turn_idx"] for m in memories.values() if m["turn_idx"] is not None]
    max_turn = current_turn_idx if current_turn_idx is not None else max(known_turns, default=0)
    for mid, mem in memories.items():
        # `importance`, not `salience`: how much it matters NOW, which is the
        # question ranking is asking. They are the same number until some
        # consequence revises one, so a bank that has never been touched ranks
        # exactly as it did.
        fused[mid] += 0.08 * effective_importance(mem)
        fused[mid] += 0.04 * mem["confidence"]
        if mem["kind"] == "inference":
            # Belief-weighted recall. Confidence on an inference row is no
            # longer a mint-time constant -- reconcile_inference_confidence
            # tracks it to what the character currently believes -- so it is
            # the signal that separates a live belief from one they have since
            # explained away. Signed around 0.5 so a held belief is promoted
            # and an abandoned one demoted; magnitude is deliberately in the
            # same band as the salience term above rather than larger, because
            # this should break a tie between competing inferences, not
            # outrank an actual semantic match.
            fused[mid] += 0.10 * (mem["confidence"] - 0.5)
            if mem["confidence"] >= 0.6:
                reasons[mid].append("belief the character still holds")
            elif mem["confidence"] <= 0.25:
                reasons[mid].append("belief the character has since revised")
        fused[mid] += 0.08 * _exact_cue_score(mem, query_text)
        if mood_axis is not None:
            # Same-signed feeling pulls up, opposite pushes down, scaled by how
            # strongly the memory itself is charged. A neutral memory (valence
            # 0) is untouched either way.
            congruent = mood_axis * float(mem["valence"] or 0.0)
            if congruent:
                fused[mid] += _MOOD_CONGRUENCE * congruent
                if congruent > 0 and "matches how you feel" not in reasons[mid]:
                    reasons[mid].append("matches how you feel")
        ti = mem["turn_idx"]
        if ti is not None and max_turn:
            age = _clamp((max_turn - ti) / max(max_turn, 1))
            if tmode == "old":
                fused[mid] += 0.12 * age
                if "older-memory cue" not in reasons[mid]:
                    reasons[mid].append("older-memory cue")
            elif tmode == "recent":
                fused[mid] += 0.12 * (1.0 - age)
                if "recent-memory cue" not in reasons[mid]:
                    reasons[mid].append("recent-memory cue")
        # Where you are is a retrieval cue. Ranking was semantic + lexical +
        # recency only, so "what happened in THIS room" -- and the navigational
        # form of it, "which way did I go from here last time" -- had no index
        # behind it at all: the one memory that answers it competes purely on
        # wording. `location` was already stored on every row and simply never
        # read. Deliberately modest, and additive rather than a filter: being
        # here makes a memory easier to reach, it does not make everything
        # elsewhere unreachable.
        if here_set and str(mem.get("location") or "").strip().casefold() \
                in here_set:
            fused[mid] += 0.09
            if "happened here" not in reasons[mid]:
                reasons[mid].append("happened here")
        elif in_sight_set and str(mem.get("location") or "").strip().casefold() \
                in in_sight_set:
            # A place currently VISIBLE is a retrieval cue too, and it is the
            # more useful one: recalling what happened in the room you are
            # standing in confirms where you are, but recalling it about a room
            # you can SEE lets you decide whether to go there. Weighted below
            # the here-cue, since standing somewhere is stronger evidence of
            # relevance than looking at it.
            fused[mid] += 0.05
            if "visible from here" not in reasons[mid]:
                reasons[mid].append("visible from here")
        if mem["category"] == "promise" and any(t in query_text.lower() for t in ("promise", "promised", "swore", "vow", "agreed")):
            fused[mid] += 0.1
            reasons[mid].append("promise category")
    ranked = sorted(memories, key=lambda x: fused[x], reverse=True)
    selected = []
    pool = ranked[:max(k * 8, 40)]
    while pool and len(selected) < k:
        best_id, best = None, float("-inf")
        for mid in pool:
            rel = fused[mid]
            red = max((_memory_similarity(memories[mid], memories[s]) for s in selected), default=0.0)
            mmr = 0.82 * rel - 0.18 * red
            if mmr > best:
                best = mmr
                best_id = mid
        selected.append(best_id)
        pool.remove(best_id)
    expanded = list(selected)
    if len(expanded) < k + 2:
        by_turn = sorted((m for m in memories.values() if m["turn_idx"] is not None), key=lambda m: (m["turn_idx"], m["id"]))
        positions = {m["id"]: i for i, m in enumerate(by_turn)}
        for mid in selected[:3]:
            mem = memories[mid]
            if mem["category"] != "episode":
                continue
            pos = positions.get(mid)
            if pos is None:
                continue
            for np in (pos - 1, pos + 1):
                if 0 <= np < len(by_turn):
                    nid = by_turn[np]["id"]
                    if nid not in expanded and abs(by_turn[np]["turn_idx"] - mem["turn_idx"]) <= 1:
                        expanded.append(nid)
                        reasons[nid].append("chronological neighbor of recalled episode")
                    if len(expanded) >= k + 2:
                        break
    result = []
    for mid in expanded:
        mem = dict(memories[mid])
        mem.pop("_vector", None)
        mem["score"] = round(fused[mid], 6)
        mem["retrieval_reasons"] = reasons[mid]
        result.append(mem)
    if chronological:
        result.sort(key=lambda m: (m["turn_idx"] is None, m["turn_idx"] if m["turn_idx"] is not None else 10**12, m["id"]))
    if result:
        now = time.time()
        ids = [m["id"] for m in result]
        ph = ",".join("?" for _ in ids)
        qi(f"UPDATE memories SET access_count=access_count+1, last_accessed=? WHERE id IN ({ph})", (now, *ids))
    return result

# ---- Contrast retrieval (unbidden recall) ----
#
# Ordinary recall asks "what is most like this beat". A character measurably
# stuck -- reissuing a sentence shape, holding the same ungoverned goal for a
# dozen beats, plateaued on a sustained stimulus -- needs the opposite
# question answered once: "what that mattered is LEAST like this beat".
# The selection is a second scoring pass over the same character-scoped,
# turn-cutoff, frame-filtered rows ordinary recall reads; it crosses no
# information boundary ordinary recall doesn't already cross, and it is a
# pure read -- unlike search_memories it must never touch access_count,
# because it runs mid-pipeline at character-stage time.

# How hard semantic distance pushes an unbidden memory away from the beat.
# Comparable to the token penalty (0.8) rather than larger: the structural
# axis is exact and has been carrying this since the beginning, so the vector
# joins it instead of replacing it.
_CONTRAST_SEMANTIC = 0.7

# What share of the bank must be comparable with the live model before the
# semantic axis is used at all. See the inversion note in contrast_memory.
_CONTRAST_SEMANTIC_COVERAGE = 0.9

# Below this many rows, "far from the recent window" barely means anything.
_CONTRAST_MIN_BANK = 20
# Obligation-tier categories never intrude as texture: surfacing a promise
# "unbidden" reads as the engine nagging, and those tiers have their own
# governance (fading/adrift clocks).
_CONTRAST_EXCLUDED_CATEGORIES = ("promise", "intention", "relationship")
# The salience backbone: what returns unbidden is what MATTERED. This floor
# also happens to exclude the unplaced-perception boilerplate rows (minted at
# salience 0.469 by the deterministic salience rule), which are noise here.
_CONTRAST_MIN_SALIENCE = 0.5


def contrast_memory(chat_id, char_id, query_text, current_turn_idx, *,
                    here=None, exclude_ids=(), k=1, viewer_frame_id=_UNSET):
    """Up to `k` high-salience memories DISSIMILAR to the current beat.

    Deliberately ignores `confidence`: a belief the character has since set
    aside is exactly the sort of thing that returns unprompted.

    Dissimilarity is carried by the structural fields (tokens, location,
    entities, turn distance), which are exact, PLUS semantic distance where
    the bank can supply it. The semantic half was deliberately absent until
    alpha 6.3.1: on a corpus embedded with the local-hash fallback, cosine was
    a fuzzy-lexical signal and would only have restated the token penalty.
    With real vectors it says something the token axis structurally cannot --
    that "the alley smelled of wet brick and chip fat" and "the backstreet
    stank of damp masonry and frying grease" are the SAME memory, not a
    perfect contrast. It is gated on near-total model coverage; see the
    inversion note in the body for why that gate is not optional.

    Same epistemic envelope as search_memories: this character's own rows
    only, hard turn cutoff, frame visibility. No writes.
    """
    rows = visible_memory_rows(
        chat_id, char_id,
        before_turn_idx=current_turn_idx,
        viewer_frame_id=viewer_frame_id,
        include_archived=True,
    )
    if len(rows) < _CONTRAST_MIN_BANK:
        return []
    excluded = set()
    for i in exclude_ids or ():
        try:
            excluded.add(int(i))
        except (TypeError, ValueError):
            continue
    here_cf = str(here or "").strip().casefold()
    query_cf = str(query_text or "").casefold()

    # THE INVERSION TRAP, and why this is gated so carefully.
    #
    # A row embedded by a different model scores 0.0 against any query. In
    # `search_memories` that makes it invisible, which is a silent omission.
    # Here the axis is INVERTED -- distance is the thing being rewarded -- so
    # the same 0.0 would read as maximally contrasting, and unbidden recall
    # would preferentially surface precisely the memories that have not been
    # rebuilt yet. The identical number flips from an omission into a
    # systematic bias, so only rows that are actually comparable get the
    # semantic term; the rest keep the structural axis alone, exactly as
    # before. A story mid-rebuild degrades to the old behaviour rather than to
    # a wrong one.
    qv = None
    comparable = {}
    try:
        embedded = embed_texts_meta([query_text or "memory"])
        for r in rows:
            if (r["embedding"] and r["embedding_model"] == embedded.model_key
                    and r["embedding_dim"] == embedded.dimensions):
                comparable[r["id"]] = _vec(r["embedding"])
        # Only worth the axis if MOST of the bank can be compared; a bank that
        # is half rebuilt would otherwise rank on which half a row is in.
        if len(comparable) >= _CONTRAST_SEMANTIC_COVERAGE * len(rows):
            qv = embedded.vectors[0]
        else:
            comparable = {}
    except Exception:
        qv, comparable = None, {}

    scored = []
    for r in rows:
        if r["id"] in excluded:
            continue
        mem = _row_memory(r)
        if mem["category"] in _CONTRAST_EXCLUDED_CATEGORIES:
            continue
        if not (mem["gist"] or "").strip():
            continue
        sal = effective_importance(mem)
        if sal < _CONTRAST_MIN_SALIENCE:
            continue
        score = sal
        score += 0.5 * abs(float(mem["valence"] or 0.0))
        score += 0.3 * float(mem["arousal"] or 0.0)
        ti = mem["turn_idx"]
        if ti is not None and current_turn_idx:
            score += 0.4 * _clamp((current_turn_idx - ti)
                                  / max(current_turn_idx, 1))
        else:
            # No place in play order (imported/authored past): as far from
            # the present as a memory gets.
            score += 0.4
        score -= 0.8 * _jaccard_text(
            query_text,
            f"{mem['gist']} {' '.join(mem['key_phrases'] or [])}")
        if qv is not None:
            # Semantic distance, once the vectors can carry it. The token
            # penalty above can only see DIFFERENT WORDS, and different words
            # routinely mean the same thing -- "the alley smelled of wet brick
            # and chip fat" against "the backstreet stank of damp masonry and
            # frying grease" shares nothing lexically and is the same memory.
            # A lexical axis calls that a perfect contrast; this one does not.
            fv = comparable.get(mem["id"])
            if fv is not None:
                score -= _CONTRAST_SEMANTIC * _cos(qv, fv)
        if here_cf and str(mem["location"] or "").strip().casefold() == here_cf:
            score -= 0.3
        ents = [str(e) for e in (mem["entities"] or []) if str(e).strip()]
        if ents and query_cf:
            present = sum(1 for e in ents if e.casefold() in query_cf)
            score -= 0.4 * (present / len(ents))
        scored.append((score, mem["id"], mem))
    scored.sort(key=lambda item: (-item[0], item[1]))
    out = []
    for score, _mid, mem in scored[:max(1, int(k))]:
        entry = dict(mem)
        entry["contrast_score"] = round(score, 4)
        out.append(entry)
    return out


def provenance_context_label(provenance):
    """The label a character's own context uses for this provenance class --
    'what_i_experienced' / 'what_i_was_told' / 'what_i_concluded' -- shared
    with the summary scopes so an unbidden memory speaks the same epistemic
    vocabulary the summaries already taught."""
    scope = summary_scope_for(provenance)
    for s, _field, label in _SUMMARY_SCOPES:
        if s == scope:
            return label
    return "what_i_experienced"


def recent_memory_buffer(chat_id, char_id, current_turn_idx, turns=4, limit=12, viewer_frame_id=_UNSET):
    # Fetch newest-first so a memory-dense window (many self/episodic/
    # inference rows in a short span) truncates its OLDEST rows against
    # `limit`, not its newest -- ORDER BY turn_idx, id ASC with LIMIT would
    # silently drop exactly the most recent memories (e.g. "I just escaped
    # aboard the ship") while keeping stale ones from a turn or two back,
    # which is precisely the wrong direction for a "recent memory" buffer
    # meant to keep a character's own decisions grounded in what most
    # recently happened. Reversed back to chronological order below since
    # every caller presents/reads this as an ordered narrative, not a
    # ranked list.
    # Exclude turn_idx >= current_turn_idx. A character's onset-time context
    # (perception/character decision for THIS turn) must never contain its own
    # committed memory of how this very turn resolved -- otherwise a single-step
    # reroll of a pre-commit stage on an already-committed turn would feed the
    # outcome back into the onset declaration (audit #10). The current turn has
    # not legitimately "happened" yet from the deciding mind's point of view.
    #
    # Recent-by-play-order is not the same as recent-by-diegetic-order: the
    # turn immediately before a frame jump can be an entirely different era,
    # so the frame filter in the seam is what stops a flash-forward's opening
    # turns pulling in the pre-jump present as "recent memory."
    rows = visible_memory_rows(
        chat_id, char_id,
        before_turn_idx=current_turn_idx,
        viewer_frame_id=viewer_frame_id,
        include_archived=False,
        since_turn_idx=max(0, current_turn_idx - turns),
        require_turn_idx=True,
    )
    # Truncate against `limit` from the NEWEST end, then hand back in
    # chronological order. Sorting ascending and slicing would drop exactly
    # the most recent memories ("I just escaped aboard the ship") and keep
    # stale ones from a turn or two back, which is the wrong direction for a
    # buffer meant to keep a character's own decisions grounded in what most
    # recently happened. Ordering after the seam rather than in SQL also means
    # the cap counts VISIBLE rows: it used to be applied before the frame
    # pass, so another era's memories consumed slots and shortened the buffer.
    rows.sort(key=lambda r: (r["turn_idx"], r["id"]), reverse=True)
    rows = list(reversed(rows[:limit]))
    return [_row_memory(r) for r in rows]

# ---- Memory Summaries ----

def get_memory_summary(chat_id, char_id, scope="autobiographical"):
    row = q("SELECT * FROM memory_summaries WHERE chat_id=? AND char_id=? AND scope=?", (chat_id, char_id, scope), one=True)
    if not row:
        return {"scope": scope, "start_turn_idx": 0, "end_turn_idx": 0, "summary": "",
                "key_phrases": [], "unresolved_threads": [], "updated": None}
    return {"scope": row["scope"], "start_turn_idx": row["start_turn_idx"], "end_turn_idx": row["end_turn_idx"],
            "summary": row["summary"], "key_phrases": _json_list(row["key_phrases"]),
            "unresolved_threads": _json_list(row["unresolved_threads"]), "updated": row["updated"]}

def _summary_retrieval_text(summary, key_phrases, unresolved_threads):
    return "\n".join([summary or "", ", ".join(key_phrases or []),
                      "\n".join(unresolved_threads or [])])

def save_memory_summary(chat_id, char_id, summary, *, scope="autobiographical", start_turn_idx=0,
                        end_turn_idx=0, key_phrases=None, unresolved_threads=None,
                        embedding=None, embedding_model=None, embedding_dim=None):
    key_phrases = key_phrases or []
    unresolved_threads = unresolved_threads or []
    # Checkpoint/export restore passes the previously stored vector back
    # in verbatim (raw bytes) so a restore never re-embeds -- every
    # normal caller omits it and embeds exactly as before.
    if embedding is None or not embedding_model:
        retrieval_text = _summary_retrieval_text(summary, key_phrases, unresolved_threads)
        embedded = embed_texts_meta([retrieval_text])
        embedding = _blob(embedded.vectors[0])
        embedding_model = embedded.model_key
        embedding_dim = embedded.dimensions
    qi("""INSERT INTO memory_summaries(chat_id,char_id,scope,start_turn_idx,end_turn_idx,summary,
        key_phrases,unresolved_threads,embedding,embedding_model,embedding_dim,updated)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(chat_id,char_id,scope) DO UPDATE SET
        start_turn_idx=excluded.start_turn_idx, end_turn_idx=excluded.end_turn_idx,
        summary=excluded.summary, key_phrases=excluded.key_phrases,
        unresolved_threads=excluded.unresolved_threads, embedding=excluded.embedding,
        embedding_model=excluded.embedding_model, embedding_dim=excluded.embedding_dim,
        updated=excluded.updated""",
       (chat_id, char_id, scope, start_turn_idx, end_turn_idx, summary or "",
        json.dumps(key_phrases, ensure_ascii=False), json.dumps(unresolved_threads, ensure_ascii=False),
        embedding, embedding_model, embedding_dim, time.time()))

def _with_reading(mem):
    """Attach the character's own later re-reading, where they have made one.

    The memory itself is handed over UNCHANGED -- content, gist, provenance,
    salience all as recorded -- and the revision travels beside it under its
    own key. That separation is the feature: the character still remembers
    seeing what they saw, and also remembers having since decided it meant
    something else. Collapsing the two would either erase the experience or
    hide the correction, and a mind that has been deceived holds both.

    The key is phrased as the character's own voice, matching the
    `it_comes_back_to_me` / `i_suspect` precedent -- epistemic status carried
    by the key rather than by prose a model can drop.
    """
    dispute = mem.get("disputed") if isinstance(mem, dict) else None
    if not dispute:
        return mem
    out = dict(mem)
    out.pop("disputed", None)
    out["i_now_read_this_differently"] = dispute.get("reading") or ""
    if dispute.get("count", 0) > 1:
        out["times_i_have_reconsidered_it"] = int(dispute["count"])
    return out


def build_character_memory_context(chat_id, char_id, current_turn_idx, current_view, active_state, *,
                                   recent_turns=4, recall_limit=_RECALL_LIMIT, here=None,
                                   in_sight=None):
    active_state = active_state or {}
    recent = recent_memory_buffer(chat_id, char_id, current_turn_idx, turns=recent_turns, limit=12)
    recent_ids = {m["id"] for m in recent}
    summary = get_memory_summary(chat_id, char_id)
    # P8: the other two epistemic classes travel as their own labelled fields
    # rather than being melted into the first-hand paragraph. A character must
    # be able to tell what they saw from what they were told from what they
    # worked out -- collapsing them is the same layer-collapse the engine
    # polices between minds, happening inside one.
    provenance_summaries = {}
    for scope, _field, label in _SUMMARY_SCOPES:
        if scope == SUMMARY_SCOPE_FIRSTHAND:
            continue
        text = str(get_memory_summary(chat_id, char_id, scope).get("summary") or "").strip()
        if text:
            provenance_summaries[label] = text
    # The beat is the query; what the character BRINGS to it travels beside it
    # as aspects, each with its own ranking. Concatenated, they did nothing:
    # the view runs a median ~1,015 characters and a mood fragment 10-60, so
    # the combined vector sat at cosine 0.994 to the view alone and the mood
    # reached recall only through stray shared n-grams. See search_memories.
    query_text = str(current_view or "").strip()
    aspects = [
        ("what you are trying to do", str(active_state.get("goal") or "")),
        ("how you are feeling", str(active_state.get("mood") or "")),
        ("what is still unsettled",
         " ".join(summary.get("unresolved_threads") or [])),
    ]
    if not query_text:
        # No perception this beat (a character gated out of the scene): fall
        # back to the aspects as the query rather than retrieving on "".
        query_text = " ".join(t for _l, t in aspects if t)
    # current_turn_idx is required here (recent_memory_buffer arithmetic above
    # would already fail on None), so search_memories' F1 turn cutoff always
    # fires on this path -- the character context can never see turn N's own
    # committed memories while deciding turn N, reroll or not.
    recalled = search_memories(chat_id, char_id, query_text, k=recall_limit,
                               include_archived=True, current_turn_idx=current_turn_idx,
                               chronological=True, here=here, in_sight=in_sight,
                               aspects=aspects)
    recalled = [m for m in recalled if m["id"] not in recent_ids]
    return {
        "working_memory": {
            # A citable id for the PRESENT beat. Without one, the only ids in
            # this payload belong to memory rows -- and recent_memory_buffer
            # deliberately excludes the current turn (audit #10), so every
            # real event_id here is from an EARLIER turn. A character asked to
            # cite evidence could therefore only ever cite the past, and did:
            # across one 61-turn chat, observations_used cited a previous
            # turn 15 times and the current beat zero times, which is why the
            # character kept answering the line before the one just spoken.
            "event_id": "current",
            "current_perception": current_view or "",
            "current_mood": active_state.get("mood") or "neutral",
            "current_goal": active_state.get("goal") or "",
            "active_concerns": list(dict.fromkeys([
                *[str(item) for item in (active_state.get("active_concerns") or [])
                  if str(item).strip()],
                *[str(item) for item in (summary.get("unresolved_threads") or [])
                  if str(item).strip()],
            ]))[:6],
        },
        "recent_episodes": [_with_reading(m) for m in recent],
        "recalled_old_memories": [_with_reading(m) for m in recalled],
        # First-hand only. What reached this character through someone else's
        # account, and what they worked out for themselves, are carried
        # separately below and must not be folded in here.
        "autobiographical_summary": summary.get("summary") or "",
        "summary_key_phrases": summary.get("key_phrases") or [],
        "unresolved_threads": summary.get("unresolved_threads") or [],
        **provenance_summaries,
    }

def consolidate_character_memory(chat_id, char_id, *, through_turn_idx=None, archive_old=True,
                                 viewer_frame_id=_UNSET):
    char = q("SELECT name FROM characters WHERE id=?", (char_id,), one=True)
    if not char:
        raise ValueError("Character not found")
    old_summary = get_memory_summary(chat_id, char_id)
    # Everything up to old_summary["end_turn_idx"] is already folded into
    # old_summary (sent below as previous_summary) and archived rows were
    # already folded into some still-earlier summary -- resending either
    # gets the consolidator no new information but made the payload (and
    # its cost) grow without bound across a long chat's repeated
    # consolidation passes, since every call previously re-sent the
    # complete history since turn 0 regardless of what had already been
    # summarized.
    # turn_idx is GLOBAL play order shared by every frame, not per-era -- so
    # without the seam's frame filter, memories formed during a
    # flash-forward/-back would be folded into the singleton autobiographical
    # summary the moment play returns to the present and turn_idx catches up,
    # handing a character knowledge of events they have not diegetically
    # reached. `before_turn_idx` is exclusive and this window is inclusive of
    # `through_turn_idx`, hence the +1.
    rows = visible_memory_rows(
        chat_id, char_id,
        before_turn_idx=(None if through_turn_idx is None
                         else int(through_turn_idx) + 1),
        viewer_frame_id=viewer_frame_id,
        include_archived=False,
        since_turn_idx=(old_summary.get("end_turn_idx") or 0) + 1,
        require_turn_idx=True,
    )
    rows.sort(key=lambda r: (r["turn_idx"], r["id"]))
    memories = [_row_memory(r) for r in rows]
    if not memories:
        return old_summary
    payload = {
        "character": char["name"],
        "previous_summary": old_summary,
        "memories_chronological": [
            {"id": m["id"], "turn_idx": m["turn_idx"], "category": m["category"],
             "provenance": m["provenance"], "salience": m["salience"], "confidence": m["confidence"],
             "gist": m["gist"], "details": m["content"], "key_phrases": m["key_phrases"],
             "entities": m["entities"], "location": m["location"], "emotional_context": m["emotional_context"]}
            for m in memories
        ],
    }
    raw = chat_complete("utility", get_prompt("memory_consolidate"),
                        json.dumps(payload, ensure_ascii=False), temperature=0.1, max_tokens=5000)
    try:
        result = json.loads(raw)
    except Exception:
        match = re.search(r"\{.*\}", raw or "", re.S)
        if not match:
            raise RuntimeError("Memory consolidator returned invalid JSON")
        result = json.loads(re.sub(r",\s*([}\]])", r"\1", match.group(0)))
    start_turn = min(m["turn_idx"] for m in memories)
    end_turn = max(m["turn_idx"] for m in memories)
    # One row per epistemic class. The first-hand row is written
    # unconditionally, even when this window produced nothing first-hand,
    # because maybe_consolidate_character_memory reads ITS end_turn_idx as the
    # cursor -- skip it on a hearsay-only window and the same memories
    # re-consolidate forever.
    present = {summary_scope_for(m.get("provenance")) for m in memories}
    for scope, field, _label in _SUMMARY_SCOPES:
        text = str(result.get(field) or "").strip()
        if scope != SUMMARY_SCOPE_FIRSTHAND and not text and scope not in present:
            continue
        save_memory_summary(
            chat_id, char_id, text, scope=scope,
            start_turn_idx=start_turn, end_turn_idx=end_turn,
            key_phrases=(result.get("key_phrases") or []
                         if scope == SUMMARY_SCOPE_FIRSTHAND else []),
            unresolved_threads=(result.get("unresolved_threads") or []
                                if scope == SUMMARY_SCOPE_FIRSTHAND else []))
    if archive_old:
        cutoff = max(start_turn, end_turn - 12)
        # Archive ONLY memories that were part of THIS (frame-visible)
        # consolidation set. turn_idx is global play order, so the old
        # blanket UPDATE also archived another era's memories that were
        # correctly excluded from this summary (is_memory_visible filtered
        # them out of `memories`) and never folded into any summary.
        archivable = [
            m["id"] for m in memories
            if m.get("id") is not None
            and (m.get("turn_idx") or 0) < cutoff
            # The HIGHER of the two. A memory that turned out to matter is
            # not archived on the strength of how ordinary it looked at the
            # time -- which is the entire reason the two numbers are separate.
            and max(float(m.get("salience") or 0),
                    effective_importance(m)) < 0.72
            and m.get("category") not in ("promise", "relationship", "intention")
        ]
        if archivable:
            marks = ",".join("?" for _ in archivable)
            qi(f"UPDATE memories SET archived=1 WHERE id IN ({marks})", tuple(archivable))
    return {**get_memory_summary(chat_id, char_id), "stable_facts": result.get("stable_facts") or [], "memory_count": len(memories)}

def maybe_consolidate_character_memory(chat_id, char_id, current_turn_idx, *, frame_id=_UNSET):
    # A singleton per-character summary has nowhere to put "as of the
    # present era" vs. "as of the future flash-forward" -- consolidating
    # outside the present would permanently blend eras into one
    # autobiography with no way to un-blend it. Frozen to present only;
    # a frame visited away from the present just accumulates raw memories
    # (still correctly filtered by is_memory_visible) until play returns.
    #
    # frame_id is accepted explicitly (falling back to the ambient
    # contextvar only when the caller doesn't have it on hand) rather
    # than always trusting the contextvar, because the one real caller
    # that matters -- commit.py's per-character consolidation loop --
    # runs each character's check on a concurrent.futures.ThreadPoolExecutor
    # worker thread, and THAT does not propagate contextvars the way
    # agents/runtime.py's own bespoke thread-spawning helpers do (they
    # explicitly contextvars.copy_context() first). Reading the
    # contextvar from inside the worker thread would silently see the
    # default None on every call regardless of which frame's turn is
    # actually being committed, defeating this guard exactly the way
    # app.py's old streaming path defeated active_frame_id.
    fid = _active_frame_id.get() if frame_id is _UNSET else frame_id
    if fid is not None:
        return None
    summary = get_memory_summary(chat_id, char_id)
    last_turn = summary.get("end_turn_idx") or 0
    count = q("SELECT COUNT(*) AS c FROM memories WHERE chat_id=? AND char_id=? AND archived=0 AND turn_idx>?",
              (chat_id, char_id, last_turn), one=True)["c"]
    if current_turn_idx - last_turn < 10 and count < 40:
        return None
    return consolidate_character_memory(chat_id, char_id, through_turn_idx=current_turn_idx,
                                        viewer_frame_id=fid)

# ---- Snapshot dump/restore ----

def vector_address(char_id, content) -> str:
    """The string form of `_memory_vector_key`, for the `memory_vectors.vkey`
    column. Built FROM that function rather than beside it, so the checkpoint
    store and `rebuild_checkpoint_embeddings` can never disagree about what
    identifies a vector."""
    char_part, digest = _memory_vector_key(char_id, content)
    return "%s:%s" % (char_part, digest)


def put_memory_vector(vkey, embedding, cue_embedding, model, dim):
    """File a vector pair under its content address. Idempotent, append-only.

    `INSERT OR IGNORE`, not upsert: the address IS the content, so a second
    write for the same key is the same vector. If it somehow is not -- a model
    change without a rekey -- the FIRST one wins, because that is the one the
    existing checkpoints were written against and a rollback has to reproduce
    what it saved, not what is current.
    """
    if not vkey or embedding is None or cue_embedding is None:
        return False
    qi("INSERT OR IGNORE INTO memory_vectors"
       "(vkey,embedding,cue_embedding,embedding_model,embedding_dim,created) "
       "VALUES(?,?,?,?,?,?)",
       (vkey, embedding, cue_embedding, model or "", dim, time.time()))
    return True


def get_memory_vectors(vkeys):
    """{vkey: (embedding_blob, cue_blob, model, dim)} for the keys that exist."""
    keys = [str(k) for k in (vkeys or []) if str(k or "").strip()]
    if not keys:
        return {}
    out = {}
    # Chunked: a long story's restore can ask for hundreds of keys at once and
    # SQLite caps host parameters.
    for i in range(0, len(keys), 400):
        part = keys[i:i + 400]
        marks = ",".join("?" for _ in part)
        for r in q("SELECT * FROM memory_vectors WHERE vkey IN (%s)" % marks,
                   tuple(part)):
            out[r["vkey"]] = (r["embedding"], r["cue_embedding"],
                              r["embedding_model"], r["embedding_dim"])
    return out


def dump_memory_vectors(vkeys):
    """Content-addressed vectors, base64'd, for a portable archive."""
    out = []
    for vkey, (full, cue, model, dim) in sorted(get_memory_vectors(vkeys).items()):
        out.append({"vkey": vkey, "embedding": _blob_to_b64(full),
                    "cue_embedding": _blob_to_b64(cue),
                    "embedding_model": model, "embedding_dim": dim})
    return out


def restore_memory_vectors(entries):
    """File an archive's vectors into this database's store.

    Additive and idempotent -- the address is the content, so an entry that is
    already here is the same vector. Never deletes: another chat's checkpoints
    may reference the same address.
    """
    n = 0
    with transaction():
        for e in entries or []:
            if not isinstance(e, dict):
                continue
            if put_memory_vector(e.get("vkey"), _b64_to_blob(e.get("embedding")),
                                 _b64_to_blob(e.get("cue_embedding")),
                                 e.get("embedding_model"), e.get("embedding_dim")):
                n += 1
    return n


def dump_chat_memories(chat_id, *, inline_vectors=True):
    """The chat's memory bank, for a checkpoint or a portable archive.

    `inline_vectors` is the difference between the two callers, and it matters:

    * a CHECKPOINT lives in the same database as the vector store, so it can
      reference vectors by content address and carry none of the payload.
      That is the whole compaction -- the two vector fields are 96.9% of a
      checkpoint, re-stored on every turn for the life of the story.
    * a portable ARCHIVE is imported into a DIFFERENT database, where no such
      store exists, so it must carry the vectors with it or the import
      re-embeds the whole bank (expensive, and a provider hiccup during it
      silently downgrades every vector to the crc32 fallback).

    The restore path accepts either shape, so an old checkpoint written before
    this existed still restores from its inline vectors unchanged.
    """
    rows = q("SELECT * FROM memories WHERE chat_id=? ORDER BY CASE WHEN turn_idx IS NULL THEN 1 ELSE 0 END, turn_idx, id", (chat_id,))
    if not inline_vectors:
        with transaction():
            for r in rows:
                if r["embedding"] is None or r["cue_embedding"] is None:
                    continue
                put_memory_vector(
                    vector_address(r["char_id"], r["content"]),
                    r["embedding"], r["cue_embedding"],
                    r["embedding_model"], r["embedding_dim"])
    return [
        {"char_id": r["char_id"], "turn_id": r["turn_id"], "turn_idx": r["turn_idx"],
         "frame_id": r["frame_id"],
         "kind": r["kind"], "category": r["category"], "provenance": r["provenance"],
         "salience": r["salience"], "content": r["content"], "gist": r["gist"],
         "key_phrases": _json_list(r["key_phrases"]), "entities": _json_list(r["entities"]),
         "location": r["location"], "emotional_context": r["emotional_context"],
         "valence": r["valence"], "arousal": r["arousal"], "confidence": r["confidence"],
         "archived": bool(r["archived"]), "event_key": r["event_key"],
         "importance": r["importance"], "disputed": r["disputed"] or "",
         # Stored vectors travel with the dump so restore can put them
         # back byte-identically instead of re-embedding the entire
         # memory bank on every checkpoint restore (expensive, and a
         # provider hiccup during it silently downgrades every vector
         # to the crc32 fallback, which then scores 0.0 forever).
         **({"embedding": _blob_to_b64(r["embedding"]),
             "cue_embedding": _blob_to_b64(r["cue_embedding"])}
            if inline_vectors else
            {"vkey": vector_address(r["char_id"], r["content"])}),
         "embedding_model": r["embedding_model"],
         "embedding_dim": r["embedding_dim"]}
        for r in rows
    ]

@dataclass
class _StoredEmbeddingMeta:
    """Stands in for providers.EmbeddingBatch when the vectors came out
    of a dump instead of a live embedding call -- _upsert_memory only
    reads model_key/dimensions off it."""
    model_key: str
    dimensions: int

def prepare_chat_memory_restore(chat_id, mems):
    """Build a write-free restore plan for restore_chat_memories.

    All normalization and any embedding calls happen here, BEFORE any
    row is touched, so apply_chat_memory_restore is pure writes and can
    run inside an outer transaction (checkpoint restore) without a
    remote provider call ever holding SQLite's write lock. Dumps that
    carry their stored vectors (see dump_chat_memories) are restored
    verbatim; only legacy dumps without them are re-embedded."""
    entries = []
    legacy_items = []
    # One lookup for every address in the dump, before the loop: a restore
    # should not issue a query per memory.
    vector_store = get_memory_vectors(
        [m.get("vkey") for m in (mems or []) if isinstance(m, dict) and m.get("vkey")])
    for m in mems or []:
        if not m.get("content"):
            continue
        item = {
            "chat_id": chat_id, "char_id": m.get("char_id"), "turn_id": m.get("turn_id"),
            "turn_idx": m.get("turn_idx"), "kind": m.get("kind", "episodic"),
            # Preserved verbatim, never re-stamped with whatever frame
            # happens to be active during the restore -- a checkpoint
            # restore means "put it back exactly as it was," and a
            # branch clone is expected to have already remapped this to
            # the new chat's own frame ids before calling this function.
            "frame_id": m.get("frame_id"),
            "category": m.get("category"), "provenance": m.get("provenance", "witnessed"),
            "salience": m.get("salience", 0.5), "content": m["content"],
            "gist": m.get("gist"), "key_phrases": m.get("key_phrases"),
            "entities": m.get("entities"), "location": m.get("location", ""),
            "emotional_context": m.get("emotional_context", ""),
            "valence": m.get("valence", 0.0), "arousal": m.get("arousal", 0.0),
            "confidence": m.get("confidence", 1.0), "event_key": m.get("event_key", ""),
            # Carried verbatim. A revised importance and a recorded re-reading
            # are things the character earned; a rollback restores the bank as
            # it was, and neither is re-derivable from the row's own text.
            "importance": m.get("importance"),
            "disputed": m.get("disputed") or "",
        }
        full_blob = _b64_to_blob(m.get("embedding"))
        cue_blob = _b64_to_blob(m.get("cue_embedding"))
        model = m.get("embedding_model") or ""
        # A compacted checkpoint carries a content address instead of the
        # payload. Resolve it here, in the same read-only phase the inline
        # shape is handled in, so the write phase stays identical for both.
        if (full_blob is None or cue_blob is None) and m.get("vkey"):
            hit = vector_store.get(m["vkey"])
            if hit:
                full_blob, cue_blob = hit[0], hit[1]
                model = model or hit[2]
                if not m.get("embedding_dim"):
                    m = {**m, "embedding_dim": hit[3]}
        if full_blob is not None and cue_blob is not None and model:
            full_vec = _vec(full_blob)
            cue_vec = _vec(cue_blob)
            dim = m.get("embedding_dim") or len(full_vec)
            entries.append({
                "mode": "direct", "source": m, "data": prepare_memory(**item),
                "full_vec": full_vec, "cue_vec": cue_vec,
                "meta": _StoredEmbeddingMeta(model, int(dim)),
            })
        else:
            entries.append({"mode": "legacy", "source": m})
            legacy_items.append(item)
    legacy_batch = prepare_memories_batch(legacy_items) if legacy_items else None
    return {"entries": entries, "legacy_batch": legacy_batch}

def apply_chat_memory_restore(chat_id, plan):
    """Write phase of restore_chat_memories: delete-and-reinsert the
    chat's memory bank from a plan built by prepare_chat_memory_restore.
    One transaction, no provider calls; FTS rows are maintained through
    the exact same _upsert_memory path the normal add path uses."""
    entries = plan.get("entries") or []
    legacy_batch = plan.get("legacy_batch")
    legacy_prepared = (legacy_batch or {}).get("prepared") or []
    legacy_embedded = (legacy_batch or {}).get("embedded")
    legacy_count = sum(1 for e in entries if e["mode"] == "legacy")
    if legacy_count and (legacy_embedded is None
                         or len(legacy_embedded.vectors) != legacy_count * 2
                         or len(legacy_prepared) != legacy_count):
        raise ValueError("Invalid prepared memory embedding batch")
    with transaction():
        for r in q("SELECT id FROM memories WHERE chat_id=?", (chat_id,)):
            _delete_memory_fts(r["id"])
        qi("DELETE FROM memories WHERE chat_id=?", (chat_id,))
        li = 0
        for entry in entries:
            if entry["mode"] == "direct":
                mid = _upsert_memory(entry["data"], entry["full_vec"],
                                     entry["cue_vec"], entry["meta"])
            else:
                mid = _upsert_memory(legacy_prepared[li],
                                     legacy_embedded.vectors[li * 2],
                                     legacy_embedded.vectors[li * 2 + 1],
                                     legacy_embedded)
                li += 1
            if entry["source"].get("archived"):
                qi("UPDATE memories SET archived=1 WHERE id=?", (mid,))

def restore_chat_memories(chat_id, mems):
    apply_chat_memory_restore(chat_id, prepare_chat_memory_restore(chat_id, mems))

def dump_character_memories(chat_id, char_id):
    """Same shape as dump_chat_memories, but scoped to one character --
    the unit a user actually wants to carry around (export a character's
    accumulated memory bank, import it into a different story with the
    same character, or back it up separately from the whole chat)."""
    rows = q(
        "SELECT * FROM memories WHERE chat_id=? AND char_id=? "
        "ORDER BY CASE WHEN turn_idx IS NULL THEN 1 ELSE 0 END, turn_idx, id",
        (chat_id, char_id),
    )
    return [
        {"turn_idx": r["turn_idx"],
         "kind": r["kind"], "category": r["category"], "provenance": r["provenance"],
         "salience": r["salience"], "content": r["content"], "gist": r["gist"],
         "key_phrases": _json_list(r["key_phrases"]), "entities": _json_list(r["entities"]),
         "location": r["location"], "emotional_context": r["emotional_context"],
         "valence": r["valence"], "arousal": r["arousal"], "confidence": r["confidence"],
         "archived": bool(r["archived"]), "event_key": r["event_key"],
         "importance": r["importance"], "disputed": r["disputed"] or ""}
        for r in rows
    ]

def import_character_memories(chat_id, char_id, memories):
    """Additive import for one character's memories -- unlike
    restore_chat_memories (which wipes and replaces, only ever used for
    checkpoint restore), this never deletes anything: it's for a user
    bringing a character's memory bank INTO a chat, possibly a different
    one than it was exported from. turn_id/turn_idx are always dropped
    even on a same-chat re-import, since an old export's turn numbering
    can't be trusted to still line up with this chat's actual turns --
    the same treatment already used for background-promotion memory
    seeds, which also arrive with no real turn to anchor to."""
    prepared = []
    for m in memories or []:
        content = str(m.get("content") or "").strip()
        if not content:
            continue
        prepared.append({
            "chat_id": chat_id, "char_id": char_id, "turn_id": None, "turn_idx": None,
            "kind": m.get("kind", "episodic"), "category": m.get("category"),
            "provenance": m.get("provenance", "told"),
            "salience": m.get("salience", 0.5), "content": content,
            "gist": m.get("gist"), "key_phrases": m.get("key_phrases"),
            "entities": m.get("entities"), "location": m.get("location", ""),
            "emotional_context": m.get("emotional_context", ""),
            "valence": m.get("valence", 0.0), "arousal": m.get("arousal", 0.0),
            "confidence": m.get("confidence", 1.0), "event_key": "",
            # Both travel with a portable character bank: they are the
            # character's own history with these memories, not facts about the
            # chat they were formed in.
            "importance": m.get("importance"),
            "disputed": m.get("disputed") or "",
        })
    return len(add_memories_batch(prepared))

def dump_memory_summaries(chat_id):
    return [
        {"char_id": r["char_id"], "scope": r["scope"], "start_turn_idx": r["start_turn_idx"],
         "end_turn_idx": r["end_turn_idx"], "summary": r["summary"],
         "key_phrases": _json_list(r["key_phrases"]), "unresolved_threads": _json_list(r["unresolved_threads"]),
         "updated": r["updated"],
         # Same rationale as dump_chat_memories: carry the stored vector
         # so restore is verbatim instead of a provider round trip.
         "embedding": _blob_to_b64(r["embedding"]),
         "embedding_model": r["embedding_model"],
         "embedding_dim": r["embedding_dim"]}
        for r in q("SELECT * FROM memory_summaries WHERE chat_id=? ORDER BY char_id, scope", (chat_id,))
    ]

def prepare_memory_summary_restore(summaries):
    """Embedding phase of restore_memory_summaries: resolves each
    summary's vector (verbatim from the dump when present, one embed
    call per legacy item otherwise) with zero writes, so the apply
    phase never makes a provider call while holding the write lock."""
    prepared = []
    for item in summaries or []:
        emb = _b64_to_blob(item.get("embedding"))
        model = item.get("embedding_model") or ""
        dim = item.get("embedding_dim")
        if emb is None or not model:
            embedded = embed_texts_meta([_summary_retrieval_text(
                item.get("summary"), item.get("key_phrases") or [],
                item.get("unresolved_threads") or [])])
            emb = _blob(embedded.vectors[0])
            model = embedded.model_key
            dim = embedded.dimensions
        prepared.append((item, emb, model, dim))
    return prepared

def apply_memory_summary_restore(chat_id, prepared):
    with transaction():
        qi("DELETE FROM memory_summaries WHERE chat_id=?", (chat_id,))
        for item, emb, model, dim in prepared:
            save_memory_summary(chat_id, item["char_id"], item.get("summary", ""),
                                scope=item.get("scope", "autobiographical"),
                                start_turn_idx=item.get("start_turn_idx", 0),
                                end_turn_idx=item.get("end_turn_idx", 0),
                                key_phrases=item.get("key_phrases") or [],
                                unresolved_threads=item.get("unresolved_threads") or [],
                                embedding=emb, embedding_model=model, embedding_dim=dim)

def restore_memory_summaries(chat_id, summaries):
    apply_memory_summary_restore(chat_id, prepare_memory_summary_restore(summaries))

def dump_lorebook(lb_id):
    return [
        {
            "entry_uid": r["entry_uid"], "keys": r["keys"], "content": r["content"],
            "category": r["category"] or "other", "locked": r["canon_locked"],
            "turn_added": r["turn_added"], "title": r["title"],
            "knowledge_tag": r["knowledge_tag"], "knowledge_range": r["knowledge_range"],
            "knowledge_locations": r["knowledge_locations"],
            "importance": r["importance"], "aliases": r["aliases"],
            "scope": r["scope"], "relations": r["relations"],
            "source_notes": r["source_notes"],
            # Stored vector travels with the dump so restore/import can
            # reuse it verbatim instead of re-embedding every entry.
            "embedding": _blob_to_b64(r["embedding"]),
        }
        for r in q("SELECT * FROM lore_entries WHERE lorebook_id=? ORDER BY id", (lb_id,))
    ]

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
    for link in links or []:
        source = old_to_new.get(link.get("source_book_id"))
        target = old_to_new.get(link.get("target_book_id"))

        if source is None or target is None:
            continue
        if source == target:
            continue

        source_row = q("SELECT chat_id FROM lorebooks WHERE id=?", (source,), one=True)
        target_row = q("SELECT chat_id FROM lorebooks WHERE id=?", (target,), one=True)

        if not source_row or not target_row:
            continue
        if source_row["chat_id"] != chat_id:
            continue
        if target_row["chat_id"] != chat_id:
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
        except Exception:
            pass

def restore_lorebook(lb_id, entries):
    import hashlib, uuid

    def legacy_entry_uid(entry):
        raw = "\x1f".join([
            str(entry.get("keys") or "").strip().casefold(),
            re.sub(r"\s+", " ", str(entry.get("content") or "").strip().casefold()),
            str(entry.get("category") or "other"),
        ])
        return f"legacy_entry_{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"

    incoming = [entry for entry in (entries or []) if isinstance(entry, dict) and entry.get("content")]
    incoming_uids = set()

    # Resolve every entry's embedding up front, before any row is
    # touched: entries dumped by dump_lorebook carry their stored vector
    # (reused verbatim -- the snapshot's vector matches the snapshot's
    # keys/content by construction), and only legacy dumps without one
    # are re-embedded, in a single batch so no per-entry provider call
    # ever runs between writes.
    entry_vecs = {}
    legacy_entries = []
    for entry in incoming:
        raw = entry.get("embedding")
        if isinstance(raw, str):
            raw = _b64_to_blob(raw)
        elif not isinstance(raw, (bytes, bytearray, memoryview)):
            raw = None
        vec = _vec(bytes(raw)) if raw and len(raw) % 4 == 0 else None
        if vec is None:
            legacy_entries.append(entry)
        entry_vecs[id(entry)] = vec
    if legacy_entries:
        texts = [(e.get("keys") or "") + " " + (e.get("content") or "") for e in legacy_entries]
        for e, vec in zip(legacy_entries, embed_texts(texts)):
            entry_vecs[id(e)] = vec

    for entry in incoming:
        uid = entry.get("entry_uid") or legacy_entry_uid(entry)
        existing = q("SELECT id FROM lore_entries WHERE lorebook_id=? AND entry_uid=?", (lb_id, uid), one=True)
        if existing:
            incoming_uids.add(uid)
            update_lore(existing["id"], entry.get("keys", ""), entry["content"],
                        entry.get("category", "other"), title=entry.get("title"),
                        knowledge_tag=entry.get("knowledge_tag"),
                        knowledge_range=entry.get("knowledge_range"),
                        knowledge_locations=_storage_json(entry.get("knowledge_locations")),
                        importance=entry.get("importance", 0.5),
                        aliases=entry.get("aliases", []),
                        scope=entry.get("scope", {}),
                        relations=entry.get("relations", {}),
                        source_notes=entry.get("source_notes", ""),
                        embedding=entry_vecs.get(id(entry)))
            qi("UPDATE lore_entries SET canon_locked=?, turn_added=? WHERE id=?",
               (int(bool(entry.get("locked", 0))), entry.get("turn_added"), existing["id"]))
            continue

        # UID might exist in a different lorebook (global UNIQUE constraint)
        global_existing = q("SELECT id FROM lore_entries WHERE entry_uid=?", (uid,), one=True)
        if global_existing:
            uid = f"entry_{uuid.uuid4().hex}"

        incoming_uids.add(uid)
        add_lore(lb_id, entry.get("keys", ""), entry["content"],
                 turn_added=entry.get("turn_added"), locked=int(bool(entry.get("locked", 0))),
                 category=entry.get("category", "other"), title=entry.get("title"),
                 knowledge_tag=entry.get("knowledge_tag"), knowledge_range=entry.get("knowledge_range"),
                 knowledge_locations=_storage_json(entry.get("knowledge_locations")),
                 entry_uid=uid,
                 importance=entry.get("importance", 0.5),
                 aliases=entry.get("aliases", []),
                 scope=entry.get("scope", {}),
                 relations=entry.get("relations", {}),
                 source_notes=entry.get("source_notes", ""),
                 embedding=entry_vecs.get(id(entry)))

    for row in q("SELECT id,entry_uid FROM lore_entries WHERE lorebook_id=?", (lb_id,)):
        if row["entry_uid"] not in incoming_uids:
            delete_lore(row["id"])

# ---- Lorebook Entries ----

def add_lore(lorebook_id, keys, content, turn_added=None, locked=0, category="other",
             title=None, knowledge_tag=None, knowledge_range=None,
             knowledge_locations=None, entry_uid=None,
             importance=0.5, aliases=None, scope=None, relations=None,
             source_notes="", embedding=None):
    import uuid
    entry_uid = entry_uid or f"entry_{uuid.uuid4().hex}"
    vec = embedding
    if vec is None:
        vec = embed_texts([(keys or "") + " " + (content or "")])[0]
    return qi("""INSERT INTO lore_entries(
            lorebook_id, keys, content, category, canon_locked, turn_added,
            embedding, title, knowledge_tag, knowledge_range,
            knowledge_locations, entry_uid, importance, aliases, scope,
            relations, source_notes
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (lorebook_id, keys or "", content or "",
         category if category in LORE_CATEGORIES else "other",
         locked, turn_added, _blob(vec), title, knowledge_tag,
         knowledge_range, _storage_json(knowledge_locations), entry_uid,
         float(importance),
         _storage_json(aliases or []),
         _storage_json(scope or {}),
         _storage_json(relations or {}),
         source_notes))

def update_lore(entry_id, keys, content, category=None, title=None,
                knowledge_tag=None, knowledge_range=None, knowledge_locations=None,
                importance=None, aliases=None, scope=None, relations=None,
                source_notes=None, embedding=None):
    vec = embedding
    if vec is None:
        vec = embed_texts([(keys or "") + " " + (content or "")])[0]
    fields = ["keys=?", "content=?", "embedding=?", "title=?",
              "knowledge_tag=?", "knowledge_range=?", "knowledge_locations=?"]
    values = [keys or "", content or "", _blob(vec), title,
              knowledge_tag, knowledge_range, knowledge_locations]
    
    if category and category in LORE_CATEGORIES:
        fields.append("category=?")
        values.append(category)
    if importance is not None:
        fields.append("importance=?")
        values.append(float(importance))
    if aliases is not None:
        fields.append("aliases=?")
        values.append(_storage_json(aliases))
    if scope is not None:
        fields.append("scope=?")
        values.append(_storage_json(scope))
    if relations is not None:
        fields.append("relations=?")
        values.append(_storage_json(relations))
    if source_notes is not None:
        fields.append("source_notes=?")
        values.append(source_notes)
    
    values.append(entry_id)
    qi(f"UPDATE lore_entries SET {','.join(fields)} WHERE id=?", tuple(values))

def duplicate_lorebook_tree_for_chat(root_id, chat_id, include_links=True):
    """Duplicate a lorebook subtree for a chat, preserving hierarchy and links."""
    book_ids = lorebook_descendants(root_id)
    if not book_ids:
        return {}
    
    old_to_new = {}
    
    # Pass 1: Create all books
    for old_id in book_ids:
        src = q("SELECT * FROM lorebooks WHERE id=?", (old_id,), one=True)
        if not src:
            continue
        new_id = qi("""INSERT INTO lorebooks(name,chat_id,origin_id,book_type,summary,
                      parent_id,scope_world_id,scope_location_id,inheritance_mode,sort_order,
                      resource_uid)
                      VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                    ((src["name"] or "book") + " (chat copy)", chat_id, old_id,
                     src["book_type"] or "general", src["summary"] or "",
                     src["parent_id"], src["scope_world_id"],
                     src["scope_location_id"], src["inheritance_mode"] or "inherit",
                     src["sort_order"] or 0,
                     None))
        old_to_new[old_id] = new_id
        for e in q("SELECT * FROM lore_entries WHERE lorebook_id=?", (old_id,)):
            add_lore(new_id, e["keys"], e["content"], e["turn_added"], e["canon_locked"],
                     e["category"] or "other", title=e["title"],
                     knowledge_tag=e["knowledge_tag"],
                     knowledge_range=e["knowledge_range"],
                     knowledge_locations=e["knowledge_locations"],
                     importance=e["importance"],
                     aliases=_json_list(e["aliases"]),
                     scope=json.loads(e["scope"] or "{}"),
                     relations=json.loads(e["relations"] or "{}"),
                     source_notes=e["source_notes"],
                     # The clone's keys/content are identical to the
                     # source row's, so its stored vector is reused
                     # verbatim instead of re-embedding every entry
                     # (falls back to embedding only if the source row
                     # never had a vector).
                     embedding=_vec(e["embedding"]))
    
    # Pass 2: Remap parent IDs
    for old_id, new_id in old_to_new.items():
        src = q("SELECT parent_id FROM lorebooks WHERE id=?", (old_id,), one=True)
        if src and src["parent_id"] and src["parent_id"] in old_to_new:
            qi("UPDATE lorebooks SET parent_id=? WHERE id=?",
               (old_to_new[src["parent_id"]], new_id))
        elif src and src["parent_id"]:
            # Parent was outside the subtree, null it out
            qi("UPDATE lorebooks SET parent_id=NULL WHERE id=?", (new_id,))
    
    # Pass 3: Copy links
    if include_links:
        links = dump_lorebook_links(book_ids)
        restore_lorebook_links(chat_id, old_to_new, links)
    
    return old_to_new

def duplicate_lorebook_for_chat(src_id, chat_id):
    """Legacy single-book duplication for backward compatibility."""
    return list(duplicate_lorebook_tree_for_chat(src_id, chat_id, include_links=False).values())[0]

def delete_lore(entry_id):
    qi("DELETE FROM lore_entries WHERE id=?", (entry_id,))

def search_lore(lorebook_ids, query, k=6, exclude_categories=None):
    # lorebook_ids may be a plain list/int (existing callers, unweighted --
    # every book competes as an equal) or a {book_id: weight} dict as
    # returned by chat_lorebook_weights -- _ids() already extracts the id
    # list correctly from either (iterating a dict yields its keys), so
    # this only changes behavior for callers that opt in by passing the
    # richer shape. Previously an ancestor several hops up the lorebook
    # tree, or a reference_only-linked book, scored identically to a
    # book the chat is actually attached to -- resolve_lorebook_graph
    # computed a meaningful per-book weight for exactly this and it was
    # discarded the moment chat_lorebook_ids flattened it to bare ids.
    weights = lorebook_ids if isinstance(lorebook_ids, dict) else None
    ids = _ids(lorebook_ids)
    if not ids:
        return []
    ph = ",".join("?" * len(ids))
    rows = q(f"SELECT * FROM lore_entries WHERE lorebook_id IN ({ph})", tuple(ids))
    if exclude_categories:
        rows = [r for r in rows if (r["category"] or "other") not in exclude_categories]
    if not rows:
        return []
    qv = embed_texts([query or ""])[0]
    kw = _kw_scores("lore_fts", query)
    scored = []
    for r in rows:
        s = (0.65 * _cos(qv, _vec(r["embedding"]))
             + 0.35 * kw.get(r["id"], 0.0)
             + (0.1 if r["canon_locked"] else 0.0)
             + (0.05 * (r["importance"] or 0.5)))
        if weights is not None:
            s *= (0.7 + 0.3 * weights.get(r["lorebook_id"], 1.0))
        scored.append((s, r))
    scored.sort(key=lambda x: -x[0])
    return [
        {"id": row["id"], "entry_uid": row["entry_uid"],
         "book_id": row["lorebook_id"], "keys": row["keys"],
         "content": row["content"], "category": row["category"] or "other",
         "locked": bool(row["canon_locked"])}
        for _, row in scored[:k]
    ]

def knowledge_for_character(lorebook_ids, char_room, known_tags, excluded_titles, limit=30):
    ids = _ids(lorebook_ids)
    if not ids or not known_tags:
        return []
    ph = ",".join("?" * len(ids))
    rows = q(f"""SELECT * FROM lore_entries WHERE lorebook_id IN ({ph})
             AND category='knowledge' ORDER BY lorebook_id, id""", tuple(ids))
    excl = set(excluded_titles or [])
    seen_titles = set()
    results = []
    for r in rows:
        tag = r["knowledge_tag"] or "common"
        if tag not in known_tags:
            continue
        title = r["title"] or ""
        if title and (title in excl or title in seen_titles):
            continue
        range_type = r["knowledge_range"] or "global"
        if range_type == "local":
            try:
                locations = json.loads(r["knowledge_locations"] or "[]")
            except Exception:
                locations = []
            if not locations:
                continue
            if char_room and char_room not in locations:
                continue
        results.append({"title": title, "content": r["content"],
                        "tag": tag, "range": range_type})
        if title:
            seen_titles.add(title)
        if len(results) >= limit:
            break
    return results

# ---- Relationship Graph ----

@dataclass
class Relationship:
    target_name: str
    trust: float = 0.0
    familiarity: float = 0.0
    emotional_valence: float = 0.0
    fear: float = 0.0
    last_interaction_turn: int = 0
    salient_event: str = ""
    notes: str = ""

@dataclass
class RelationshipGraph:
    relationships: dict[str, Relationship] = field(default_factory=dict)

    def get(self, target_name: str) -> Optional[Relationship]:
        return self.relationships.get(target_name)

    def update(self, target_name: str, **kwargs):
        r = self.relationships.setdefault(target_name, Relationship(target_name=target_name))
        for k, v in kwargs.items():
            if hasattr(r, k):
                setattr(r, k, v)

    def adjust_trust(self, target_name: str, delta: float, trigger: str = ""):
        r = self.relationships.setdefault(target_name, Relationship(target_name=target_name))
        r.trust = max(-1.0, min(1.0, r.trust + delta))
        if trigger:
            r.salient_event = trigger

    def to_dict(self) -> dict:
        return {name: asdict(rel) for name, rel in self.relationships.items()}

    @classmethod
    def from_dict(cls, data: dict) -> "RelationshipGraph":
        graph = cls()
        for name, rd in (data or {}).items():
            graph.relationships[name] = Relationship(**rd)
        return graph

def get_relationships(chat_id: int, char_id: int) -> RelationshipGraph:
    state = wget(chat_id, f"relationships:{char_id}", None)
    if state:
        return RelationshipGraph.from_dict(state)
    return RelationshipGraph()

def save_relationships(chat_id: int, char_id: int, graph: RelationshipGraph):
    wset(chat_id, f"relationships:{char_id}", graph.to_dict())

def apply_relationship_updates(chat_id, char_id, turn_idx, updates):
    graph = get_relationships(chat_id, char_id)
    for update in updates or []:
        target = str(update.get("target_entity") or "").strip()
        if not target:
            continue
        current = graph.get(target)
        if current is None:
            graph.update(target)
            current = graph.get(target)
        trust_delta = _clamp_signed(update.get("trust_delta", 0.0), -0.2, 0.2)
        warmth_delta = _clamp_signed(update.get("warmth_delta", 0.0), -0.2, 0.2)
        fear_delta = _clamp_signed(update.get("fear_delta", 0.0), -0.2, 0.2)
        triggers = ", ".join(update.get("trigger_event_ids") or [])
        graph.update(target,
            trust=_clamp_signed(current.trust + trust_delta, -1.0, 1.0),
            emotional_valence=_clamp_signed(current.emotional_valence + warmth_delta, -1.0, 1.0),
            fear=_clamp_signed(current.fear + fear_delta, -1.0, 1.0),
            familiarity=min(1.0, current.familiarity + 0.03),
            last_interaction_turn=turn_idx,
            # Only overwrite the recorded salient event when this update
            # actually carries triggers -- a routine trigger-less delta
            # must not erase previously recorded history.
            **({"salient_event": triggers[-300:]} if triggers else {}))
    save_relationships(chat_id, char_id, graph)
    return graph

def update_relationships_from_inference(chat_id, char_id, turn_idx, inference_updates, existing=None):
    graph = existing or get_relationships(chat_id, char_id)
    for u in inference_updates:
        about = u.get("about", "")
        if not about:
            continue
        confidence = float(u.get("confidence", 0.5))
        conclusion = u.get("conclusion", "")
        cl = conclusion.lower()
        trust_delta = 0.0
        if any(w in cl for w in ("trustworthy", "honest", "kind", "saved", "helped")):
            trust_delta = 0.1 * confidence
        elif any(w in cl for w in ("lied", "betrayed", "deceitful", "dangerous", "threat")):
            trust_delta = -0.15 * confidence
        if trust_delta != 0:
            graph.adjust_trust(about, trust_delta, conclusion[:200])
        graph.update(about,
            familiarity=min(1.0, (graph.get(about).familiarity + 0.05) if graph.get(about) else 0.05),
            last_interaction_turn=turn_idx)
    save_relationships(chat_id, char_id, graph)
    return graph

def relationships_for_payload(chat_id: int, char_id: int) -> dict:
    graph = get_relationships(chat_id, char_id)
    return graph.to_dict()

# ---- Rebuilding vectors after the embedding model changes ----

# Rows per embedding call. Each memory costs TWO documents (its full document
# and its cue text), so a batch of 32 is 64 texts -- comfortably inside every
# provider's per-request limit while still amortising the round trip.
_REBUILD_BATCH = 32


def embedding_bank_status(chat_id=None, char_id=None):
    """How many stored rows were embedded by a model other than the live one.

    Read-only, and cheap: it is the question `_warn_stranded_embeddings`
    answers per retrieval, asked deliberately and for the whole bank so a host
    can see the split before deciding to spend on rebuilding it.
    """
    live = embed_texts_meta(["status"])
    where, args = ["1=1"], []
    if chat_id is not None:
        where.append("chat_id=?"); args.append(chat_id)
    if char_id is not None:
        where.append("char_id=?"); args.append(char_id)
    clause = " AND ".join(where)
    stale = ("(embedding_model IS NULL OR embedding_model!=? "
             "OR embedding_dim IS NULL OR embedding_dim!=?)")
    counts = {}
    for table in ("memories", "memory_summaries"):
        total = q(f"SELECT COUNT(*) AS n FROM {table} WHERE {clause}",
                  tuple(args), one=True)["n"]
        stranded = q(
            f"SELECT COUNT(*) AS n FROM {table} WHERE {clause} AND {stale}",
            tuple(args) + (live.model_key, live.dimensions), one=True)["n"]
        counts[table] = {"total": total, "stranded": stranded}
    return {
        "model": live.model_key,
        "dimensions": live.dimensions,
        # True when no embeddings provider is configured, so the live "model"
        # is the crc32 fallback. Rebuilding TO that is legal but is a
        # downgrade, and a caller deserves to be told which way it is going.
        "is_fallback": bool(live.fallback),
        # WHY it fell back, verbatim from the provider. Without this the
        # panel can only say "no embeddings provider", which is wrong and
        # unhelpful when one IS configured and is simply not an embeddings
        # model: `embed_texts_meta` catches every failure and degrades to the
        # hash, so choosing a chat model for this role looks like success and
        # silently changes nothing. Measured live -- `inception/mercury-2`
        # selected here returned "Model inception/mercury-2 does not exist",
        # which is exactly the sentence a host needs to see.
        "fallback_reason": str(live.error or "") if live.fallback else "",
        **counts,
    }


def rebuild_embeddings(chat_id=None, char_id=None, *, batch=_REBUILD_BATCH,
                       limit=None, progress=None):
    """Re-embed every row whose vectors were made by a different model.

    Configuring an `embeddings` provider on a story with history does not
    re-embed anything, and `search_memories` scores a row 0.0 on BOTH vector
    rankings when its `embedding_model`/`embedding_dim` do not match the live
    ones. Without this pass, the upgrade silently splits a memory bank into
    two eras -- everything written before it reachable only by keyword and
    exact match, forever. See docs/UNBUILT.md §1.15.

    Rebuilt with the SAME document construction `_embed_memory` uses, because
    a vector built from different text is not comparable with one built from
    the same text, and a rebuild that quietly changed the recipe would be a
    subtler version of the bug it fixes.

    **Resumable by construction**: the selection is "rows that do not match
    the live model", so a run that dies halfway simply has less to do next
    time. Each batch commits on its own for that reason.

    **Refuses to write a fallback over a real vector.** `embed_texts_meta`
    degrades to the crc32 hash on any provider error, and stamps the batch as
    `cheap:crc32:256`. Writing that would mark the rows migrated while
    downgrading them -- the one outcome worse than not running. A batch that
    comes back `fallback` when the caller is not deliberately rebuilding TO
    the fallback aborts the run and reports what it managed.

    Never call this on the turn path: it is O(bank) and it talks to a provider.
    """
    live = embed_texts_meta(["status"])
    target_key, target_dim = live.model_key, live.dimensions
    want_fallback = bool(live.fallback)
    report = {"model": target_key, "dimensions": target_dim,
              "memories": 0, "summaries": 0, "batches": 0,
              "stopped_early": False, "error": ""}

    where, args = ["1=1"], []
    if chat_id is not None:
        where.append("chat_id=?"); args.append(chat_id)
    if char_id is not None:
        where.append("char_id=?"); args.append(char_id)
    clause = " AND ".join(where)
    stale = ("(embedding_model IS NULL OR embedding_model!=? "
             "OR embedding_dim IS NULL OR embedding_dim!=?)")
    stale_args = tuple(args) + (target_key, target_dim)

    def _embed(texts):
        """Embed, or raise so the run stops with the bank still coherent."""
        got = embed_texts_meta(texts)
        if got.fallback and not want_fallback:
            raise RuntimeError(
                "embedding provider unavailable (%s); refusing to write "
                "fallback vectors over real ones" % (got.error or "unknown"))
        return got

    done = 0
    try:
        while limit is None or done < limit:
            take = batch if limit is None else min(batch, limit - done)
            rows = q(f"SELECT * FROM memories WHERE {clause} AND {stale} "
                     "ORDER BY id LIMIT ?", stale_args + (take,))
            if not rows:
                break
            mems = [_row_memory(r) for r in rows]
            docs = []
            for mem in mems:
                docs.append(_memory_document(mem))
                docs.append(_memory_cues(mem) or _memory_document(mem))
            got = _embed(docs)
            with transaction():
                for index, mem in enumerate(mems):
                    qi("UPDATE memories SET embedding=?,cue_embedding=?,"
                       "embedding_model=?,embedding_dim=? WHERE id=?",
                       (_blob(got.vectors[index * 2]),
                        _blob(got.vectors[index * 2 + 1]),
                        got.model_key, got.dimensions, mem["id"]))
            done += len(rows)
            report["memories"] += len(rows)
            report["batches"] += 1
            if progress:
                progress(report["memories"], "memories")

        while True:
            rows = q(f"SELECT * FROM memory_summaries WHERE {clause} AND {stale} "
                     "ORDER BY id LIMIT ?", stale_args + (batch,))
            if not rows:
                break
            texts = [_summary_retrieval_text(
                r["summary"], _json_list(r["key_phrases"]),
                _json_list(r["unresolved_threads"])) for r in rows]
            got = _embed(texts)
            with transaction():
                for index, row in enumerate(rows):
                    qi("UPDATE memory_summaries SET embedding=?,"
                       "embedding_model=?,embedding_dim=? WHERE id=?",
                       (_blob(got.vectors[index]), got.model_key,
                        got.dimensions, row["id"]))
            report["summaries"] += len(rows)
            report["batches"] += 1
            if progress:
                progress(report["summaries"], "summaries")
    except Exception as exc:
        # Everything committed so far stands, and re-running resumes.
        report["stopped_early"] = True
        report["error"] = str(exc)
        logger.warning("memory: embedding rebuild stopped early after "
                       "%d memories and %d summaries: %s",
                       report["memories"], report["summaries"], exc)
        return report

    # A rebuilt row is no longer stranded, so let the per-retrieval warning
    # speak again if it ever becomes true a second time.
    _STRANDED_REPORTED.clear()
    logger.info("memory: rebuilt %d memories and %d summaries onto %s",
                report["memories"], report["summaries"], target_key)
    return report


def _memory_vector_key(char_id, content):
    """What decides a memory's vector: whose it is, and what it says.

    Checkpoint dumps carry no row id, so the join is on the content itself --
    which is the honest key anyway, since the vector is a pure function of the
    document built from it. Scoped per character because two minds can hold
    word-identical memories that are still different rows.
    """
    body = " ".join(str(content or "").split())
    return (char_id, hashlib.sha1(body.encode("utf-8", "ignore")).hexdigest())


def rebuild_checkpoint_embeddings(chat_id=None, *, dry_run=True, progress=None):
    """Carry a completed rebuild back through a story's saved states.

    A checkpoint stores each memory's vector verbatim so that restoring one
    never re-embeds a bank (see `_blob_to_b64`). That is right, and it means a
    checkpoint written BEFORE a rebuild holds the old vectors and the old model
    key -- so rolling back to it silently undoes the rebuild. Measured live:
    one reroll put 637 of 642 rows back on the crc32 fallback.

    **This re-embeds nothing.** A vector is a pure function of the memory's
    content, and the same memory appears in dozens of checkpoints unchanged --
    chat 38 held 40,224 memory copies across its checkpoints and only 526
    distinct by content, 90.7% of which already had a rebuilt vector in the
    live table. So the fix is substitution, not computation: look each saved
    memory up by (character, content) and write in the vector already earned.

    Deliberately conservative, because this rewrites rollback history:

    * a saved row with no live match is left EXACTLY as it was, never blanked
      and never guessed at (those are memories since deleted; if one is ever
      restored, `start_rebuild_if_needed` picks it up);
    * a blob is rewritten only if something actually changed, and only after
      re-parsing to prove it is still valid JSON with the same row count;
    * `dry_run` is the default -- it reports what it would do and writes
      nothing.

    Resumable by construction: a checkpoint already carrying the live model
    key has nothing to substitute and is skipped on the next pass.
    """
    live = embed_texts_meta(["status"])
    key, dim = live.model_key, live.dimensions
    where, args = ["1=1"], []
    if chat_id is not None:
        where.append("chat_id=?"); args.append(chat_id)
    clause = " AND ".join(where)

    vectors = {}
    for row in q(f"SELECT char_id, content, embedding, cue_embedding "
                 f"FROM memories WHERE {clause} AND embedding_model=? "
                 f"AND embedding_dim=?", tuple(args) + (key, dim)):
        vectors[_memory_vector_key(row["char_id"], row["content"])] = (
            _blob_to_b64(row["embedding"]), _blob_to_b64(row["cue_embedding"]))
    summaries = {}
    for row in q(f"SELECT char_id, summary, embedding FROM memory_summaries "
                 f"WHERE {clause} AND embedding_model=? AND embedding_dim=?",
                 tuple(args) + (key, dim)):
        summaries[_memory_vector_key(row["char_id"], row["summary"])] = (
            _blob_to_b64(row["embedding"]))

    report = {"model": key, "checkpoints": 0, "rewritten": 0,
              "memories_repaired": 0, "summaries_repaired": 0,
              "memories_unmatched": 0, "dry_run": bool(dry_run)}
    if not vectors and not summaries:
        return report

    rows = q(f"SELECT id, chat_id, turn_idx, blob FROM checkpoints "
             f"WHERE {clause} ORDER BY id", tuple(args))
    for row in rows:
        report["checkpoints"] += 1
        try:
            blob = json.loads(row["blob"])
        except (TypeError, ValueError):
            continue          # an unreadable checkpoint is left untouched
        changed = 0
        for mem in (blob.get("memories") or []):
            if not isinstance(mem, dict):
                continue
            if mem.get("embedding_model") == key and mem.get("embedding_dim") == dim:
                continue
            hit = vectors.get(_memory_vector_key(mem.get("char_id"),
                                                 mem.get("content")))
            if hit is None:
                report["memories_unmatched"] += 1
                continue
            mem["embedding"], mem["cue_embedding"] = hit
            mem["embedding_model"], mem["embedding_dim"] = key, dim
            changed += 1
            report["memories_repaired"] += 1
        for summ in (blob.get("memory_summaries") or []):
            if not isinstance(summ, dict):
                continue
            if summ.get("embedding_model") == key and summ.get("embedding_dim") == dim:
                continue
            hit = summaries.get(_memory_vector_key(summ.get("char_id"),
                                                   summ.get("summary")))
            if hit is None:
                continue
            summ["embedding"] = hit
            summ["embedding_model"], summ["embedding_dim"] = key, dim
            changed += 1
            report["summaries_repaired"] += 1
        if not changed or dry_run:
            continue
        text = json.dumps(blob, ensure_ascii=False)
        # Prove it before it replaces rollback history: parseable, and the
        # same number of rows it went in with.
        check = json.loads(text)
        if (len(check.get("memories") or []) != len(blob.get("memories") or [])
                or sorted(check) != sorted(blob)):
            continue
        qi("UPDATE checkpoints SET blob=? WHERE id=?", (text, row["id"]))
        report["rewritten"] += 1
        if progress:
            progress(report["rewritten"], report["checkpoints"])
    if not dry_run and report["rewritten"]:
        logger.info("memory: carried the rebuild into %d checkpoint(s); "
                    "%d saved memories repaired, %d left unmatched",
                    report["rewritten"], report["memories_repaired"],
                    report["memories_unmatched"])
    return report


# ---- The rebuild, run for the host instead of by the host ----------------
#
# Nobody should have to know that changing an embeddings provider silently
# halves their retrieval, notice that it happened, find a maintenance command
# and run it. The engine knows the model it is embedding with and the model
# every stored row was embedded with; where those disagree it can simply fix
# it. This is the standing reconciler that does.
#
# NOT a one-time upgrade migration, and that distinction is the whole design:
# a mismatch appears whenever the embedding model changes -- configuring a
# provider, switching providers, a provider changing its default model or its
# dimensions, or falling back to the crc32 hash because a key expired. So this
# is a condition to be reconciled whenever it holds, checked at startup and
# again whenever provider settings are written, rather than a migration that
# runs once and is never thought about again.

_REBUILD_LOCK = threading.Lock()
_REBUILD_STATE = {
    "running": False, "done": 0, "total": 0, "model": "",
    "finished_at": 0.0, "error": "", "stopped_early": False,
}


def rebuild_progress():
    """A snapshot of the reconciler, for the status endpoint."""
    with _REBUILD_LOCK:
        return dict(_REBUILD_STATE)


def _run_rebuild(chat_id=None, char_id=None):
    status = embedding_bank_status(chat_id, char_id)
    total = (status["memories"]["stranded"]
             + status["memory_summaries"]["stranded"])
    with _REBUILD_LOCK:
        _REBUILD_STATE.update(running=True, done=0, total=total,
                              model=status["model"], error="",
                              stopped_early=False, finished_at=0.0)
    try:
        def _tick(count, _kind):
            with _REBUILD_LOCK:
                # Memories are rebuilt before summaries, so the summary pass
                # continues the same count rather than restarting it.
                _REBUILD_STATE["done"] = max(_REBUILD_STATE["done"], count)
        report = rebuild_embeddings(chat_id, char_id, progress=_tick)
        with _REBUILD_LOCK:
            _REBUILD_STATE.update(
                done=report["memories"] + report["summaries"],
                error=report["error"], stopped_early=report["stopped_early"])
    except Exception as exc:           # never take the server down for this
        logger.warning("memory: embedding rebuild failed: %s", exc)
        with _REBUILD_LOCK:
            _REBUILD_STATE.update(error=str(exc), stopped_early=True)
    finally:
        with _REBUILD_LOCK:
            _REBUILD_STATE.update(running=False, finished_at=time.time())


def start_rebuild_if_needed(chat_id=None, char_id=None, *, force=False):
    """Reconcile stored vectors with the live embedding model, in the
    background. Returns what it decided, having already started if it started.

    Safe to call on every startup and every settings write: it costs one
    COUNT per table when there is nothing to do, and it will not start a
    second run while one is going.
    """
    with _REBUILD_LOCK:
        if _REBUILD_STATE["running"]:
            return {"started": False, "reason": "already running"}
    try:
        status = embedding_bank_status(chat_id, char_id)
    except Exception as exc:
        logger.warning("memory: could not check embedding bank: %s", exc)
        return {"started": False, "reason": "status check failed: %s" % exc}
    stranded = (status["memories"]["stranded"]
                + status["memory_summaries"]["stranded"])
    if not stranded:
        return {"started": False, "reason": "nothing to rebuild", **status}
    if status["is_fallback"] and not force:
        # The live "model" is the crc32 hash, which means no embeddings
        # provider is configured. Rebuilding onto it would overwrite real
        # vectors with the fallback -- a downgrade, and one the host never
        # asked for. Wait for a provider, or for an explicit force.
        logger.info("memory: %d rows do not match the live embedding model, "
                    "but no embeddings provider is configured -- not "
                    "rebuilding onto the fallback.", stranded)
        return {"started": False, "reason": "no embeddings provider", **status}
    logger.info("memory: rebuilding %d rows onto %s in the background",
                stranded, status["model"])
    thread = threading.Thread(target=_run_rebuild, args=(chat_id, char_id),
                              name="embedding-rebuild", daemon=True)
    thread.start()
    return {"started": True, "stranded": stranded, **status}


# ---- Why there is no vector index ----
#
# There was a `sqlite-vec` ANN index here (`init_vec_index`,
# `search_memories_vec`). It never ran -- no caller, and the extension was
# never loaded -- and it was deleted rather than wired, because wiring it
# would have been a REGRESSION.
#
# `search_memories` filters its rows before ranking: the F1 turn cutoff (a
# mind deciding turn N must never retrieve how turn N turned out, live on
# every reroll) and frame visibility. The ANN query filtered on chat_id and
# char_id only, and those predicates are exactly the kind an ANN index cannot
# carry cheaply -- so a vec-first branch would have handed a character the
# committed outcome of its own undecided beat.
#
# And the scan it would have optimised does not need optimising. Memories
# accrue at ~3.5 rows per turn per character; measured with `_cos` verbatim,
# the full scan costs 16ms at a real story's worst case (442 rows), 126ms at
# ~1,000 turns, 709ms at ~10,000 -- beside an LLM call measured in seconds.
# Two cheap optimisations sit in front of an index anyway if it ever mattered:
# `_cos` recomputes both norms although every stored vector is already
# normalised (~4x), and the loop could be one matmul (~20x). See
# docs/UNBUILT.md §1.4.


# How far an inference the character no longer holds is pushed down, and the
# floor it stops at. Not zero: a belief that was explained away is still a
# belief they once had, and "I was sure of this and I was wrong" is a thing a
# character should be able to recall. It just must not outrank what replaced it.
#
# The demotion is a ONE-SHOT re-anchoring to a fraction of the confidence the
# character declared at mint time -- never a compounding per-turn decay on the
# current value. The predicate "no surviving hypothesis expresses it" is met by
# per-entity pruning and half-life expiry as well as by genuine explaining-away,
# and mind_models is a small working set while the memory bank is an archive:
# under the compounding rule, 76-80% of a long chat's entire inference bank
# reached the floor within 7-18 played turns of the rule landing (measured
# 2026-07-29 across the live corpus), at which point the belief-weighted
# ranking term removed inferences from recall almost completely (0-1 of top-8
# vs 13-15 at mint confidence in replayed late-turn retrievals). A belief that
# merely aged out of the working set was never concluded WRONG, and must not
# rank as though it was.
_ABANDONED_BELIEF_DECAY = 0.55
_ABANDONED_BELIEF_FLOOR = 0.08


def _mint_confidence_of(salience):
    """The confidence an inference row was minted with, recovered from its
    salience. commit.py mints inference memories with
    salience = 0.45 + 0.3 * confidence, and reconciliation deliberately never
    touches salience (it records how much the inference mattered when formed),
    so the mint-time confidence stays reconstructible without a second column.
    Rows whose salience was authored/imported outside that rule get a
    conservative low anchor rather than a crash."""
    try:
        return max(0.0, min(1.0, (float(salience) - 0.45) / 0.3))
    except (TypeError, ValueError):
        return 0.5


def _abandoned_confidence(salience):
    """The resting confidence for an inference no live hypothesis carries.

    A pure function of the row's (untouched) salience, which is what makes
    reconciliation idempotent: reconciling the same abandoned row on every
    subsequent turn lands on the same number instead of compounding it into
    unretrievability -- and a corpus previously crushed by the compounding
    rule self-heals to this value on its next reconcile pass, no migration.
    Clamped to never exceed the mint confidence, so a belief the character
    barely credited when they formed it is not lifted to the floor."""
    mint = _mint_confidence_of(salience)
    return min(mint, max(_ABANDONED_BELIEF_FLOOR,
                         mint * _ABANDONED_BELIEF_DECAY))


def reconcile_inference_confidence(chat_id, char_id, state, turn_idx,
                                   elapsed_seconds=None):
    """Re-weight this character's inference memories to what they believe NOW.

    An inference memory is minted with the confidence the character declared
    the moment they formed it, and nothing ever revisited it. Meanwhile their
    mind_models kept moving -- theory_of_mind.apply_mind_model_updates blends a
    restated belief upward, partially explains away the competitor it displaces,
    decays the unreinforced, and prunes what falls through the floor. So a
    character could hold one belief and preferentially RECALL the one they had
    already abandoned, because recall ranked on a number frozen at mint time.

    This projects the reconciled credence back onto the memories that expressed
    it: a claim still carried by a live hypothesis takes that hypothesis's
    decay-adjusted confidence; a claim no hypothesis carries any more is pushed
    toward _ABANDONED_BELIEF_FLOOR.

    Information-firewall note, because this is the part that matters: the only
    inputs are this character's OWN memory rows and their OWN mind_models, both
    already built from what they legitimately perceived. Nothing here consults
    the objective record, another mind's state, or whether the belief was
    actually TRUE -- a character revises because of what they later perceived,
    never because they were graded against reality. Reconciling against truth
    would collapse the belief layer into the truth layer, which is the one
    distinction this engine exists to keep.

    `salience` is deliberately untouched: it records how much the inference
    mattered when it was formed (and drives consolidation/archiving), which is
    a different question from how much the character credits it now.

    Returns the number of rows whose confidence changed.
    """
    rows = q(
        "SELECT id, entities, gist, salience, confidence FROM memories "
        "WHERE chat_id=? AND char_id=? AND kind='inference'",
        (chat_id, char_id),
    )
    if not rows:
        return 0

    updates = []
    for row in rows:
        subjects = _json_list(row["entities"])
        subject = str(subjects[0]).strip() if subjects else ""
        claim = str(row["gist"] or "").strip()
        if not subject or not claim:
            continue
        credence = belief_credence(
            state, subject, claim, turn_idx, elapsed_seconds)
        abandoned = _abandoned_confidence(row["salience"])
        if credence is None:
            # No live hypothesis carries this claim. That is NOT proof the
            # character concluded they were wrong -- mind_models prunes on
            # capacity and half-life as well as on displacement -- so the row
            # rests at a fixed fraction of its mint confidence (idempotent;
            # see _abandoned_confidence) rather than compounding downward on
            # every reconciled turn.
            revised = abandoned
        else:
            # A claim STILL STORED must never rank below one that was pruned:
            # half-life decay on a surviving hypothesis measures staleness,
            # not disbelief, so the live credence is floored at the abandoned
            # resting place. Held >= abandoned, always.
            revised = max(credence, abandoned)
        if abs(revised - float(row["confidence"] or 0.0)) > 1e-6:
            updates.append((round(revised, 4), row["id"]))

    for confidence, mid in updates:
        qi("UPDATE memories SET confidence=? WHERE id=?", (confidence, mid))
    return len(updates)
