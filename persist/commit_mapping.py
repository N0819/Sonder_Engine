"""Lore/book filing commit: what a beat established, written as structured
canon from the Director's committed diff -- no model in the loop.

Extracted verbatim from commit.py in the 2026-08 split, which re-exports
every name here (see docs/experiments/AUDIT_COMMIT.md). Rewritten 2026-09-04
with the mapping model's retirement: `prepare_mapping_commit` used to hand a
`mapping_commit` model the beat's staged lore, world facts and introductions
and take back its verdict (`validated`, `lore_ops`, `book_ops`,
`validated_introductions`, a shadow profile, standing intentions and
volunteered off-screen ticks). Every one of those was either a model
re-describing what the Director had already resolved (v2 § 9.4: "immediate
commit must not require an author agent to redescribe reality as prose") or
an unadjudicated authoring channel wearing a payload field. What survives is
the deterministic writer:

  * ROOM FILINGS -- every room the committed diff described gets a `layout`
    lore entry keyed to it, through `canon_provenance.promote` with the
    ruling stage as adjudicator, so the description perception serves as
    room notes is canon with a disposition rather than a model's
    confirmation (UNBUILT § 4.3 Gap 5's "mapping path is not routed through
    it", closed here).
  * WORLD FACTS -- the Director's typed `world_facts` not already covered
    by an existing entry, filed as before through the fallback op writer.
  * INTRODUCTIONS -- the Director's typed `introductions`, applied under
    the same presence and same-room gates the model's verdicts were
    (UNBUILT § 3.5 P7's "validated by model judgment", closed here).
  * PLANNING NEEDS -- what the world-context compiler found the beat
    reaching for that no plan holds, recorded on the frame's ledger with
    the surface the beat committed attached (`world/planning_needs.py`).
"""

import json
from core.db import q, qi, transaction, wget, wset
from mind.memory import (search_lore, add_lore, update_lore, LORE_CATEGORIES,
                    LOREBOOK_TYPES, chat_lorebook_ids, chat_lorebook_weights,
                    ensure_chat_canon_book)
from llm.providers import embed_texts
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

#: The disposition a filed room description is promoted to. It is the
#: Director's own spatial authority made durable: the room exists because the
#: beat put a body in it, and it reads as the ruling stage described it.
FILED_ROOM_DISPOSITION = "spatial_generation"

#: How much of a room's description one lore entry carries. The scene's own
#: `notes` field is capped at 500 by the scene commit; the entry keeps the
#: whole description the diff carried, up to this.
FILED_ROOM_CHARS = 2400


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


def _room_description(room):
    if not isinstance(room, dict):
        return ""
    text = room.get("desc") or room.get("description") or room.get("notes") or ""
    return " ".join(str(text).split())


def _existing_layout_entry(cid, book_ids, room_id, room_name):
    """The `layout` entry already filed for this room, if any: keyed to the
    room by its knowledge location, or by its keys when filed before the
    location was carried. Locked entries are found and left alone."""
    if not book_ids:
        return None
    marks = ", ".join("?" for _ in book_ids)
    rows = q(
        "SELECT id, lorebook_id, keys, knowledge_locations, canon_locked "
        "FROM lore_entries WHERE lorebook_id IN (%s) AND category='layout' "
        "ORDER BY id" % marks, tuple(book_ids))
    folded = {normalize_room_id(str(room_id)),
              normalize_room_id(str(room_name or ""))} - {""}
    for row in rows:
        try:
            locations = json.loads(row["knowledge_locations"] or "[]")
        except (TypeError, ValueError):
            locations = []
        if any(normalize_room_id(str(loc)) in folded for loc in locations
               if isinstance(loc, str)):
            return row
        keys = [normalize_room_id(k.strip())
                for k in str(row["keys"] or "").split(",") if k.strip()]
        if keys and keys[0] in folded:
            return row
    return None


def room_filings(ctx, diff, prev_scene, *, adjudicator):
    """The rooms this beat described, as promoted provenance records.

    One record per room in the committed diff whose description is new or
    changed against the scene the beat began in. Each is built as a
    PROVISIONAL record (subject kind `room`, id-shaped, the ruling stage's
    turn as base) and promoted through `canon_provenance.promote` to
    `spatial_generation` on the ruling stage's authority -- the seam UNBUILT
    § 4.3 named -- before anything is written. A room the diff re-asserts
    unchanged files nothing; a room with no description files nothing.
    """
    from mind.canon_provenance import PROVISIONAL, promote

    rooms = diff.get("rooms") if isinstance(diff.get("rooms"), dict) else {}
    prev_rooms = (prev_scene or {}).get("rooms") or {}
    out = []
    for rid, room in rooms.items():
        desc = _room_description(room)
        if not desc:
            continue
        if _room_description(prev_rooms.get(rid)) == desc:
            continue
        subject_id = normalize_room_id(str(rid))
        if not subject_id:
            continue
        name = str((room or {}).get("name") or "").strip() or str(rid)
        record = {
            "disposition": PROVISIONAL,
            "subject": {"kind": "room", "id": subject_id,
                        **({"display": name} if name != subject_id else {})},
            "base_turn": int(getattr(ctx.turn, "idx", 0) or 0),
            "basis": "deterministic",
            "room_key": str(rid),
            "content": desc[:FILED_ROOM_CHARS],
        }
        try:
            out.append(promote(record, FILED_ROOM_DISPOSITION,
                               adjudicator=adjudicator))
        except ValueError as exc:
            ctx.add_warning(f"room {rid!r} not filed: {exc}")
    return out


def _filing_ops(cid, book_ids, filings):
    """Lore ops for promoted room records: an update where the room already
    has a layout entry, a creation otherwise. Locked entries are skipped
    with the room's description left to the scene alone."""
    ops = []
    for record in filings:
        rid = record["room_key"]
        name = (record.get("subject") or {}).get("display") or rid
        existing = _existing_layout_entry(cid, book_ids, rid, name)
        provenance = "%s by %s (room %s)" % (
            record["disposition"], record["adjudicator"], rid)
        op = {
            "op": "update" if existing else "create",
            "keys": name if normalize_room_id(name) == normalize_room_id(rid)
                    else "%s, %s" % (name, rid),
            "content": record["content"],
            "category": "layout",
            "title": name,
            "knowledge_locations": [rid],
            "provenance": provenance,
            "book_id": existing["lorebook_id"] if existing else None,
        }
        if existing:
            if existing["canon_locked"]:
                continue
            op["id"] = existing["id"]
        ops.append(op)
    return ops


def prepare_mapping_commit(ctx):
    """Resolve and embed the beat's lore filings without mutating durable state.

    The embedding round-trip is the slow part; preparing it before the outer
    turn transaction keeps network latency off SQLite's write lock and lets
    commit_all apply every durable domain atomically. No model is consulted:
    every op here is derived from the Director's committed diff and the
    world-context compiler's step.
    """
    chat = ctx.chat
    turn = ctx.turn
    cid = chat.id
    res = ctx.director_resolve or ctx.director_establish or {}
    adjudicator = "director_resolve" if ctx.director_resolve else "director_establish"
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
    # The scene the beat began in: prepare runs before the write lock, so
    # the stored scene is still the pre-turn one.
    prev_scene = wget(cid, "scene", {}) or {}
    filings = room_filings(ctx, diff, prev_scene, adjudicator=adjudicator)
    needs = [n for n in (ctx.world_context().get("planning_needs") or [])
             if isinstance(n, dict)]
    seed = f"tick:{cid}:{turn.idx}"

    if not (filings or world_facts or introductions or needs):
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

    # The canon book is always a valid filing target (commit falls back to
    # it), so it is searched for an existing entry even when the chat's
    # attached-book graph does not list it yet.
    search_books = list(book_ids)
    if chat.lorebook_id and chat.lorebook_id not in search_books:
        search_books.append(chat.lorebook_id)
    ops = _filing_ops(cid, search_books, filings)
    if world_facts:
        lore_ctx = search_lore(
            chat_lorebook_weights(cid),
            res.get("summary") or " ".join(
                str(f.get("fact") if isinstance(f, dict) else f)
                for f in world_facts)[:400],
            k=10,
        )
        ops += _generate_fallback_ops([], [], world_facts, existing_lore=lore_ctx)
    for o in ops:
        if "keys" in o:
            o["keys"] = _keys_str(o["keys"])
        _file_engine_provenance(o)
    # An entry whose whole text was bookkeeping has nothing left to say about
    # the world.
    ops = [o for o in ops if o.get("content")]

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
        "mout": {
            "rooms_filed": [r["room_key"] for r in filings],
            "facts": len(world_facts),
            "introductions": len(introductions),
            "planning_needs": len(needs),
        },
        "ops": ops,
        "book_ops": [],
        "book_ids": book_ids,
        "seed": seed,
        "introductions": introductions,
        "needs": needs,
    }


def _attach_committed_surface(ctx, needs):
    """A room need whose stub the beat rendered carries that stub's surface:
    the name and the exits the committed diff gave it, so the plan that
    answers the need may not contradict what a body already saw."""
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

    ops = prepared["ops"]
    book_ops = prepared.get("book_ops") or []
    applied = {"created": 0, "updated": 0}
    lb = chat.lorebook_id
    if (ops or book_ops) and not lb:
        # One spelling of "the chat's canon book", shared with the other writer
        # that can mint it first (background_claims.write_canon).
        lb = ensure_chat_canon_book(cid)

    temp_book_map = _apply_mapping_book_ops(cid, lb, book_ops)
    # The canon book is a valid target whatever the attached-book graph
    # says: every op that resolves nowhere else lands in it, so an entry
    # already filed there must be updatable in place.
    valid_books = set(chat_lorebook_ids(cid)) | ({lb} if lb else set())
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
                        source_notes=o.get("source_notes"),
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
                source_notes=o.get("source_notes") or "",
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
            # The staged entry's own declaration that it was generated without
            # canon behind it. Carried as a FIELD, never as a sentence in
            # `content` -- `_file_engine_provenance` files it on `source_notes`.
            "provenance": entry.get("provenance"),
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
