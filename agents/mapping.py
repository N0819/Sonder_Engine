"""Lore routing and retrieval agents."""

from __future__ import annotations

from character_schema import (
    persona_appearance,
    persona_name,
    persona_public_history,
)
from db import wget
from memory import lorebook_manifest, search_lore, resolve_lorebook_graph
from prompts import get_prompt
from scene import (
    cast_scene_context,
    director_context,
    fiction_model,
    get_scene,
    persona_of,
    recent_events,
)

from .common import (
    _agent_json,
    _books,
    _book_weights,
    _join_text,
    _lore_fingerprint,
    _normalize_scene_patch,
)

def mapping_stage(ctx, nonce):
    chat = ctx.chat
    interp = ctx.get("director_interpret") or {}
    fl = interp.get("flow", {})

    pieces = [e.get("text") or e.get("attempt") or ""
              for e in (interp.get("sequence") or [])]
    pieces += [fl.get("mapping_request") or "",
               interp.get("location_query") or "", ctx.input or ""]
    pieces += recent_events(chat["id"], 5)

    if not ctx.get("director_interpret"):
        pieces += [chat.get("scenario") or ""]
        for actor in cast_scene_context(ctx.cast):
            pieces.extend([
                actor["name"],
                actor["public_history"],
                actor["opening_context"],
                " ".join(str(ab.get("name") or "") for ab in actor["abilities"]
                         if isinstance(ab, dict)),
                " ".join(str(ab.get("notes") or "") for ab in actor["abilities"]
                         if isinstance(ab, dict)),
            ])

    query = _join_text(pieces)
    books = _books(ctx, refresh=True)
    weights = _book_weights(ctx, refresh=True)
    hits = search_lore(weights, query, k=14, exclude_categories=["knowledge"])

    pers = persona_of(chat)

    payload = {
        "director_recent_messages": director_context(chat["id"], 5),
        "player_action": {
            "sequence": interp.get("sequence") or [],
            "speech": interp.get("speech"),
            "action": (interp.get("action") or {}).get("attempt"),
        },
        "player_raw_input": ctx.input or "",
        "scenario": chat.get("scenario") or "",
        "player": {
            "name": persona_name(pers),
            "appearance": persona_appearance(pers),
            "public_history": persona_public_history(pers),
        },
        "present_characters": cast_scene_context(ctx.cast),
        "location_query": interp.get("location_query"),
        "lorebook_manifest": lorebook_manifest(chat["id"]),
        "currently_active_books": wget(chat["id"], "active_books", None),
        "candidate_lore": hits,
        "scene": get_scene(chat["id"], chat),
        "fiction_model": fiction_model(chat["id"]),
        "pending": wget(chat["id"], "pending", []),
        "variant_seed": nonce,
    }

    out = _agent_json(
        "mapping",
        "mapping_stage",
        get_prompt("mapping_stage"),
        payload,
        temperature=0.2,
    )

    out.setdefault("relevant_lore", [])
    out.setdefault("staged_lore", [])
    out["scene_patch"] = _normalize_scene_patch(out.get("scene_patch"))

    valid = set(books)
    rb = []
    for b in (out.get("relevant_books") or []):
        try:
            bi = int(b)
        except Exception:
            continue
        if bi in valid and bi not in rb:
            rb.append(bi)
    out["relevant_books"] = rb
    out["candidates"] = hits
    return out

def mapping_quick(ctx, nonce):
    chat = ctx.chat
    interp = ctx.get("director_interpret") or {}
    sc = get_scene(chat["id"], chat)
    mv = interp.get("movement")
    if isinstance(mv, dict) and mv.get("to_room"):
        if mv["to_room"] not in (sc.get("rooms") or {}):
            return mapping_stage(ctx, nonce)
    if interp.get("location_query"):
        return mapping_stage(ctx, nonce)
    mr = ((interp.get("flow") or {}).get("mapping_request") or "").lower()
    if "new room" in mr or "generate room" in mr or "scene graph" in mr:
        return mapping_stage(ctx, nonce)

    pieces = [ctx.input or ""]
    pieces += [e.get("text") or e.get("attempt") or ""
               for e in (interp.get("sequence") or [])]
    pieces += recent_events(chat["id"], 3)
    books = _books(ctx)
    active = wget(chat["id"], "active_books", None)
    canon = chat.get("lorebook_id")
    if isinstance(active, list) and active:
        # `active` is whatever specific book ids the last full mapping_
        # stage call flagged as relevant_books -- typically just the
        # current location, not its ancestor region/setting book, even
        # though that ancestor is exactly the kind of thing a location
        # should keep inheriting from. A flat intersection against
        # `books` (already hierarchy-expanded) silently dropped any
        # ancestor that active's own listing didn't happen to name --
        # re-expand active through the hierarchy again before
        # intersecting, so its ancestors survive here too.
        expanded = {r["id"] for r in resolve_lorebook_graph(active, chat_id=chat["id"])}
        if canon:
            expanded.add(canon)
        sel = [b for b in books if b in expanded]
        if not sel:
            sel = books
    else:
        sel = books
    query = _join_text(pieces)
    weights = _book_weights(ctx)
    hits = search_lore(
        {b: weights.get(b, 1.0) for b in sel},
        query,
        k=8,
        exclude_categories=["knowledge"],
    )
    cache = wget(chat["id"], "lore_cache", []) or []
    seen, merged = set(), []
    for e in hits + cache:
        if not isinstance(e, dict):
            continue
        key = e.get("entry_uid") or _lore_fingerprint(e)
        if key in seen:
            continue
        seen.add(key)
        merged.append(e)
    return {
        "relevant_lore": merged[:12], "staged_lore": [],
        "scene_patch": {
            "rooms": {}, "entities": {},
            "positions": {}, "remove_entities": [], "remove_rooms": [],
        },
        "cached": True,
        "summary": f"{len(merged[:12])} lore entries recalled from "
                   f"{len(sel)} active book(s) (no mapping call needed).",
    }
