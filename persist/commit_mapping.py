"""Lore/book mapping commit: proposed book ops, canon fallback ops, and the
off-screen event normaliser feeding it.

Extracted verbatim from commit.py, which re-exports every name here.
See docs/experiments/AUDIT_COMMIT.md for the split record.
"""

import json
from core.db import q, qi, transaction, wget, wset
from mind.memory import (search_lore, add_lore, update_lore, LORE_CATEGORIES,
                    LOREBOOK_TYPES, chat_lorebook_ids, chat_lorebook_weights,
                    lorebook_manifest, ensure_chat_canon_book)
from llm.providers import embed_texts
from llm.prompts import get_prompt
from story.character_schema import character_name_from_text, new_uid, persona_name
from core.frames import is_recognized_in_frame
from world.spatial import normalize_room_id
from persist.commit_common import (_canonical_anchor, _entity_alias_map, _keys_str,
                           _normalized_fact, _registered_name_roster,
                           _resolve_roster_name)
def normalize_offscreen_events(events):
    """Coerce a beat's off-screen ticks to one shape: [{actor, tick}].

    `MappingCommitOut.offscreen_events` is typed `list[dict]` with no inner
    model, so the model invented a shape per call and the stored logs prove it:
    across eight live chats the same field holds `{actor, tick}`, `{event}`,
    `{who, event}` and `{description}`. Nothing read the log, so nothing
    noticed — and the first reader would have had to handle all four, or
    silently miss three.

    An actor is optional and stays empty when the tick names none: inventing
    one would be worse than admitting the tick is about the world rather than
    about a person.
    """
    if not isinstance(events, list):
        return []
    out = []
    for entry in events:
        if isinstance(entry, str):
            text, actor = entry, ""
        elif isinstance(entry, dict):
            text = next(
                (str(entry[k]) for k in ("tick", "event", "description",
                                         "text", "summary")
                 if entry.get(k)), "")
            actor = next(
                (str(entry[k]) for k in ("actor", "who", "name", "character")
                 if entry.get(k)), "")
        else:
            continue
        text = " ".join(text.split())
        if not text:
            continue
        out.append({"actor": actor.strip(), "tick": text[:600]})
    return out

def _apply_mapping_book_ops(cid, lb, book_ops):
    """Deterministically validates and creates the child lorebooks
    mapping_commit proposed this turn (schemas.py's BookOp, prompts.py's
    BOOK CREATION rule) -- the model proposes a subject and a place in
    the tree, this function is what actually decides whether that's
    trustworthy enough to write, mirroring how every other model
    proposal in this codebase (state_diff, lore_ops themselves) is
    validated deterministically rather than applied on the model's say.
    Returns {temp_id: real_book_id} so lore_ops filed against a book
    that didn't have a database id a moment ago can still resolve it.
    """
    temp_map = {}
    if not book_ops:
        return temp_map

    existing = {
        row["id"]: row
        for row in q("SELECT * FROM lorebooks WHERE chat_id=?", (cid,))
    }
    created = 0
    alias_map = None  # built lazily -- most turns propose no books
    for op in book_ops:
        if not isinstance(op, dict) or op.get("op") != "create":
            continue
        if created >= 3:
            # Cap per turn -- a single beat introducing dozens of new
            # subjects at once is almost always a validation failure
            # upstream, not a genuine worldbuilding moment; the rest
            # fall back to the canon book via the caller's normal
            # target_book_id resolution, not lost.
            continue
        name = str(op.get("name") or "").strip()
        if not name:
            continue
        book_type = op.get("book_type") if op.get("book_type") in LOREBOOK_TYPES else "general"
        anchor = str(op.get("anchor_entity_id") or "").strip() or None
        scope_loc = str(op.get("scope_location_id") or "").strip() or None
        # Anchor-alias + normalized-name dedup: comparing raw anchor ids
        # let two DIFFERENT entity-id aliases of ONE vehicle
        # ('ferry_tamsin' vs 'tamsin_ferry_entity') mint two books for the
        # same ship. Resolve both sides to a canonical entity first, and
        # compare names by slug so punctuation/case drift can't fork a
        # book either. One vehicle -> one book.
        if alias_map is None:
            alias_map = _entity_alias_map(cid)
        canon_anchor = _canonical_anchor(anchor, alias_map)
        name_slug = normalize_room_id(name)

        dup = next((
            row for row in existing.values()
            if normalize_room_id(row["name"]) == name_slug
            or (canon_anchor and _canonical_anchor(
                row["anchor_entity_id"], alias_map) == canon_anchor)
            or (scope_loc and row["book_type"] == book_type and row["scope_location_id"] == scope_loc)
        ), None)
        if dup:
            if op.get("temp_id"):
                temp_map[op["temp_id"]] = dup["id"]
            continue

        raw_parent = op.get("parent_id")
        if isinstance(raw_parent, str):
            # A same-turn temp handle, or an existing book's id spelled as
            # text. `parent_id` is declared `Union[int, str]` for exactly
            # that reason, and which of the two survives validation now
            # depends on the Pydantic major: 1.x tried `int` first and
            # coerced `"77"` to 77, 2.x's smart union keeps the string. So a
            # digit string has to be read as the id it is, or the book
            # silently reparents to canon root on 2.x -- the same op, filed
            # somewhere else, with nothing logged. Matches how lore_ops
            # already resolves `book_id` below.
            parent_id = temp_map.get(raw_parent) or (
                int(raw_parent) if raw_parent.isdigit() else None
            )
        else:
            parent_id = raw_parent
        if not isinstance(parent_id, int) or parent_id not in existing:
            parent_id = lb  # keeps the tree rooted under canon -- never an unreachable orphan

        inheritance_mode = op.get("inheritance_mode") if op.get("inheritance_mode") in (
            "inherit", "isolated") else "inherit"
        new_id = qi(
            "INSERT INTO lorebooks(name,chat_id,book_type,summary,parent_id,"
            "inheritance_mode,scope_world_id,scope_location_id,anchor_entity_id,resource_uid) "
            "VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                name, cid, book_type, str(op.get("summary") or "")[:500], parent_id,
                inheritance_mode,
                str(op.get("scope_world_id") or "").strip() or None,
                # Store the CANONICAL entity id (not the model's alias
                # spelling) so sync_anchored_books and future dedup all
                # agree on which entity this book tracks.
                scope_loc, canon_anchor, new_uid("book"),
            ),
        )
        created += 1
        existing[new_id] = {
            "id": new_id, "name": name, "book_type": book_type,
            "anchor_entity_id": canon_anchor, "scope_location_id": scope_loc,
        }
        if op.get("temp_id"):
            temp_map[op["temp_id"]] = new_id
    return temp_map

def prepare_mapping_commit(ctx):
    """Resolve and embed mapping operations without mutating durable state.

    Mapping commit may require a long LLM round-trip and one or more remote
    embedding calls.  Preparing those decisions before the outer turn
    transaction prevents network latency from holding SQLite's write lock and
    lets commit_all apply every durable domain atomically.
    """
    chat = ctx.chat
    turn = ctx.turn
    cid = chat.id
    res = ctx.director_resolve or ctx.director_establish or {}
    diff = res.get("state_diff") or {}
    book_ids = chat_lorebook_ids(cid)
    # Narration is a rendering layer, not a source of objective truth.
    # `new_specifics` is an audit field for unsupported details the narrator
    # accidentally introduced; never launder those details into canon through
    # the privileged mapping agent.
    narrator_specificity_flags = (ctx.narrator or {}).get("new_specifics") or []
    if narrator_specificity_flags:
        ctx.add_warning(
            "Narrator-originated specifics were excluded from canon: "
            + "; ".join(map(str, narrator_specificity_flags[:8]))
        )
    specifics = []
    staged = (ctx.mapping_stage or {}).get("staged_lore") or []
    world_facts = diff.get("world_facts") or []
    introductions = diff.get("introductions") or []
    seed = f"tick:{cid}:{turn.idx}"

    if not (staged or world_facts or introductions):
        return {
            "skipped": True,
            "mout": {"skipped": "nothing new to commit"},
            "ops": [],
            "book_ops": [],
            "book_ids": book_ids,
            "seed": seed,
        }

    lore_ctx = search_lore(
        chat_lorebook_weights(cid),
        " ".join(map(str, specifics)) or res.get("summary", ""), k=10,
    )
    raw_shadow = wget(cid, "shadow_profile", "") or ""
    raw_intents = wget(cid, "standing_intentions", []) or []
    # Off-screen ticks no longer ride this call AT ALL. The dormant cast is
    # not offered to the model at any level: the stochastic rung is a seeded
    # draw in `offscreen.stochastic_ticks` (free, replayable), taken in
    # `offscreen.advance_epoch` -- a commit domain of its own
    # (`commit.commit_offscreen_epoch`), which this module neither calls nor
    # imports -- and the model-priced rung above it is the out-of-band
    # profile summary. Asking a lore validator to also author offscreen life
    # was an unadjudicated authoring channel wearing a payload field -- and
    # the seed it was shown seeded nothing, since no RNG ever consumed it.
    payload = {
        "proposed_specifics": specifics,
        "narrator_specificity_audit": narrator_specificity_flags,
        "staged_lore_to_confirm": staged,
        "world_facts": world_facts,
        "existing_lore": lore_ctx,
        "lorebook_manifest": lorebook_manifest(cid),
        "resolved_summary": res.get("summary") or (res.get("resolved_event") or "")[:400],
        "player_public_behavior": {
            "speech": (ctx.director_interpret or {}).get("speech"),
            "visible_action": ((ctx.director_interpret or {}).get("action") or {}).get("attempt"),
        },
        "current_shadow_profile": raw_shadow[:1200],
        # `scene_changed` stays truthful about the scene; it is a fact about
        # the world, not a gate on anything.
        "scene_changed": bool(ctx.director_establish),
        "standing_intentions": raw_intents[:12],
        "beat_introductions": diff.get("introductions") or [],
        "beat_dialogue_log": res.get("dialogue_log") or [],
        "beat_resolved_event": res.get("resolved_event") or "",
    }
    try:
        from llm.llm_quality import complete_validated_json

        mout = complete_validated_json(
            role="mapping",
            step_key="mapping_commit",
            system=get_prompt("mapping_commit"),
            payload=payload,
            temperature=0.0,
            repair_attempts=1,
        )
    except Exception as e:
        ctx.add_warning(f"mapping_commit failed: {e}")
        mout = {
            "validated": [],
            "lore_ops": [],
            "coherence_notes": [f"mapping commit failed: {e}"],
        }

    validated_list = mout.get("validated") if isinstance(mout.get("validated"), list) else []
    ok_facts = [v for v in validated_list if isinstance(v, dict) and v.get("ok")]
    ops = mout.get("lore_ops") if isinstance(mout.get("lore_ops"), list) else []
    ops = [dict(o) for o in ops if isinstance(o, dict) and o.get("content")]
    book_ops = mout.get("book_ops") if isinstance(mout.get("book_ops"), list) else []
    book_ops = [dict(o) for o in book_ops if isinstance(o, dict)]

    if not ops:
        ops = _generate_fallback_ops(
            ok_facts, staged, world_facts, existing_lore=lore_ctx,
        )
    for o in ops:
        if "keys" in o:
            o["keys"] = _keys_str(o["keys"])

    # Lore embeddings are independent of final routing/book IDs. Compute them
    # in one batch now rather than one remote call per operation while the
    # database transaction is open.
    if ops:
        vectors = embed_texts([
            (str(o.get("keys") or "") + " " + str(o.get("content") or "")).strip()
            for o in ops
        ])
        if len(vectors) != len(ops):
            raise RuntimeError("Lore embedding provider returned an unexpected vector count")
        for op, vector in zip(ops, vectors):
            op["_embedding"] = vector

    return {
        "skipped": False,
        "mout": mout,
        "ops": ops,
        "book_ops": book_ops,
        "book_ids": book_ids,
        "seed": seed,
    }


def commit_mapping(ctx, nonce, *, prepared=None):
    chat = ctx.chat
    turn = ctx.turn
    cid = chat.id
    prepared = prepared or prepare_mapping_commit(ctx)
    mout = prepared["mout"]
    book_ids = prepared["book_ids"]
    seed = prepared["seed"]

    if prepared.get("skipped"):
        wset(cid, "lore_cache", _lore_for(ctx)[:12])
        mstep = ctx.mapping_stage or ctx.mapping_quick or {}
        if not mstep.get("cached") and isinstance(mstep.get("relevant_books"), list):
            wset(cid, "active_books", mstep["relevant_books"])
        return {
            "mout": mout,
            "applied": {"created": 0, "updated": 0},
            "book_ids": book_ids,
            "seed": seed,
        }

    ops = prepared["ops"]
    book_ops = prepared["book_ops"]
    applied = {"created": 0, "updated": 0}
    lb = chat.lorebook_id
    if (ops or book_ops) and not lb:
        # One spelling of "the chat's canon book", shared with the other writer
        # that can mint it first (background_claims.write_canon).
        lb = ensure_chat_canon_book(cid)

    temp_book_map = _apply_mapping_book_ops(cid, lb, book_ops)
    valid_books = set(chat_lorebook_ids(cid))
    with transaction() as c:
        for o in ops:
            cat = o.get("category") if o.get("category") in LORE_CATEGORIES else "other"
            kloc = (
                json.dumps(o.get("knowledge_locations") or [])
                if o.get("knowledge_locations") else None
            )
            raw_book_id = o.get("book_id")
            if isinstance(raw_book_id, str):
                raw_book_id = temp_book_map.get(raw_book_id) or (
                    int(raw_book_id) if raw_book_id.isdigit() else None
                )
            target_book_id = raw_book_id or lb
            if target_book_id not in valid_books:
                target_book_id = lb

            if o.get("op") == "update" and o.get("id"):
                row = q("SELECT * FROM lore_entries WHERE id=?", (o["id"],), one=True)
                if row and row["lorebook_id"] in valid_books and not row["canon_locked"]:
                    update_lore(
                        o["id"], o.get("keys", row["keys"]), o["content"], cat,
                        title=o.get("title"), knowledge_tag=o.get("knowledge_tag"),
                        knowledge_range=o.get("knowledge_range"),
                        knowledge_locations=kloc,
                        embedding=o.get("_embedding"),
                    )
                    applied["updated"] += 1
                    continue
            add_lore(
                target_book_id, o.get("keys", ""), o["content"],
                turn_added=turn.idx, category=cat, title=o.get("title"),
                knowledge_tag=o.get("knowledge_tag"),
                knowledge_range=o.get("knowledge_range"),
                knowledge_locations=kloc,
                embedding=o.get("_embedding"),
            )
            applied["created"] += 1
        if lb:
            c.execute(
                "UPDATE lore_entries SET canon_locked=1 "
                "WHERE lorebook_id=? AND turn_added IS NOT NULL AND turn_added<=?",
                (lb, turn.idx - 20),
            )

    wset(cid, "lore_cache", _lore_for(ctx)[:12])
    mstep = ctx.mapping_stage or ctx.mapping_quick or {}
    if not mstep.get("cached") and isinstance(mstep.get("relevant_books"), list):
        wset(cid, "active_books", mstep["relevant_books"])
    if mout.get("shadow_profile"):
        sp = mout["shadow_profile"]
        if isinstance(sp, str) and len(sp) > 2000:
            sp = sp[:2000]
        wset(cid, "shadow_profile", sp)
    if mout.get("standing_intentions"):
        si = mout["standing_intentions"]
        if isinstance(si, list) and len(si) > 20:
            si = si[-20:]
        wset(cid, "standing_intentions", si)
    _volunteered = normalize_offscreen_events(mout.get("offscreen_events"))
    if _volunteered:
        # Nothing asks the model for ticks any more, so anything here is a
        # field nobody requested -- refused on the write path regardless of
        # the chat's level, because a model-authored tick is an
        # unadjudicated authoring channel whatever the setting says.
        ctx.add_warning(
            f"discarded {len(_volunteered)} model-volunteered off-screen "
            "tick(s): ticks are drawn seeded, not authored")
    known = wget(cid, "known", {})
    # WIDE for resolution: an introduction naming an offscreen person is still
    # a sentence about a real person, and dropping it silently is the defect.
    # The EDGE it would write is gated separately, below.
    roster = _registered_name_roster(chat, ctx.cast)
    name_to_id = {character_name_from_text(r["sheet"]): r["id"] for r in ctx.cast}
    for vi in (mout.get("validated_introductions") or []):
        if not isinstance(vi, dict) or not vi.get("ok"):
            continue
        who = _resolve_roster_name(vi.get("who"), roster)
        learns = _resolve_roster_name(
            vi.get("corrected_learns") or vi.get("learns"), roster,
        )
        if not (who and learns):
            continue
        # TWO REQUIREMENTS, KEPT SEPARATE. The roster above answers "is this a
        # person the story knows about", which is what resolving a name needs.
        # An introduction needs more: somebody has to have been THERE to be
        # introduced. Now that the roster includes offscreen characters, a
        # single check would let the model write an introduction between two
        # people who were both absent -- trading a missed edge for an invented
        # one, which is worse, because a wrong edge is indistinguishable from a
        # right one afterwards and nothing downstream can catch it.
        from story.scene import persona_of as _persona_of
        present = {character_name_from_text(r["sheet"]) for r in ctx.cast}
        player = (persona_name(_persona_of(chat)) or "").strip()
        if player:
            present.add(player)
        # BOTH parties. `learns` had a frame gate and `who` had none, and that
        # gate SKIPS rather than blocks for anyone outside `ctx.cast` -- which
        # is exactly the set the wider roster has just admitted. Hanging the
        # requirement off an id lookup would open it for them instead of
        # closing it, so this is a positive test against who was on stage.
        if who not in present or learns not in present:
            continue
        learns_id = name_to_id.get(learns)
        if learns_id is not None and not is_recognized_in_frame(learns_id, turn.frame_id):
            continue
        known.setdefault(who, [])
        if learns not in known[who]:
            known[who].append(learns)
    wset(cid, "known", known)
    return {"mout": mout, "applied": applied, "book_ids": book_ids, "seed": seed}

# ---- Fallback helpers ----

def _lore_for(ctx):
    return (ctx.mapping_stage or ctx.mapping_quick or {}).get("relevant_lore") or []


def _fact_is_covered(fact, existing_lore):
    normalized = _normalized_fact(fact)
    if not normalized:
        return True
    fact_tokens = set(normalized.split())
    for entry in existing_lore or []:
        candidate = _normalized_fact(entry.get("content") or "")
        if not candidate:
            continue
        if normalized in candidate or candidate in normalized:
            return True
        candidate_tokens = set(candidate.split())
        union = fact_tokens | candidate_tokens
        if union:
            similarity = len(fact_tokens & candidate_tokens) / len(union)
            if similarity >= 0.72:
                return True
    return False

def _generate_fallback_ops(ok_facts, staged, world_facts, existing_lore=None):
    existing_lore = existing_lore or []
    ops = []
    for fact in ok_facts:
        text = str(fact.get("fact") or "")
        if text and not _fact_is_covered(text, existing_lore):
            ops.append({"op": "create", "keys": "", "content": text, "category": "event", "book_id": None})
    for entry in staged:
        content = str(entry.get("content") or "")
        if not content or _fact_is_covered(content, existing_lore):
            continue
        ops.append({
            "op": "create", "keys": entry.get("keys", ""), "content": content,
            "category": entry.get("category", "other"), "title": entry.get("title"),
            "knowledge_tag": entry.get("knowledge_tag"),
            "knowledge_range": entry.get("knowledge_range"),
            "knowledge_locations": entry.get("knowledge_locations"),
            "book_id": entry.get("book_id"),
        })
    for world_fact in world_facts:
        if isinstance(world_fact, dict):
            text = str(world_fact.get("fact") or "")
            source_kind = (world_fact.get("source") or {}).get("kind")
        else:
            text = str(world_fact)
            source_kind = None
        if source_kind == "lore":
            continue
        if text and not _fact_is_covered(text, existing_lore):
            ops.append({"op": "create", "keys": "", "content": text, "category": "other", "book_id": None})
    return [o for o in ops if o.get("content")]
