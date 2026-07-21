"""Memory system with hierarchical lorebook support and expanded categories."""

import base64
import json, re, time, math
import numpy as np
from collections import defaultdict
from db import q, qi, wget, wset, transaction
from providers import embed_texts, embed_texts_meta, chat_complete
from prompts import get_prompt
from dataclasses import dataclass, field, asdict
from typing import Optional
import frames as _frames
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

try:
    import sqlite_vec
    _HAS_VEC = True
except ImportError:
    _HAS_VEC = False

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
    book = q("SELECT parent_id, sort_order FROM lorebooks WHERE id=?", (book_id,), one=True)
    if not book:
        raise ValueError("Lorebook not found")
    
    parent_id = book["parent_id"]
    sort_order = book["sort_order"]
    
    if direction == "up":
        prev = q(
            "SELECT id FROM lorebooks WHERE parent_id IS ? AND sort_order < ? ORDER BY sort_order DESC LIMIT 1",
            (parent_id, sort_order),
            one=True,
        )
        if prev:
            qi("UPDATE lorebooks SET sort_order=? WHERE id=?", (sort_order, prev["id"]))
            qi("UPDATE lorebooks SET sort_order=? WHERE id=?", (sort_order - 1, book_id))
    elif direction == "down":
        nxt = q(
            "SELECT id FROM lorebooks WHERE parent_id IS ? AND sort_order > ? ORDER BY sort_order ASC LIMIT 1",
            (parent_id, sort_order),
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
        "archived": bool(row["archived"]),
        "event_key": row["event_key"] or "",
        "embedding_model": row["embedding_model"] or "",
        "embedding_dim": row["embedding_dim"],
    }

def prepare_memory(chat_id, char_id, turn_id, kind, provenance, salience, content, *,
                   turn_idx=None, category=None, gist=None, key_phrases=None,
                   entities=None, location="", emotional_context="",
                   valence=0.0, arousal=0.0, confidence=1.0, event_key="",
                   frame_id=_UNSET) -> dict:
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
    )
    if existing:
        mid = existing["id"]
        qi("""UPDATE memories SET turn_id=?,turn_idx=?,kind=?,category=?,provenance=?,
            salience=?,content=?,gist=?,key_phrases=?,entities=?,location=?,
            emotional_context=?,valence=?,arousal=?,confidence=?,embedding=?,
            cue_embedding=?,embedding_model=?,embedding_dim=?,frame_id=?,archived=0 WHERE id=?""",
           values + (mid,))
    else:
        mid = qi("""INSERT INTO memories(chat_id,char_id,turn_id,turn_idx,kind,category,
            provenance,salience,content,gist,key_phrases,entities,location,
            emotional_context,valence,arousal,confidence,embedding,cue_embedding,
            embedding_model,embedding_dim,frame_id,event_key)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
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
    clauses = ["chat_id=?", "char_id=?"]
    args = [chat_id, char_id]
    if not include_archived:
        clauses.append("archived=0")
    if category in MEMORY_CATEGORIES:
        clauses.append("category=?")
        args.append(category)
    if provenance in MEMORY_PROVENANCE:
        clauses.append("provenance=?")
        args.append(provenance)
    args.extend([max(1, min(int(limit), 1000)), max(0, int(offset))])
    rows = q(f"""SELECT * FROM memories WHERE {' AND '.join(clauses)}
        ORDER BY CASE WHEN turn_idx IS NULL THEN 1 ELSE 0 END, turn_idx DESC, id DESC
        LIMIT ? OFFSET ?""", tuple(args))
    vf = _active_frame_id.get() if viewer_frame_id is _UNSET else viewer_frame_id
    rows = [r for r in rows if _frames.is_memory_visible(char_id, r["frame_id"], vf, r["turn_idx"])]
    return [_row_memory(r) for r in rows]

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

def _rrf_add(scores, reasons, ranking, weight, reason):
    for rank, mid in enumerate(ranking, 1):
        scores[mid] += weight / (60.0 + rank)
        if rank <= 12 and reason not in reasons[mid]:
            reasons[mid].append(reason)

def search_memories(chat_id, char_id, query, k=8, *, include_archived=True,
                    current_turn_idx=None, chronological=True, viewer_frame_id=_UNSET):
    rows = q("SELECT * FROM memories WHERE chat_id=? AND char_id=? AND (?=1 OR archived=0)",
             (chat_id, char_id, 1 if include_archived else 0))
    vf = _active_frame_id.get() if viewer_frame_id is _UNSET else viewer_frame_id
    rows = [r for r in rows if _frames.is_memory_visible(char_id, r["frame_id"], vf, r["turn_idx"])]
    if not rows:
        return []
    query_text = str(query or "").strip()
    embedded = embed_texts_meta([query_text or "memory"])
    qv = embedded.vectors[0]
    memories = {}
    sem_scores, cue_scores = [], []
    for row in rows:
        mem = _row_memory(row)
        fv, cv = _vec(row["embedding"]), _vec(row["cue_embedding"])
        compatible = row["embedding_model"] == embedded.model_key and row["embedding_dim"] == embedded.dimensions
        sem = _cos(qv, fv) if compatible and fv is not None else 0.0
        cue = _cos(qv, cv) if compatible and cv is not None else 0.0
        mem["_vector"] = fv if compatible else None
        memories[mem["id"]] = mem
        sem_scores.append((sem, mem["id"]))
        cue_scores.append((cue, mem["id"]))
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
    tmode = _temporal_mode(query_text)
    known_turns = [m["turn_idx"] for m in memories.values() if m["turn_idx"] is not None]
    max_turn = current_turn_idx if current_turn_idx is not None else max(known_turns, default=0)
    for mid, mem in memories.items():
        fused[mid] += 0.08 * mem["salience"]
        fused[mid] += 0.04 * mem["confidence"]
        fused[mid] += 0.08 * _exact_cue_score(mem, query_text)
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
    rows = q("""SELECT * FROM memories WHERE chat_id=? AND char_id=? AND archived=0
        AND turn_idx IS NOT NULL AND turn_idx>=? AND turn_idx<? ORDER BY turn_idx DESC, id DESC LIMIT ?""",
        (chat_id, char_id, max(0, current_turn_idx - turns), current_turn_idx, limit))
    rows = list(reversed(rows))
    # Recent-by-play-order is not the same as recent-by-diegetic-order: the
    # turn immediately before a frame jump can be an entirely different
    # era. Without this filter a flash-forward's opening turns would pull
    # in the pre-jump present as "recent memory."
    vf = _active_frame_id.get() if viewer_frame_id is _UNSET else viewer_frame_id
    rows = [r for r in rows if _frames.is_memory_visible(char_id, r["frame_id"], vf, r["turn_idx"])]
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

def build_character_memory_context(chat_id, char_id, current_turn_idx, current_view, active_state, *,
                                   recent_turns=4, recall_limit=8):
    active_state = active_state or {}
    recent = recent_memory_buffer(chat_id, char_id, current_turn_idx, turns=recent_turns, limit=12)
    recent_ids = {m["id"] for m in recent}
    summary = get_memory_summary(chat_id, char_id)
    query_parts = [current_view or "", str(active_state.get("goal") or ""), str(active_state.get("mood") or ""),
                   " ".join(summary.get("unresolved_threads") or [])]
    query_text = " ".join(p for p in query_parts if p)
    recalled = search_memories(chat_id, char_id, query_text, k=recall_limit,
                               include_archived=True, current_turn_idx=current_turn_idx, chronological=True)
    recalled = [m for m in recalled if m["id"] not in recent_ids]
    return {
        "working_memory": {
            "current_perception": current_view or "",
            "current_mood": active_state.get("mood") or "neutral",
            "current_goal": active_state.get("goal") or "",
            "active_concerns": (summary.get("unresolved_threads") or [])[:4],
        },
        "recent_episodes": recent,
        "recalled_old_memories": recalled,
        "autobiographical_summary": summary.get("summary") or "",
        "summary_key_phrases": summary.get("key_phrases") or [],
        "unresolved_threads": summary.get("unresolved_threads") or [],
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
    clauses = [
        "chat_id=?", "char_id=?", "turn_idx IS NOT NULL",
        "archived=0", "turn_idx>?",
    ]
    args = [chat_id, char_id, old_summary.get("end_turn_idx") or 0]
    if through_turn_idx is not None:
        clauses.append("turn_idx<=?")
        args.append(through_turn_idx)
    rows = q(f"SELECT * FROM memories WHERE {' AND '.join(clauses)} ORDER BY turn_idx, id", tuple(args))
    # turn_idx is GLOBAL play order shared by every frame, not per-era --
    # without this filter, memories formed during a flash-forward/-back
    # would get folded into the singleton autobiographical summary the
    # moment play returns to the present and turn_idx catches up, hand-
    # ing a character knowledge of events they have not diegetically
    # reached yet. Same epistemic-cursor check every other memory read
    # path already applies (list_memories/search_memories/recent_memory_
    # buffer); this call site was the one place it had been missed.
    vf = _active_frame_id.get() if viewer_frame_id is _UNSET else viewer_frame_id
    rows = [r for r in rows if _frames.is_memory_visible(char_id, r["frame_id"], vf, r["turn_idx"])]
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
    save_memory_summary(chat_id, char_id, result.get("summary") or "",
                        start_turn_idx=start_turn, end_turn_idx=end_turn,
                        key_phrases=result.get("key_phrases") or [],
                        unresolved_threads=result.get("unresolved_threads") or [])
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
            and float(m.get("salience") or 0) < 0.72
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

def dump_chat_memories(chat_id):
    rows = q("SELECT * FROM memories WHERE chat_id=? ORDER BY CASE WHEN turn_idx IS NULL THEN 1 ELSE 0 END, turn_idx, id", (chat_id,))
    return [
        {"char_id": r["char_id"], "turn_id": r["turn_id"], "turn_idx": r["turn_idx"],
         "frame_id": r["frame_id"],
         "kind": r["kind"], "category": r["category"], "provenance": r["provenance"],
         "salience": r["salience"], "content": r["content"], "gist": r["gist"],
         "key_phrases": _json_list(r["key_phrases"]), "entities": _json_list(r["entities"]),
         "location": r["location"], "emotional_context": r["emotional_context"],
         "valence": r["valence"], "arousal": r["arousal"], "confidence": r["confidence"],
         "archived": bool(r["archived"]), "event_key": r["event_key"],
         # Stored vectors travel with the dump so restore can put them
         # back byte-identically instead of re-embedding the entire
         # memory bank on every checkpoint restore (expensive, and a
         # provider hiccup during it silently downgrades every vector
         # to the crc32 fallback, which then scores 0.0 forever).
         "embedding": _blob_to_b64(r["embedding"]),
         "cue_embedding": _blob_to_b64(r["cue_embedding"]),
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
        }
        full_blob = _b64_to_blob(m.get("embedding"))
        cue_blob = _b64_to_blob(m.get("cue_embedding"))
        model = m.get("embedding_model") or ""
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
         "archived": bool(r["archived"]), "event_key": r["event_key"]}
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
            salient_event=triggers[-300:])
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

# ---- Vector Index ----

def init_vec_index():
    if not _HAS_VEC:
        return
    from db import conn
    c = conn()
    try:
        c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS memory_vec USING vec0(embedding float[256])")
        c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS lore_vec USING vec0(embedding float[256])")
        c.commit()
    except Exception:
        pass

def search_memories_vec(chat_id, char_id, query_vec, k=8):
    if not _HAS_VEC:
        return None
    rows = q(
        "SELECT m.id, m.kind, m.provenance, m.turn_id, m.salience, m.content, v.distance "
        "FROM memories m JOIN memory_vec v ON v.rowid = m.id "
        "WHERE m.chat_id=? AND m.char_id=? ORDER BY v.distance LIMIT ?",
        (chat_id, char_id, k),
    )
    return [{"kind": r["kind"], "provenance": r["provenance"], "turn": r["turn_id"],
             "salience": r["salience"], "content": r["content"], "distance": r["distance"]} for r in rows]