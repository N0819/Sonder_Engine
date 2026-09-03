"""Lore/book filing commit: what a beat established, as typed records --
no model in the loop, and since 2026-09-03 no LORE either.

Extracted verbatim from commit.py in the 2026-08 split, which re-exports
every name here (see docs/experiments/AUDIT_COMMIT.md). Rewritten 2026-09-04
with the mapping model's retirement, and again 2026-09-03 when the physical
map became the story's record: `prepare_mapping_commit` used to file every
described room as a `layout` lore entry and every Director `world_fact`
through a fallback writer. Both were a second representation of something
the engine already held or was not the Director's to author:

  * ROOM FILINGS -- RETIRED. The room registry and the frame-scoped scene
    ARE the record of a room; a layout entry was a retrieval index over
    them for a model stage that no longer exists. Room notes are read from
    the scene (`agents.common._room_notes_from_lore`). Existing layout
    entries stay readable and age out unrefreshed; nothing files new ones.
  * WORLD FACTS -- A PLANNING NEED. A Director `world_fact` with no
    physical seat is a SETTING fact, and the setting bible is the Writers'
    Room's to file with provenance and a knowledge gate (v2 § 9.4). It is
    recorded as a `setting_fact` need (`world/planning_needs.py`) when no
    entry already covers it, and filed by nobody here.
  * INTRODUCTIONS -- the Director's typed `introductions`, applied under
    the same presence and same-room gates the model's verdicts were
    (UNBUILT § 3.5 P7's "validated by model judgment", closed here).
  * PLANNING NEEDS -- what the world-context compiler found the beat
    reaching for that no plan holds, recorded on the frame's ledger with
    the surface the beat committed attached (`world/planning_needs.py`).
    A room-need whose committed record carries `parent_entity` is DROPPED:
    where a body walks is its own; where the world puts it -- inside
    another body -- is the Director's, a place the moment it happens, and
    no plan can hold it in advance.
"""

import json
from core.db import q, qi, transaction, wget, wset
from mind.memory import (search_lore, add_lore, update_lore, LORE_CATEGORIES,
                    LOREBOOK_TYPES, chat_lorebook_ids, chat_lorebook_weights,
                    ensure_chat_canon_book)
from story.character_schema import character_name_from_text, new_uid, persona_name
from story.provenance_text import split_engine_provenance
from core.frames import is_recognized_in_frame
from world.spatial import normalize_room_id
from persist.commit_common import (_address_index, _canonical_anchor,
                           _entity_alias_map, _keys_str,
                           _normalized_fact, _registered_name_roster,
                           _resolve_roster_name, _room_of,
                           charter_recognition_projection)
# A stable, greppable stamp on the provenance column, the same shape
# `world/background_claims.CANON_SOURCE_PREFIX` uses for a ratified claim. It
# is also the denominator: `SELECT count(*) FROM lore_entries WHERE
# source_notes LIKE 'engine-generated%'` is how anyone finds every description
# the engine invented for a place canon had not described.
GENERATED_SOURCE_PREFIX = "engine-generated"

#: A setting fact's subject on the need it raises: the fact itself, capped
#: where the ledger caps a subject.
SETTING_FACT_SUBJECT_CHARS = 120


def _file_engine_provenance(op):
    """Move the engine's bookkeeping out of a lore entry's prose and into
    `source_notes`.

    A `layout` entry staged for a room no candidate described is asked to
    declare that it was generated -- the declaration is what keeps a wrong
    guess cheap to find and correct. It was declared IN THE ENTRY'S TEXT, and
    that text is what becomes the room's description and every observer's room
    notes, so a character standing in the room was told "generated because no
    candidate described this location" as a fact about the room (measured, chat
    95 beat 7).

    Same signal, different column. `source_notes` is already the provenance
    column, is returned by the lore API (`web/app.py`), and reaches no prompt
    and no view. The structured `provenance` field rides along here too, so
    the declaration survives whichever way it arrives.
    """
    prose, note = split_engine_provenance(op.get("content"))
    declared = " ".join(str(op.get("provenance") or "").split())
    stamp = "; ".join(p for p in (declared, note) if p)
    if not stamp:
        return op
    op["content"] = prose
    existing = str(op.get("source_notes") or "").strip()
    op["source_notes"] = "; ".join(
        ([existing] if existing else [])
        + ["%s: %s" % (GENERATED_SOURCE_PREFIX, stamp)])
    return op


def _apply_mapping_book_ops(cid, lb, book_ops):
    """Deterministically validates and creates the child lorebooks an
    authoring seam proposed this turn (schemas.py's BookOp) -- the proposer
    names a subject and a place in the tree, this function is what actually
    decides whether that's trustworthy enough to write, mirroring how every
    other proposal in this codebase (state_diff, lore ops themselves) is
    validated deterministically rather than applied on the proposer's say.
    Returns {temp_id: real_book_id} so lore ops filed against a book that
    didn't have a database id a moment ago can still resolve it.

    No turn stage proposes books any more (the mapping model that did is
    retired); this survives for the authoring package that will
    (v2 § 9.4's `apply_authoring_change`), and for its own tests.
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
            # somewhere else, with nothing logged. Matches how lore ops
            # already resolve `book_id` below.
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
                # Store the CANONICAL entity id (not the proposer's alias
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
    """Resolve the beat's typed records without mutating durable state.

    No model is consulted and no lore is embedded: what this prepares is the
    Director's typed introductions, the compiler's planning needs, and the
    setting facts the Director asserted that no existing entry covers --
    each a NEED for the Writers' Room, never a filing of its own.
    """
    chat = ctx.chat
    turn = ctx.turn
    cid = chat.id
    res = ctx.director_resolve or ctx.director_establish or {}
    diff = res.get("state_diff") or {}
    book_ids = chat_lorebook_ids(cid)
    # Narration is a rendering layer, not a source of objective truth.
    # `new_specifics` is an audit field for unsupported details the narrator
    # accidentally introduced; never launder those details into canon.
    narrator_specificity_flags = (ctx.narrator or {}).get("new_specifics") or []
    if narrator_specificity_flags:
        ctx.add_warning(
            "Narrator-originated specifics were excluded from canon: "
            + "; ".join(map(str, narrator_specificity_flags[:8]))
        )
    world_facts = [f for f in (diff.get("world_facts") or [])
                   if isinstance(f, (dict, str)) and f]
    introductions = [i for i in (diff.get("introductions") or [])
                     if isinstance(i, dict) and i.get("who") and i.get("learns")]
    needs = [n for n in (ctx.world_context().get("planning_needs") or [])
             if isinstance(n, dict)]
    seed = f"tick:{cid}:{turn.idx}"

    fact_needs = _setting_fact_needs(ctx, res, world_facts, book_ids)
    needs = needs + fact_needs

    if not (introductions or needs):
        return {
            "skipped": True,
            "mout": {"skipped": "nothing new to commit"},
            "ops": [],
            "book_ops": [],
            "book_ids": book_ids,
            "seed": seed,
            "introductions": [],
            "needs": [],
        }

    return {
        "skipped": False,
        "mout": {
            "facts": len(fact_needs),
            "introductions": len(introductions),
            "planning_needs": len(needs),
        },
        # No lore op is ever prepared here any more; the keys survive for
        # every reader that spelled them.
        "ops": [],
        "book_ops": [],
        "book_ids": book_ids,
        "seed": seed,
        "introductions": introductions,
        "needs": needs,
    }


def _setting_fact_needs(ctx, res, world_facts, book_ids):
    """The Director's `world_facts` as `setting_fact` planning needs -- one
    per fact no existing entry already covers, none for a fact the Director
    itself sourced from lore. The Director may say what happened; what is
    TRUE of the setting is the room's to file, with a gate."""
    if not world_facts:
        return []
    from world.planning_needs import planning_need
    chat = ctx.chat
    cid = chat.id
    frame_id = getattr(ctx.turn, "frame_id", None)
    turn_idx = getattr(ctx.turn, "idx", 0) or 0
    texts = []
    for world_fact in world_facts:
        if isinstance(world_fact, dict):
            text = str(world_fact.get("fact") or "")
            source_kind = (world_fact.get("source") or {}).get("kind")
        else:
            text = str(world_fact)
            source_kind = None
        text = " ".join(text.split())
        if not text or source_kind == "lore":
            continue
        texts.append((text, source_kind))
    if not texts:
        return []
    try:
        existing = search_lore(
            chat_lorebook_weights(cid),
            res.get("summary") or " ".join(t for t, _k in texts)[:400],
            k=10, chat_id=cid, frame_id=frame_id)
    except Exception as exc:  # a retrieval outage is not a reason to invent
        ctx.add_warning(f"setting facts not checked against lore: {exc}")
        existing = []
    needs = []
    for text, source_kind in texts:
        if _fact_is_covered(text, existing):
            continue
        try:
            needs.append(planning_need(
                "thing", "setting_fact",
                subject=text[:SETTING_FACT_SUBJECT_CHARS],
                surface={"fact": text, **({"source": source_kind} if source_kind else {})},
                turn_idx=turn_idx, frame_id=frame_id))
        except ValueError as exc:
            ctx.add_warning(f"setting fact not recorded: {exc}")
    return needs


def _attach_committed_surface(ctx, needs):
    """A room need whose stub the beat rendered carries that stub's surface:
    the name and the exits the committed diff gave it, so the plan that
    answers the need may not contradict what a body already saw.

    And a room need whose committed record carries `parent_entity` is
    DROPPED. Where a body walks is its own; where the world puts it is the
    Director's -- and a body put inside another body is a place the moment
    it happens, minted by the spatial hand, that no plan could have held in
    advance. The committed surface proves which kind of room it is, so the
    need is decided here, at the commit, on the record."""
    res = ctx.director_resolve or ctx.director_establish or {}
    rooms = (res.get("state_diff") or {}).get("rooms") or {}
    if not isinstance(rooms, dict):
        return needs
    by_slug = {normalize_room_id(str(rid)): (rid, room)
               for rid, room in rooms.items() if isinstance(room, dict)}
    out = []
    for need in needs:
        need = dict(need)
        if need.get("kind") == "room":
            hit = by_slug.get(normalize_room_id(str(need.get("subject") or "")))
            if hit and str((hit[1] or {}).get("parent_entity") or "").strip():
                continue
            if hit:
                rid, room = hit
                surface = dict(need.get("surface") or {})
                surface["room"] = str(rid)
                if room.get("name"):
                    surface["name"] = str(room["name"])
                exits = [str(e.get("to")) for e in (room.get("adjacent") or [])
                         if isinstance(e, dict) and e.get("to")]
                if exits:
                    surface["exits"] = exits
                need["surface"] = surface
        out.append(need)
    return out


def commit_mapping(ctx, nonce, *, prepared=None):
    chat = ctx.chat
    turn = ctx.turn
    cid = chat.id
    prepared = prepared or prepare_mapping_commit(ctx)
    mout = prepared["mout"]
    book_ids = prepared["book_ids"]
    seed = prepared["seed"]

    world = ctx.world_context()
    if prepared.get("skipped"):
        wset(cid, "lore_cache", _lore_for(ctx)[:12])
        if isinstance(world.get("relevant_books"), list):
            wset(cid, "active_books", world["relevant_books"])
        return {
            "mout": mout,
            "applied": {"created": 0, "updated": 0},
            "book_ids": book_ids,
            "seed": seed,
        }

    # No turn stage prepares lore ops any more (the room filing and the
    # fallback fact writer are retired); the routing below survives for the
    # authoring package that hands a prepared dict in (v2 § 9.4's
    # `apply_authoring_change`), with `book_ops` temp ids resolving to the
    # books it creates. Every op lands with its gate fields as given --
    # untagged is Director-only, by design.
    ops = prepared.get("ops") or []
    book_ops = prepared.get("book_ops") or []
    applied = {"created": 0, "updated": 0}
    lb = chat.lorebook_id
    if (ops or book_ops) and not lb:
        # One spelling of "the chat's canon book", shared with the other writer
        # that can mint it first (background_claims.write_canon).
        lb = ensure_chat_canon_book(cid)
    temp_book_map = _apply_mapping_book_ops(cid, lb, book_ops)
    if ops:
        valid_books = set(chat_lorebook_ids(cid)) | ({lb} if lb else set())
        with transaction():
            for o in ops:
                if not o.get("content"):
                    continue
                cat = o.get("category") if o.get("category") in LORE_CATEGORIES else "other"
                kloc = (json.dumps(o.get("knowledge_locations") or [])
                        if o.get("knowledge_locations") else None)
                raw_book_id = o.get("book_id")
                if isinstance(raw_book_id, str):
                    raw_book_id = temp_book_map.get(raw_book_id) or (
                        int(raw_book_id) if raw_book_id.isdigit() else None)
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
                            source_notes=o.get("source_notes"),
                            embedding=o.get("_embedding"),
                        )
                        applied["updated"] += 1
                        continue
                add_lore(
                    target_book_id, _keys_str(o.get("keys", "")), o["content"],
                    turn_added=turn.idx, category=cat, title=o.get("title"),
                    knowledge_tag=o.get("knowledge_tag"),
                    knowledge_range=o.get("knowledge_range"),
                    knowledge_locations=kloc,
                    source_notes=o.get("source_notes") or "",
                    embedding=o.get("_embedding"),
                )
                applied["created"] += 1
    if lb:
        # Canon written in play LOCKS after twenty beats: the room's filings
        # and a ratified claim's entry become the story's settled record.
        with transaction() as c:
            c.execute(
                "UPDATE lore_entries SET canon_locked=1 "
                "WHERE lorebook_id=? AND turn_added IS NOT NULL AND turn_added<=?",
                (lb, turn.idx - 20),
            )

    wset(cid, "lore_cache", _lore_for(ctx)[:12])
    if isinstance(world.get("relevant_books"), list):
        wset(cid, "active_books", world["relevant_books"])

    needs = prepared.get("needs") or []
    if needs:
        from world.planning_needs import record_planning_needs
        recorded = record_planning_needs(
            cid, _attach_committed_surface(ctx, needs), frame_id=turn.frame_id)
        if recorded:
            ctx.add_warning(
                "%d planning need(s) recorded: the beat reached for %s no "
                "plan holds" % (recorded, ", ".join(
                    "%s %r" % (n.get("kind"), n.get("subject"))
                    for n in needs[:4])))
    known = wget(cid, "known", {})
    introductions = prepared.get("introductions") or []
    # Nothing to resolve, so nothing is built. The Charter projection below is
    # O(bodies) and this runs on every beat; a thousand-body institution must
    # not be walked for a turn that introduced nobody.
    if not introductions:
        wset(cid, "known", known)
        return {"mout": mout, "applied": applied, "book_ids": book_ids,
                "seed": seed}
    # WIDE for resolution: an introduction naming an offscreen person is still
    # a sentence about a real person, and dropping it silently is the defect.
    # The EDGE it would write is gated separately, below.
    roster = _registered_name_roster(chat, ctx.cast)
    # A Charter body is a real, placed identity that `chat_chars` does not
    # contain, so a cast-built roster answers "is this somebody" with no for a
    # person standing in the room. `commit_memory` already reads this
    # projection for a name learned by hearing; this is the same ledger.
    charter_rooms, charter_aliases = {}, {}
    try:
        _charter = charter_recognition_projection(cid, turn.frame_id)
    except Exception as exc:
        ctx.add_warning(f"Charter recognition roster skipped: {exc}")
    else:
        for _name in _charter["names"]:
            if _name not in roster:
                roster.append(_name)
        charter_rooms = {name: room for name, room in _charter["rooms"].items()
                         if room}
        charter_aliases = _charter["aliases"]
    # One reading of "does this text name this person", shared with the
    # channel that learns a name by hearing it said. See _resolve_roster_name.
    address_index = _address_index(roster)
    name_to_id = {character_name_from_text(r["sheet"]): r["id"] for r in ctx.cast}
    from story.scene import persona_of as _persona_of
    present = {character_name_from_text(r["sheet"]) for r in ctx.cast}
    player = (persona_name(_persona_of(chat)) or "").strip()
    if player:
        present.add(player)
    scene_now = wget(cid, "scene", {}) or {}

    def _stands_in(name):
        """The room this body is in, or None when the engine cannot say."""
        if name in charter_rooms:
            return charter_rooms[name]
        return _room_of(scene_now, name)

    for vi in introductions:
        who = _resolve_roster_name(vi.get("who"), roster, address_index)
        learns = _resolve_roster_name(vi.get("learns"), roster, address_index)
        if not (who and learns):
            continue
        if who == learns:
            # Nobody is recognised against themselves. Reading address forms
            # makes this reachable: chat 98 turn 11 emitted `{"who": "Sabine
            # Oyelaran", "learns": "Sabine, Stellar Cartography"}` -- a person
            # and the department she had just named, resolving to one body.
            continue
        # TWO REQUIREMENTS, KEPT SEPARATE. The roster above answers "is this a
        # person the story knows about", which is what resolving a name needs.
        # An introduction needs more: somebody has to have been THERE to be
        # introduced. Now that the roster includes offscreen characters, a
        # single check would let a diff write an introduction between two
        # people who were both absent -- trading a missed edge for an invented
        # one, which is worse, because a wrong edge is indistinguishable from a
        # right one afterwards and nothing downstream can catch it.
        #
        # PRESENCE IS ANSWERED WHERE EACH KIND OF BODY RECORDS IT. A registered
        # member is on stage by membership; a Charter body is on stage by the
        # room its body stands in, which is the only presence answer that
        # population has. Both answer the same question -- was this person here
        # to be introduced.
        #
        # BOTH parties. `learns` had a frame gate and `who` had none, and that
        # gate SKIPS rather than blocks for anyone outside `ctx.cast` -- which
        # is exactly the set the wider roster has just admitted. Hanging the
        # requirement off an id lookup would open it for them instead of
        # closing it, so this is a positive test against who was on stage.
        if who not in present and who not in charter_rooms:
            continue
        if learns not in present and learns not in charter_rooms:
            continue
        # And in the same room. An introduction between two bodies the engine
        # can place in different rooms is an edge nobody witnessed; where it
        # can place neither, membership above is the whole of the answer.
        who_room, learns_room = _stands_in(who), _stands_in(learns)
        if who_room and learns_room and who_room != learns_room:
            continue
        learns_id = name_to_id.get(learns)
        if learns_id is not None and not is_recognized_in_frame(learns_id, turn.frame_id):
            continue
        known.setdefault(who, [])
        # Every formal variant of the learned body, as the hearing channel
        # writes them: a rank or a post is presentation that may change, and
        # recognition must survive the change without treating the display
        # string as identity.
        for learned in charter_aliases.get(learns, [learns]):
            if learned not in known[who]:
                known[who].append(learned)
    wset(cid, "known", known)
    return {"mout": mout, "applied": applied, "book_ids": book_ids, "seed": seed}

# ---- Fallback helpers ----

def _lore_for(ctx):
    return ctx.world_context().get("relevant_lore") or []


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
