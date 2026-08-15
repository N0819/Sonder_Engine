"""Subject identity: one id per being, read from the ledger that already owns it.

0c of ``docs/archive/PROPOSAL_2026-08-06.md`` (section 2A, reordered first by amendment
1), designed against ``docs/design/DESIGN_0c_subject_identity.md``.

WHAT ALREADY EXISTS, AND IS NOT TOUCHED. ``spatial.canonical_subject_map`` and
``spatial.normalize_scene_subjects`` fold a CHARACTER's two live spellings (a
cast display name and a scene entity id) onto one, at merge, gated on scene
liveness -- G3 in the design note, a brake with a measured eleven-test
regression history. That fold is body-shaped by construction: a faction, a
crowd and a registry room own none of the six subject-keyed ledgers, so the
liveness gate that keeps character identity honest is the same gate that makes
those kinds unreachable (design note section 4, the circularity).

THE ROUTE CHOSEN, of the note's three: C, in its narrowest form -- identity is
DECOUPLED from scene liveness, and this layer READS rather than MINTS. Each
kind resolves through the durable ledger that already owns beings of that
kind:

    character -> the cast row (``character_schema.cast_entity_id`` -- the id
                 ``cast_scene_context`` has been minting into payloads all
                 along), else the scene entity id
    room      -> the scene's own room key, else ``room_registry`` -- the sole
                 cross-frame ledger of room identity, a different namespace
                 the fold never reached
    faction   -> the lore entry (``entry_uid``); a faction has no entity id
                 and no cast row, and its lore entry is the only durable
                 record of it anywhere
    place     -> a room FIRST (a generated place IS a room -- answering
                 ``place`` beside a live ``room`` would put two spellings on
                 one being, the exact defect 0c exists to prevent), else the
                 lore entry, per amendment 8
    crowd     -> the scene entity id when the crowd is a scene entity; a
                 crowd owns nothing else

WHERE NO LEDGER OWNS THE BEING, NOTHING IS MINTED. Resolution fails with a
reason -- the measured 18 of 38 background presences that were never scene
entities fail here, and must: giving them an id that exists in no ledger is
minting a second spelling beside the live name-keyed one, which is the defect
class that produced the five-defect identity investigation. The reasons are
the measurement: whether a real identity registry is ever worth standing up
is decided by how often, and for what, this returns one -- against real
occasions, not against every row in a table.

Never guesses: every match is exact after casefold (rooms: after
``normalize_room_id``, the registry's own dedup convention), and an ambiguous
spelling -- two cast rows, two entities, two lore entries -- resolves to
nothing, with the ambiguity in the reason. Two beings folded into one is
strictly worse than two spellings of one.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from canon_provenance import Subject
from db import q, wget, wget_for_frame
from spatial import normalize_room_id


@dataclass
class Resolution:
    """One resolved subject, or the reason there is none.

    ``authority`` names the ledger that answered -- it is what makes a miss
    countable per ledger, and a hit auditable. ``reason`` is never empty on a
    miss: silence is how the abort path made a crash and a closed tab
    indistinguishable.
    """

    subject: Subject | None
    authority: str = ""
    reason: str = ""

    def __bool__(self) -> bool:
        return self.subject is not None


def _fold(text) -> str:
    return str(text or "").strip().casefold()


def _display_or_none(display, sid):
    """A display equal to the id is no display at all -- storing it would
    trip canon_provenance's id-is-not-the-display-name check for nothing."""
    text = str(display or "").strip()
    if not text or text.casefold() == _fold(sid):
        return None
    return text


# ---------------------------------------------------------------------------
# character
# ---------------------------------------------------------------------------

def _cast_matches(cid, spelling, frame_id=None):
    """Cast rows answering to `spelling` by name, alias, authored uid or the
    ``character:<id>`` fallback -- the id spellings included so an id already
    in hand round-trips through resolution unchanged."""
    from character_schema import cast_entity_id, character_name_from_text
    from scene import extant_cast

    target = _fold(spelling)
    hits = []
    for row in extant_cast(cid, frame_id):
        try:
            sheet = json.loads(row["sheet"] or "{}")
        except Exception:
            sheet = {}
        identity = (sheet or {}).get("identity") or {}
        eid = cast_entity_id(sheet, row["id"])
        labels = {_fold(character_name_from_text(row["sheet"])), _fold(eid)}
        labels.update(_fold(a) for a in (identity.get("aliases") or []))
        labels.discard("")
        if target in labels:
            hits.append((eid, character_name_from_text(row["sheet"])))
    return hits


def _entity_matches(scene, spelling):
    """Every scene entity answering to `spelling` by id, name or alias.

    Deliberately NOT ``spatial._entity_named``, which returns the first match:
    two Daleks sharing a name fold nothing under the scene fold's G1, and the
    same rule holds here -- ambiguity must surface, not be won by dict order
    (design note section 6 records that limit against ``same_subject``).
    """
    target = _fold(spelling)
    hits = []
    for eid, entity in ((scene or {}).get("entities") or {}).items():
        if not isinstance(entity, dict):
            continue
        labels = {_fold(eid), _fold(entity.get("name"))}
        labels.update(_fold(a) for a in (entity.get("aliases") or []))
        labels.discard("")
        if target in labels:
            hits.append((str(eid), str(entity.get("name") or "")))
    return hits


def _presence_reason(cid, spelling, frame_id=None):
    """The name-keyed dead end, said precisely when it is the dead end.

    ``background_presences`` is keyed by display name, deliberately and on
    write -- a convention to migrate, not an oversight to patch (proposal
    section 2A). Measured: 18 of 38 presences across 19 chats were never
    scene entities under any normalisation, so they have no id anywhere to
    resolve to, and inventing one here would be the mint this module refuses.
    """
    if frame_id is not None:
        presences = wget_for_frame(cid, "background_presences", frame_id, {}) or {}
    else:
        presences = wget(cid, "background_presences", {}) or {}
    target = _fold(spelling)
    for name in presences:
        if _fold(name) == target:
            return (
                f"background presence {str(name)!r} is name-keyed and is not a "
                "scene entity; it has no id in any ledger, and minting one here "
                "would be a second spelling beside the live name"
            )
    return ""


def _resolve_character(cid, scene, kind, spelling, frame_id=None):
    cast = _cast_matches(cid, spelling, frame_id)
    if len(cast) == 1:
        eid, display = cast[0]
        return Resolution(
            Subject(kind=kind, id=eid, display=_display_or_none(display, eid)),
            authority="cast",
        )
    if len(cast) > 1:
        return Resolution(
            None, reason=f"{len(cast)} cast rows answer to {str(spelling)!r}; "
            "resolving would fold two beings into one",
        )
    entities = _entity_matches(scene, spelling)
    if len(entities) == 1:
        eid, display = entities[0]
        return Resolution(
            Subject(kind=kind, id=eid, display=_display_or_none(display, eid)),
            authority="scene_entity",
        )
    if len(entities) > 1:
        return Resolution(
            None, reason=f"{len(entities)} scene entities answer to "
            f"{str(spelling)!r}; resolving would fold two beings into one",
        )
    presence = _presence_reason(cid, spelling, frame_id)
    if presence:
        return Resolution(None, reason=presence)
    return Resolution(
        None, reason=f"no cast row, scene entity or background presence "
        f"answers to {str(spelling)!r}",
    )


# ---------------------------------------------------------------------------
# room
# ---------------------------------------------------------------------------

def _scene_room_matches(scene, spelling):
    slug = normalize_room_id(str(spelling or ""))
    if not slug:
        return []
    hits = []
    for rid, rdef in ((scene or {}).get("rooms") or {}).items():
        labels = {normalize_room_id(str(rid))}
        if isinstance(rdef, dict):
            labels.add(normalize_room_id(str(rdef.get("name") or "")))
            labels.update(
                normalize_room_id(str(a or "")) for a in (rdef.get("aliases") or []))
        labels.discard("")
        if slug in labels:
            hits.append((str(rid), (rdef or {}).get("name") if isinstance(rdef, dict) else ""))
    return hits


def _registry_room_matches(cid, spelling, *, retired):
    """Registry rows answering to `spelling` under `normalize_room_id` -- the
    same convention the registry's own dedup index uses, so no new matching
    vocabulary is minted here."""
    slug = normalize_room_id(str(spelling or ""))
    if not slug:
        return []
    clause = "IS NOT NULL" if retired else "IS NULL"
    hits = []
    for row in q(
        "SELECT room_uid, name, aliases FROM room_registry "
        f"WHERE chat_id=? AND retired_turn_id {clause}",
        (cid,),
    ):
        try:
            aliases = json.loads(row["aliases"] or "[]")
        except Exception:
            aliases = []
        labels = {normalize_room_id(str(row["room_uid"]))}
        labels.add(normalize_room_id(str(row["name"] or "")))
        labels.update(normalize_room_id(str(a or "")) for a in aliases)
        labels.discard("")
        if slug in labels:
            hits.append((str(row["room_uid"]), str(row["name"] or "")))
    return hits


def _resolve_room(cid, scene, kind, spelling):
    live = _scene_room_matches(scene, spelling)
    if len(live) == 1:
        rid, display = live[0]
        return Resolution(
            Subject(kind=kind, id=rid, display=_display_or_none(display, rid)),
            authority="scene_room",
        )
    if len(live) > 1:
        return Resolution(
            None, reason=f"{len(live)} scene rooms answer to {str(spelling)!r}",
        )
    if cid is not None:
        rows = _registry_room_matches(cid, spelling, retired=False)
        if len(rows) == 1:
            rid, display = rows[0]
            return Resolution(
                Subject(kind=kind, id=rid, display=_display_or_none(display, rid)),
                authority="room_registry",
            )
        if len(rows) > 1:
            return Resolution(
                None, reason=f"{len(rows)} live registry rooms answer to "
                f"{str(spelling)!r}; per-book dedup keeps them distinct and so "
                "must this",
            )
        # Retired rows answer too, second: identity outlives destruction --
        # retire-not-delete exists so "the ship that sank here" stays
        # retrievable -- but a live room must always outrank a ruin, and dedup
        # (which excludes retired rows so a rebuilt deck is a NEW room) is a
        # different question from reference resolution, which this is.
        rows = _registry_room_matches(cid, spelling, retired=True)
        if len(rows) == 1:
            rid, display = rows[0]
            return Resolution(
                Subject(kind=kind, id=rid, display=_display_or_none(display, rid)),
                authority="room_registry_retired",
            )
        if len(rows) > 1:
            return Resolution(
                None, reason=f"{len(rows)} retired registry rooms answer to "
                f"{str(spelling)!r}",
            )
    return Resolution(
        None, reason=f"{str(spelling)!r} is not a scene room and has no "
        "room_registry row; 'a quiet office' is the shape this refuses",
    )


# ---------------------------------------------------------------------------
# lore-owned kinds: faction, place
# ---------------------------------------------------------------------------

def _lore_matches(cid, spelling, categories):
    """Lore entries in the chat's reachable books answering to `spelling` by
    title, alias, key term or entry_uid. Exact after casefold -- retrieval may
    be fuzzy, identity may not."""
    from memory import chat_lorebook_ids

    book_ids = chat_lorebook_ids(cid)
    if not book_ids:
        return []
    target = _fold(spelling)
    placeholders = ",".join("?" * len(book_ids))
    cats = ",".join("?" * len(categories))
    hits = []
    for row in q(
        "SELECT id, entry_uid, title, keys, aliases FROM lore_entries "
        f"WHERE lorebook_id IN ({placeholders}) AND category IN ({cats})",
        (*book_ids, *categories),
    ):
        try:
            aliases = json.loads(row["aliases"] or "[]")
        except Exception:
            aliases = []
        labels = {_fold(row["title"]), _fold(row["entry_uid"])}
        labels.update(_fold(a) for a in aliases)
        labels.update(_fold(k) for k in str(row["keys"] or "").split(","))
        labels.discard("")
        if target in labels:
            hits.append(row)
    return hits


def _resolve_from_lore(cid, kind, spelling, categories, absent_reason):
    if cid is None:
        return Resolution(
            None, reason=f"kind {kind!r} resolves through lore entries and no "
            "chat id was given",
        )
    rows = _lore_matches(cid, spelling, categories)
    if len(rows) > 1:
        return Resolution(
            None, reason=f"{len(rows)} lore entries answer to {str(spelling)!r}; "
            "resolving would fold two subjects into one",
        )
    if len(rows) == 1:
        row = rows[0]
        uid = str(row["entry_uid"] or "")
        if not uid:
            # add_lore has minted entry_uid since it existed; a NULL is an old
            # imported row. Said rather than papered over with the numeric id,
            # which does not survive export/import remapping.
            return Resolution(
                None, reason=f"lore entry {row['id']} matches {str(spelling)!r} "
                "but carries no entry_uid; an id that changes on import is not "
                "an identity",
            )
        return Resolution(
            Subject(kind=kind, id=uid, display=_display_or_none(row["title"], uid)),
            authority="lore_entry",
        )
    return Resolution(None, reason=absent_reason)


def _resolve_place(cid, scene, spelling):
    # A generated place IS a room. Amendment 8 gives an UNgenerated lorebook
    # place ``kind: place`` keyed on its lore entry precisely because it has
    # no room_uid yet -- so the moment a room exists, the room subject is the
    # one true spelling and the place answer must yield to it, or the same
    # location is addressable under two ids at once.
    as_room = _resolve_room(cid, scene, "room", spelling)
    if as_room:
        return as_room
    return _resolve_from_lore(
        cid, "place", spelling, ("location",),
        absent_reason=f"{str(spelling)!r} is not a room and no location lore "
        "entry answers to it",
    )


# ---------------------------------------------------------------------------
# crowd, and the open remainder
# ---------------------------------------------------------------------------

def _resolve_crowd(cid, scene, spelling, frame_id=None):
    entities = _entity_matches(scene, spelling)
    if len(entities) == 1:
        eid, display = entities[0]
        return Resolution(
            Subject(kind="crowd", id=eid, display=_display_or_none(display, eid)),
            authority="scene_entity",
        )
    if len(entities) > 1:
        return Resolution(
            None, reason=f"{len(entities)} scene entities answer to "
            f"{str(spelling)!r}",
        )
    presence = _presence_reason(cid, spelling, frame_id)
    if presence:
        return Resolution(None, reason=presence)
    return Resolution(
        None, reason=f"no scene entity answers to {str(spelling)!r}; a crowd "
        "that is not a scene entity is owned by no ledger",
    )


def resolve_subject(cid, scene, kind, spelling, frame_id=None) -> Resolution:
    """One spelling in, one id out -- or the reason there is none.

    ``kind`` is an OPEN vocabulary, matching ``canon_provenance``: an
    unrecognised kind is tried against scene entities (the most general
    ledger) rather than raised on, so a new subject kind never needs an edit
    here to be spellable. Ids round-trip: passing a subject's own id as the
    spelling resolves to that same subject, which is what lets a caller
    verify an id and canonicalise a display name through one door.
    """
    text = str(spelling or "").strip()
    if not text:
        return Resolution(None, reason="empty spelling")
    k = _fold(kind)
    if not k:
        return Resolution(None, reason="empty subject kind")
    if k == "character":
        return _resolve_character(cid, scene, k, text, frame_id)
    if k == "room":
        return _resolve_room(cid, scene, k, text)
    if k == "place":
        return _resolve_place(cid, scene, text)
    if k == "faction":
        return _resolve_from_lore(
            cid, k, text, ("faction",),
            absent_reason=f"no faction lore entry answers to {str(text)!r}; a "
            "faction with no lore entry is owned by no ledger",
        )
    if k == "crowd":
        return _resolve_crowd(cid, scene, text, frame_id)
    entities = _entity_matches(scene, text)
    if len(entities) == 1:
        eid, display = entities[0]
        return Resolution(
            Subject(kind=k, id=eid, display=_display_or_none(display, eid)),
            authority="scene_entity",
        )
    if len(entities) > 1:
        return Resolution(
            None, reason=f"{len(entities)} scene entities answer to {text!r}",
        )
    return Resolution(
        None, reason=f"no identity authority owns kind {k!r}; scene entities "
        "were tried and none answers to " + repr(text),
    )
