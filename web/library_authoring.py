"""Bounded authoring projections and optimistic revision checks.

This module is a presentation seam, not a persistence authority. Domain
routes continue to perform every write; they may ask this seam to compare a
content-derived revision while holding their existing transaction lock.
"""

from __future__ import annotations

import hashlib
import json

from fastapi import APIRouter, HTTPException

from core.db import q
from story.character_schema import (
    character_name,
    normalize_character_data,
    normalize_persona_data,
    persona_name,
)


router = APIRouter()
KINDS = frozenset(("story", "character", "persona", "lore"))


def canonical_revision(document: dict) -> str:
    """Return a stable token for one normalized authoring document."""
    encoded = json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _json_object(value) -> dict:
    try:
        parsed = json.loads(value or "{}")
    except (TypeError, ValueError):
        parsed = {}
    return parsed if isinstance(parsed, dict) else {}


def _story_document(item_id: int) -> dict:
    row = q(
        "SELECT name,scenario,persona_id FROM chats WHERE id=?",
        (item_id,), one=True,
    )
    if not row:
        raise HTTPException(404, "Story not found")
    return {
        "name": str(row["name"] or ""),
        "scenario": str(row["scenario"] or ""),
        "persona_id": row["persona_id"],
    }


def _character_document(item_id: int) -> dict:
    row = q("SELECT sheet FROM characters WHERE id=?", (item_id,), one=True)
    if not row:
        raise HTTPException(404, "Character not found")
    return normalize_character_data(_json_object(row["sheet"]))


def _persona_document(item_id: int) -> dict:
    row = q("SELECT sheet FROM personas WHERE id=?", (item_id,), one=True)
    if not row:
        raise HTTPException(404, "Persona not found")
    return normalize_persona_data(_json_object(row["sheet"]))


def _lore_document(item_id: int) -> dict:
    row = q("SELECT * FROM lorebooks WHERE id=?", (item_id,), one=True)
    if not row:
        raise HTTPException(404, "Lorebook not found")
    return {
        "name": str(row["name"] or ""),
        "book_type": str(row["book_type"] or "general"),
        "summary": str(row["summary"] or ""),
        "parent_id": row["parent_id"],
        "scope_world_id": row["scope_world_id"],
        "scope_location_id": row["scope_location_id"],
        "inheritance_mode": str(row["inheritance_mode"] or "inherit"),
        "sort_order": int(row["sort_order"] or 0),
        "anchor_entity_id": row["anchor_entity_id"],
    }


_DOCUMENT_READERS = {
    "story": _story_document,
    "character": _character_document,
    "persona": _persona_document,
    "lore": _lore_document,
}


def authoring_document(kind: str, item_id: int) -> dict:
    reader = _DOCUMENT_READERS.get(str(kind or "").casefold())
    if not reader:
        raise HTTPException(404, "Unknown Library item type")
    return reader(int(item_id))


def assert_expected_revision(kind: str, item_id: int, expected) -> dict:
    """Refuse a stale replacement write and return current authority."""
    document = authoring_document(kind, item_id)
    revision = canonical_revision(document)
    if expected is not None and str(expected) != revision:
        raise HTTPException(409, detail={
            "code": "edit-conflict",
            "owner": f"{kind}:{int(item_id)}",
            "revision": revision,
            "document": document,
        })
    return {"document": document, "revision": revision}


def _story_cast(item_id: int) -> list[dict]:
    rows = q(
        "SELECT ch.id,COALESCE(cc.sheet,ch.sheet) AS sheet,cc.sheet AS override_sheet,"
        "cc.status FROM chat_chars cc JOIN characters ch ON ch.id=cc.char_id "
        "WHERE cc.chat_id=? ORDER BY ch.id",
        (item_id,),
    )
    return [{
        "id": int(row["id"]),
        "name": character_name(normalize_character_data(_json_object(row["sheet"]))),
        "state": str(row["status"] or "active"),
        "card_source": "chat" if row["override_sheet"] is not None else "library",
    } for row in rows]


def _story_personas(item_id: int, document: dict) -> list[dict]:
    result = []
    primary_id = document.get("persona_id")
    if primary_id is not None:
        row = q("SELECT id,sheet FROM personas WHERE id=?", (primary_id,), one=True)
        if row:
            result.append({
                "id": int(row["id"]),
                "name": persona_name(normalize_persona_data(_json_object(row["sheet"]))),
                "state": "primary",
            })
    for row in q(
        "SELECT p.id,p.sheet,cp.status FROM chat_personas cp "
        "JOIN personas p ON p.id=cp.persona_id WHERE cp.chat_id=? ORDER BY p.id",
        (item_id,),
    ):
        if primary_id is not None and int(row["id"]) == int(primary_id):
            continue
        result.append({
            "id": int(row["id"]),
            "name": persona_name(normalize_persona_data(_json_object(row["sheet"]))),
            "state": str(row["status"] or "active"),
        })
    return result


def _story_lore(item_id: int) -> list[dict]:
    story = q("SELECT lorebook_id FROM chats WHERE id=?", (item_id,), one=True)
    canon_id = story["lorebook_id"] if story else None
    result = []
    seen = set()
    if canon_id is not None:
        row = q(
            "SELECT id,name,origin_id FROM lorebooks WHERE id=?", (canon_id,), one=True,
        )
        if row:
            seen.add(int(row["id"]))
            result.append({
                "id": int(row["id"]), "name": str(row["name"] or ""),
                "state": "canon", "origin_id": row["origin_id"],
            })
    for row in q(
        "SELECT lb.id,lb.name,COALESCE(cl.origin_id,lb.origin_id) AS origin_id,"
        "cl.enabled FROM chat_lorebooks cl "
        "JOIN lorebooks lb ON lb.id=cl.lorebook_id "
        "WHERE cl.chat_id=? ORDER BY lb.id",
        (item_id,),
    ):
        if int(row["id"]) in seen:
            continue
        result.append({
            "id": int(row["id"]), "name": str(row["name"] or ""),
            "state": "attached" if row["enabled"] else "disabled",
            "origin_id": row["origin_id"],
        })
    return result


def _story_activity(item_id: int) -> dict:
    count = q(
        "SELECT COUNT(*) AS count FROM turns WHERE chat_id=?", (item_id,), one=True,
    )["count"]
    recent = [{
        "id": int(row["id"]), "idx": int(row["idx"]), "created": row["created"],
    } for row in q(
        "SELECT id,idx,created FROM turns WHERE chat_id=? ORDER BY idx DESC LIMIT 3",
        (item_id,),
    )]
    return {"turn_count": int(count or 0), "recent": recent}


def _story_issues(document: dict, lore: list[dict]) -> list[dict]:
    issues = []
    persona_id = document.get("persona_id")
    if persona_id is None:
        issues.append({"code": "missing-player-persona"})
    elif not q("SELECT 1 FROM personas WHERE id=?", (persona_id,), one=True):
        issues.append({"code": "missing-player-persona", "persona_id": persona_id})
    for item in lore:
        origin_id = item.get("origin_id")
        if origin_id is not None and not q(
            "SELECT 1 FROM lorebooks WHERE id=?", (origin_id,), one=True,
        ):
            issues.append({
                "code": "missing-lore-origin",
                "item_id": item["id"],
                "origin_id": origin_id,
            })
    return issues


def _story_overview(item_id: int, document: dict) -> dict:
    lore = _story_lore(item_id)
    return {
        "cast": _story_cast(item_id),
        "personas": _story_personas(item_id, document),
        "lore": lore,
        "activity": _story_activity(item_id),
        "issues": _story_issues(document, lore),
    }


def authoring_payload(kind: str, item_id: int) -> dict:
    normalized_kind = str(kind or "").casefold()
    document = authoring_document(normalized_kind, item_id)
    payload = {
        "kind": normalized_kind,
        "id": int(item_id),
        "owner": f"{normalized_kind}:{int(item_id)}",
        "document": document,
        "revision": canonical_revision(document),
    }
    if normalized_kind == "story":
        payload["overview"] = _story_overview(item_id, document)
    return payload


@router.get("/api/library/authoring/{kind}/{item_id}")
def library_authoring_get(kind: str, item_id: int):
    return authoring_payload(kind, item_id)
