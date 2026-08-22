"""Unified Library projection and reversible host-authoring lifecycle.

The projection answers one database question for the replacement UI. It does
not own resources or associations: existing resource and story routes remain
the mutation authority.
"""

from __future__ import annotations

import json
import math
import time
from collections import defaultdict
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from core.db import q, qi, transaction


router = APIRouter()

KINDS = ("story", "character", "persona", "lore")
_TABLES = {
    "story": "chats",
    "character": "characters",
    "persona": "personas",
    "lore": "lorebooks",
}
_PUBLIC_TEXT_KEYS = frozenset((
    "description", "summary", "tags", "tag", "role", "occupation",
    "archetype", "title", "category", "genre", "keywords",
))


def _json(value, default):
    try:
        parsed = json.loads(value or "")
    except (TypeError, ValueError):
        return default
    return parsed if isinstance(parsed, type(default)) else default


def _public_text(value, *, depth=0):
    """Extract only explicitly public descriptive fields from a sheet."""
    if depth > 4 or not isinstance(value, dict):
        return []
    found = []
    for key, child in value.items():
        normalized = str(key).strip().casefold()
        if normalized in _PUBLIC_TEXT_KEYS:
            if isinstance(child, str) and child.strip():
                found.append(child.strip())
            elif isinstance(child, list):
                found.extend(str(item).strip() for item in child
                             if isinstance(item, (str, int, float))
                             and str(item).strip())
        elif normalized in ("identity", "profile", "appearance"):
            found.extend(_public_text(child, depth=depth + 1))
    return found


def _summary(sheet):
    values = _public_text(sheet)
    return values[0][:500] if values else ""


def _association(story_id, story_name, state, **extra):
    return {
        "story_id": int(story_id),
        "story_name": str(story_name or "Untitled story"),
        "state": str(state),
        **extra,
    }


def _archive_map():
    return {
        (row["item_type"], int(row["item_id"])): bool(row["archived"])
        for row in q("SELECT item_type,item_id,archived FROM library_item_state")
    }


def _character_associations():
    result = defaultdict(list)
    for row in q(
        "SELECT cc.char_id,c.id AS story_id,c.name AS story_name,cc.status "
        "FROM chat_chars cc JOIN chats c ON c.id=cc.chat_id "
        "ORDER BY c.id"
    ):
        result[int(row["char_id"])].append(_association(
            row["story_id"], row["story_name"], row["status"] or "active",
        ))
    return result


def _persona_associations():
    by_persona = defaultdict(dict)
    for row in q(
        "SELECT p.id AS persona_id,c.id AS story_id,c.name AS story_name "
        "FROM chats c JOIN personas p ON p.id=c.persona_id ORDER BY c.id"
    ):
        by_persona[int(row["persona_id"])][int(row["story_id"])] = _association(
            row["story_id"], row["story_name"], "primary",
        )
    for row in q(
        "SELECT cp.persona_id,c.id AS story_id,c.name AS story_name,cp.status "
        "FROM chat_personas cp JOIN chats c ON c.id=cp.chat_id ORDER BY c.id"
    ):
        persona_id, story_id = int(row["persona_id"]), int(row["story_id"])
        by_persona[persona_id].setdefault(story_id, _association(
            story_id, row["story_name"], row["status"] or "active",
        ))
    return defaultdict(list, {
        persona_id: [stories[key] for key in sorted(stories)]
        for persona_id, stories in by_persona.items()
    })


def _lore_associations():
    """Map reusable lore ids to the story copies that actually carry them."""
    by_origin = defaultdict(dict)
    for row in q(
        "SELECT cl.lorebook_id,cl.origin_id AS attached_origin,cl.enabled,"
        "lb.origin_id AS book_origin,lb.chat_id AS book_chat_id,"
        "c.id AS story_id,c.name AS story_name "
        "FROM chat_lorebooks cl "
        "JOIN lorebooks lb ON lb.id=cl.lorebook_id "
        "JOIN chats c ON c.id=cl.chat_id ORDER BY c.id"
    ):
        origin = row["attached_origin"] or row["book_origin"]
        if origin is None and row["book_chat_id"] is None:
            origin = row["lorebook_id"]
        if origin is None:
            continue
        story_id = int(row["story_id"])
        by_origin[int(origin)][story_id] = _association(
            story_id,
            row["story_name"],
            "attached" if row["enabled"] else "disabled",
            story_item_id=int(row["lorebook_id"]),
        )
    for row in q(
        "SELECT c.id AS story_id,c.name AS story_name,c.lorebook_id,"
        "lb.origin_id,lb.chat_id AS book_chat_id "
        "FROM chats c JOIN lorebooks lb ON lb.id=c.lorebook_id "
        "WHERE c.lorebook_id IS NOT NULL ORDER BY c.id"
    ):
        origin = row["origin_id"]
        if origin is None and row["book_chat_id"] is None:
            origin = row["lorebook_id"]
        if origin is None:
            continue
        story_id = int(row["story_id"])
        by_origin[int(origin)][story_id] = _association(
            story_id, row["story_name"], "canon",
            story_item_id=int(row["lorebook_id"]),
        )
    return defaultdict(list, {
        origin: [stories[key] for key in sorted(stories)]
        for origin, stories in by_origin.items()
    })


def _base_items(story_id=None):
    archived = _archive_map()
    char_use = _character_associations()
    persona_use = _persona_associations()
    lore_use = _lore_associations()
    items = []

    for row in q("SELECT id,name,scenario,created FROM chats ORDER BY id"):
        item_id = int(row["id"])
        items.append({
            "kind": "story", "id": item_id, "key": f"story:{item_id}",
            "name": row["name"] or "Untitled story",
            "summary": str(row["scenario"] or "")[:500],
            "subtype": "", "created": row["created"], "reusable": False,
            "archived": archived.get(("story", item_id), False),
            "use_count": 0, "associations": [],
        })
    for row in q("SELECT id,name,sheet,created FROM characters ORDER BY id"):
        item_id = int(row["id"])
        associations = char_use[item_id]
        items.append({
            "kind": "character", "id": item_id,
            "key": f"character:{item_id}", "name": row["name"],
            "summary": _summary(_json(row["sheet"], {})),
            "subtype": "", "created": row["created"], "reusable": True,
            "archived": archived.get(("character", item_id), False),
            "use_count": len(associations), "associations": associations,
        })
    for row in q("SELECT id,name,sheet FROM personas ORDER BY id"):
        item_id = int(row["id"])
        associations = persona_use[item_id]
        items.append({
            "kind": "persona", "id": item_id,
            "key": f"persona:{item_id}", "name": row["name"],
            "summary": _summary(_json(row["sheet"], {})),
            "subtype": "", "created": None, "reusable": True,
            "archived": archived.get(("persona", item_id), False),
            "use_count": len(associations), "associations": associations,
        })
    for row in q(
        "SELECT id,name,summary,book_type FROM lorebooks "
        "WHERE chat_id IS NULL ORDER BY id"
    ):
        item_id = int(row["id"])
        associations = lore_use[item_id]
        items.append({
            "kind": "lore", "id": item_id, "key": f"lore:{item_id}",
            "name": row["name"], "summary": str(row["summary"] or "")[:500],
            "subtype": row["book_type"] or "general", "created": None,
            "reusable": True,
            "archived": archived.get(("lore", item_id), False),
            "use_count": len(associations), "associations": associations,
        })

    if story_id is not None:
        story = q("SELECT id,name FROM chats WHERE id=?", (story_id,), one=True)
        if not story:
            raise HTTPException(404, "Story not found")
        for row in q(
            "SELECT id,name,summary,book_type FROM lorebooks "
            "WHERE chat_id=? AND origin_id IS NULL ORDER BY id",
            (story_id,),
        ):
            item_id = int(row["id"])
            items.append({
                "kind": "lore", "id": item_id, "key": f"lore:{item_id}",
                "name": row["name"],
                "summary": str(row["summary"] or "")[:500],
                "subtype": row["book_type"] or "general", "created": None,
                "reusable": False,
                "archived": archived.get(("lore", item_id), False),
                "use_count": 1,
                "associations": [_association(
                    story_id, story["name"], "owned", story_item_id=item_id,
                )],
            })
    return items


def _parse_types(raw):
    if not raw:
        return set(KINDS)
    chunks = raw if isinstance(raw, list) else [raw]
    values = {
        part.strip().casefold()
        for chunk in chunks
        for part in str(chunk).split(",")
        if part.strip()
    }
    if not values or not values <= set(KINDS):
        raise HTTPException(422, "Unknown Library type")
    return values


def _search_text(item):
    associations = " ".join(row["story_name"] for row in item["associations"])
    return " ".join((
        item["name"], item["summary"], item["subtype"], associations,
    )).casefold()


def _sort_key(item, selected_sort):
    identity = (item["name"].casefold(), item["kind"], item["id"])
    if selected_sort == "type":
        return (item["kind"], *identity)
    if selected_sort == "usage":
        return (-item["use_count"], *identity)
    if selected_sort == "created":
        created = item["created"]
        return (created is None, -(created if created is not None else -math.inf), *identity)
    return identity


@router.get("/api/library")
def library_projection(
    scope: Literal["all", "story", "unassigned", "multiple"] = "all",
    story_id: int | None = Query(default=None, gt=0),
    types: list[str] | None = Query(default=None, max_length=80),
    q_text: str = Query(default="", alias="q", max_length=240),
    sort: Literal["name", "type", "created", "usage"] = "name",
    visibility: Literal["active", "archived"] = "active",
    offset: int = Query(default=0, ge=0, le=100_000),
    limit: int = Query(default=100, ge=1, le=200),
):
    if scope == "story" and story_id is None:
        raise HTTPException(422, "story_id is required for story scope")
    selected_types = _parse_types(types)
    items = _base_items(story_id if scope == "story" else None)
    wants_archived = visibility == "archived"
    items = [item for item in items
             if item["kind"] in selected_types
             and item["archived"] is wants_archived]
    if scope == "story":
        items = [item for item in items if (
            (item["kind"] == "story" and item["id"] == story_id)
            or any(row["story_id"] == story_id for row in item["associations"])
        )]
    elif scope == "unassigned":
        items = [item for item in items
                 if item["reusable"] and item["use_count"] == 0]
    elif scope == "multiple":
        items = [item for item in items
                 if item["reusable"] and item["use_count"] > 1]
    needle = q_text.strip().casefold()
    if needle:
        items = [item for item in items if needle in _search_text(item)]
    items.sort(key=lambda item: _sort_key(item, sort))
    total = len(items)
    facets = {kind: sum(1 for item in items if item["kind"] == kind)
              for kind in KINDS}
    page = items[offset:offset + limit]
    return {
        "items": page,
        "page": {
            "offset": offset, "limit": limit,
            "returned": len(page), "total": total,
        },
        "facets": {"types": facets},
        "query": {
            "scope": scope, "story_id": story_id,
            "types": sorted(selected_types), "q": q_text.strip(),
            "sort": sort, "visibility": visibility,
        },
    }


def _require_item(kind, item_id):
    table = _TABLES.get(kind)
    if table is None:
        raise HTTPException(404, "Library item not found")
    if not q(f"SELECT 1 FROM {table} WHERE id=?", (item_id,), one=True):
        raise HTTPException(404, "Library item not found")


def cleanup_library_state(kind, item_id):
    if kind not in KINDS:
        return
    qi("DELETE FROM library_item_state WHERE item_type=? AND item_id=?",
       (kind, item_id))


@router.put("/api/library/{kind}/{item_id}/archive")
def archive_library_item(kind: str, item_id: int):
    _require_item(kind, item_id)
    with transaction():
        current = q(
            "SELECT archived FROM library_item_state "
            "WHERE item_type=? AND item_id=?",
            (kind, item_id), one=True,
        )
        changed = not current or not bool(current["archived"])
        qi(
            "INSERT INTO library_item_state(item_type,item_id,archived,updated) "
            "VALUES(?,?,1,?) ON CONFLICT(item_type,item_id) DO UPDATE SET "
            "archived=1,updated=excluded.updated",
            (kind, item_id, time.time()),
        )
    return {"key": f"{kind}:{item_id}", "archived": True, "changed": changed}


@router.delete("/api/library/{kind}/{item_id}/archive")
def restore_library_item(kind: str, item_id: int):
    _require_item(kind, item_id)
    with transaction():
        current = q(
            "SELECT archived FROM library_item_state "
            "WHERE item_type=? AND item_id=?",
            (kind, item_id), one=True,
        )
        changed = bool(current and current["archived"])
        qi("DELETE FROM library_item_state WHERE item_type=? AND item_id=?",
           (kind, item_id))
    return {"key": f"{kind}:{item_id}", "archived": False, "changed": changed}
