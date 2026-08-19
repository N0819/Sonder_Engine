"""Lore routing and retrieval agents."""

from __future__ import annotations

from story.character_schema import (
    persona_appearance,
    persona_name,
    persona_public_history,
)
from core.db import wget
from mind.memory import lorebook_manifest, search_lore, resolve_lorebook_graph
from llm.prompts import get_prompt
from story.scene import (
    cast_scene_context,
    director_context,
    fiction_model,
    get_scene,
    persona_of,
    recent_events,
    style_guide,
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
    # Living world, approach D: a location entry the mapping agent is about
    # to work from may carry the history the unvisited place has accrued
    # (living_world.owed_history). This seam is the obligation ledger's ONLY
    # consumer -- the place's debt surfaces where the place itself is
    # generated, never in any mind's payload; arrival is the earning event.
    try:
        from world.living_world import attach_owed_history
        hits = attach_owed_history(chat["id"], hits)
    except Exception as exc:
        ctx.add_warning(f"owed history not attached: {exc}")

    pers = persona_of(chat)

    payload = {
        # X18: mapping is NOT entitled to the omniscient record. It emits lore
        # entries and scene_patch room notes, and room_notes is served into
        # every perceiver's payload -- so an unscrubbed concealed line here
        # launders into everyone's context two model hops later.
        "director_recent_messages": director_context(
            chat["id"], 5, entitled=False),
        "player_action": {
            "sequence": interp.get("sequence") or [],
            "speech": interp.get("speech"),
            "action": (interp.get("action") or {}).get("attempt"),
        },
        "player_raw_input": ctx.input or "",
        "scenario": chat.get("scenario") or "",
        # Authored house style for generated content (see scene.style_guide).
        # Omitted entirely when unset, so the self-determining default path is
        # byte-identical to what it was before this existed.
        **({"style_guide": style_guide(chat["id"])}
           if style_guide(chat["id"]) else {}),
        "player": {
            "name": persona_name(pers),
            "appearance": persona_appearance(pers),
            "public_history": persona_public_history(pers),
        },
        "present_characters": cast_scene_context(ctx.cast),
        "location_query": interp.get("location_query"),
        # Captured player declarations forwarded for BOUNDED ADDITIVE
        # elaboration (see the GENERATION REQUESTS prompt rule): the player
        # owns the declared existence and stated specifics; mapping owns
        # only what was left unstated, at the scale of the declaration.
        "generation_requests": [
            g for g in (fl.get("generation_requests") or [])
            if isinstance(g, dict)
        ],
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
        get_prompt("mapping_stage", ctx.language),
        payload,
        temperature=0.2,
    )

    out["relevant_lore"] = _join_relevant_lore(
        ctx, out.get("relevant_lore"), hits)
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
    # The full candidate list is NOT stored back on the step. Nothing read it
    # -- the entries the model actually cited are already merged into
    # `relevant_lore` above, from this same in-memory `hits`, and
    # `common.lore_for` is the only consumer of a stored mapping step. Live,
    # it was 462 of 463 active mapping_stage variants and 4,961,385 of
    # 7,510,198 stored bytes: 66% of the step, riding every checkpoint,
    # branch, archive and trace as opaque content, and re-read on every
    # rerun's hydration.
    return out


# The entry text the engine hands the model, and the entry text the engine
# takes back, are the same rows -- so the return trip is transcription, and
# transcription is where a lore entry quietly loses sentences.
#
# Measured over all 416 real mapping calls in the corpus (855 relevant_lore
# entries): 86.3% of echoed `content` came back byte-identical, 5.8% came
# back truncated, and 7.7% came back rewritten at a median 59% of the true
# length. That mutated 13.6% is not a cosmetic loss. `lore_for` forwards the
# echo into the Director's payloads, and `commit.py` writes it into
# `lore_cache`, which `mapping_quick` then re-serves with NO further model
# call for 1,879 of 1,881 measured steps -- so one abridged echo becomes the
# served copy of that entry until the next real mapping call happens to
# replace it. The engine still holds every candidate in `hits` two hundred
# lines up; joining by id is free, in memory, and cannot abridge anything.
#
# What the model is still authoring, and what this must not touch: WHICH
# entries are relevant, and `why_relevant`. That judgement is the whole
# point of the ask. Only the echo goes.
_LORE_JOINED_FIELDS = (
    "entry_uid", "book_id", "keys", "content", "category", "locked")


def _join_relevant_lore(ctx, entries, hits):
    """Replace the model's echoed lore text with the engine's own rows.

    An id the engine never offered keeps whatever the model wrote and warns:
    that is either a hallucinated citation or an entry retrieved by some
    path this function does not know about, and silently dropping either
    one would hide it.
    """
    by_id = {}
    for hit in (hits or []):
        if isinstance(hit, dict) and hit.get("id") is not None:
            by_id[str(hit["id"])] = hit
    joined, uncited = [], []
    for entry in (entries or []):
        if not isinstance(entry, dict):
            continue
        source = by_id.get(str(entry.get("id")))
        if source is None:
            uncited.append(entry.get("id"))
            joined.append(entry)
            continue
        merged = dict(entry)
        for field in _LORE_JOINED_FIELDS:
            if field in source:
                merged[field] = source[field]
        joined.append(merged)
    if uncited:
        ctx.add_warning(
            "mapping cited lore not offered as a candidate "
            f"(ids {uncited}); their text is the model's own and was not "
            "verified against a stored entry")
    return joined


# The phrases in the Director's free-text `flow.mapping_request` that mean this
# beat needs a place STAGED rather than recalled.
#
# One list, because there were two and they had already drifted apart by
# `"new location"`. They answer adjacent questions -- runtime's
# `_mapping_must_precede_perception` decides whether mapping must run BEFORE
# perception, `mapping_quick` below decides whether cached recall may serve at
# all -- but a request that forces the serialization and does not force the
# staging produces the worst of both: mapping runs first, cheaply, and the
# location is never staged, so perception's room-notes fallback reads nothing.
#
# Still a naked substring test against model-authored prose, which is the
# literal-guard shape that fails when a model rewrites. Keeping it in one place
# is what makes replacing it with a structured signal a single edit later.
STAGING_REQUEST_PHRASES = (
    "new room", "generate room", "scene graph", "new location")


def mapping_request_stages_a_room(request) -> bool:
    """True when `flow.mapping_request` asks for a place to be brought into
    existence, rather than for lore about one that already is."""
    text = str(request or "").casefold()
    return any(phrase in text for phrase in STAGING_REQUEST_PHRASES)


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
    if (interp.get("flow") or {}).get("generation_requests"):
        # A captured player declaration awaits elaboration -- cached recall
        # cannot mint the declared content; escalate to the full stage.
        return mapping_stage(ctx, nonce)
    if mapping_request_stages_a_room(
            (interp.get("flow") or {}).get("mapping_request")):
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
    merged = merge_lore(hits, cache)
    return {
        "relevant_lore": merged[:12], "staged_lore": [],
        # The same normalizer `mapping_stage` runs, rather than the same shape
        # written out again: this copy was already a field behind
        # (`remove_adjacent`), and it survived only because every consumer
        # spells the read `diff.get("remove_adjacent") or []`. The next field
        # the normalizer grows would be missing here too, silently.
        "scene_patch": _normalize_scene_patch({}),
        "cached": True,
        "summary": f"{len(merged[:12])} lore entries recalled from "
                   f"{len(sel)} active book(s) (no mapping call needed).",
    }


def merge_lore(hits, cache):
    """Fresh retrieval first, cached entries after, one copy of each entry.

    `id` FIRST, because it is the one field two revisions of the same entry
    must share. Lore entries ACCRETE -- the engine appends narrative events to
    them -- and the cache stores SNAPSHOTS rather than references, so the same
    entry can sit here twice at two lengths.

    `entry_uid or fingerprint` could not collide those. A cached dict written
    before the uid was carried through has none, so it falls to the
    fingerprint, and a uid and a fingerprint live in different namespaces. The
    fingerprint cannot rescue it either: it hashes keys+content, which is
    exactly what differs between two revisions.

    Measured live, chat 59: ten cached entries, nine distinct ids, entry 2213
    present twice at 1,572 and 1,442 characters. The shorter copy predates a
    sentence the longer one carries, so the model was handed the same room
    twice at two revisions, one of which did not know a character had gone
    upstairs. A contradiction served as retrieved lore, not a wasted slot.

    `hits` precede `cache`, so keeping the first occurrence keeps the freshly
    retrieved revision and drops the fossil.
    """
    seen, merged = set(), []
    for e in list(hits or []) + list(cache or []):
        if not isinstance(e, dict):
            continue
        key = e.get("id") or e.get("entry_uid") or _lore_fingerprint(e)
        if key in seen:
            continue
        seen.add(key)
        merged.append(e)
    return merged
