"""The gap generator: what changed about a subject while nobody was looking.

Item 1 of ``docs/PROPOSAL_2026-08-06.md`` section 1.2, steps 1 and 2. One
question, answered structurally: *what changed about X between turn N and
now*. The answer is a RECORD, never prose -- prose is what produced the one
``offscreen_log`` row ever written, which placed its actor in "a quiet
office", a room the scene graph does not contain, and which nothing
downstream could reason about.

Three properties, each from a defect already on the record:

  1. ``subject.id`` is an id, not a display name. Enforced at the earliest
     stage: every ask goes through ``subjects.resolve_subject``, so a caller
     holding a display name gets the id (with the display preserved) and a
     caller holding a spelling no ledger owns gets ``basis: "unavailable"``
     with the resolver's own reason.
  2. Room references are node ids, never prose -- tested against the SAME
     pattern ``canon_provenance`` validates with. A ledger entry carrying a
     prose room is dropped and the drop is noted, because repeating a stored
     defect is worse than admitting less.
  3. A gap that could not be produced says so, with a reason. Silence is how
     the abort path made a crash and a closed tab indistinguishable.

RESOLUTION IS DERIVED, NOT OBEYED. The subject's own tier picks the rung --
a caller that can pick the expensive tier is a caller that will -- and the
``resolution`` argument may only lower it, never raise it. ``low`` is
assembled from state the engine already has with NO model call; ``medium``
adds one bounded call over that deterministic skeleton, so the skeleton is
what the prose must stay true to rather than something it invents around.
A medium call that fails, or that names a room outside the world, falls to
the rung below after one retry: a deterministic "she was elsewhere" is worth
more than a plausible lie.

THE LOW RUNGS MAY DESCRIBE, NEVER COMMIT (section 1.0.1). ``deltas`` stays
empty at both rungs built here, and the medium prompt is shaped so a
consequence has no field to land in. Only the full-agent rung -- unbuilt,
Director-adjudicated -- may change the world.

WHAT THE SKELETON READS: fired mechanics rows are promoted into the
checkpointed, frame-scoped ``world_events`` spine and gaps consume that
objective record. Legacy fired ``scheduled_events`` rows remain a fallback for
stories predating the spine. The only other turn-stamped offscreen ledger is
``offscreen_log``; a source without an id remains id-less, because inventing
identity in a reader would be 0c's defect from the other side.
"""

from __future__ import annotations

import json

from canon_provenance import is_node_id
from db import active_frame_id, q, wget, wget_for_frame
from logging_utils import logger
from providers import chat_complete
from spatial import room_of
from subjects import resolve_subject

#: World-KV ledger: {subject_id: {turn, room, elapsed_seconds}} -- the one
#: new piece of state the bottom rung requires (section 1.2 step 2; nothing
#: recorded last-seen before this). Frame-scoped (registered in db.py):
#: who was co-present with the player is a fact about an era, like the scene
#: it is read from. KEYED BY SUBJECT ID from birth -- the first ledger in
#: the tree born in the right key space, so it never needs the migration the
#: name-keyed five are waiting for.
LAST_SEEN_KEY = "subject_last_seen"

_PRODUCER = "gaps.gap_for"


def _read_key(cid, key, default, frame_id=None):
    if frame_id is not None:
        return wget_for_frame(cid, key, frame_id, default)
    return wget(cid, key, default)


def _record(subject, resolution, since, until, *, basis, moves=None,
            events=None, reason=None, summary=None, inputs=None, seed=None):
    out = {
        "subject": subject,
        "resolution": resolution,
        "since_turn": since,
        "until_turn": until,
        "moves": moves or [],
        "events": events or [],
        # Empty at every rung built here, structurally: a rung that cannot
        # express a consequence cannot smuggle one (section 1.0.1).
        "deltas": {},
        "basis": basis,
        "producer": _PRODUCER,
        "inputs": inputs or {},
        "seed": seed or "",
    }
    if reason is not None:
        out["reason"] = reason
    if summary is not None:
        out["summary"] = summary
    return out


def _unavailable(subject, since, until, reason, seed=""):
    """Section 1.2 property 3: never nothing. The reason rides the record."""
    return _record(subject, "low", since, until, basis="unavailable",
                   reason=reason, seed=seed)


def _derived_resolution(cid, subject, frame_id=None):
    """The subject's own tier, from the one tier ledger the engine has.

    Cast members carry ``simulation.tier``; a major character acting in the
    background is the proposal's own line for medium. Every other kind has
    no tier ledger at all yet -- section 1.2 step 3 (distance x importance)
    is where that representation arrives -- so until it exists they are low,
    which asserts almost nothing and therefore cannot contradict anything.
    """
    if subject["kind"] != "character":
        return "low"
    from character_schema import cast_entity_id, character_tier
    from scene import extant_cast

    for row in extant_cast(cid, frame_id):
        try:
            sheet = json.loads(row["sheet"] or "{}")
        except Exception:
            continue
        if cast_entity_id(sheet, row["id"]) == subject["id"]:
            return "medium" if character_tier(sheet) == "major" else "low"
    return "low"


def _subject_room(scene, subject):
    """Where the subject is NOW, resolved through identity rather than
    spelling -- `positions` may key this being by display name (cast
    convention) or by entity id, and `room_of` tolerates case but not a
    different name for the same thing."""
    for spelling in (subject["id"], subject.get("display")):
        if not spelling:
            continue
        room = room_of(scene, str(spelling))
        if room:
            return room
    return None


def _skeleton(cid, scene, subject, since, until, frame_id=None):
    """The deterministic trail: positions, clock, scheduled events. No model
    call, and everything asserted is read from a ledger, so the worst it can
    be is thin -- never wrong in a way prose can be."""
    notes = []
    ledgers = ["subject_last_seen"]
    moves = []
    events = []

    last = (_read_key(cid, LAST_SEEN_KEY, {}, frame_id) or {}).get(subject["id"]) or {}

    # -- moves: the endpoint delta. No ledger records positions per turn, so
    # the honest claim is "was there at since, is here at until", one move,
    # stamped with the turn it is known BY rather than a turn it happened on.
    if subject["kind"] in ("room", "place"):
        pass  # a room does not move; asserting so would be noise
    else:
        ledgers.append("scene.positions")
        from_room = last.get("room")
        to_room = _subject_room(scene, subject)
        if from_room and not is_node_id(str(from_room)):
            # Property 2, enforced on read as well as write: a stored prose
            # room is the 'quiet office' defect, and repeating it is worse
            # than admitting less.
            notes.append(f"dropped non-id last-seen room {str(from_room)!r}")
            from_room = None
        if from_room and to_room and str(from_room) != str(to_room):
            moves.append({"turn": until, "from_room": str(from_room),
                          "to_room": str(to_room), "basis": "deterministic"})

    # -- objective world events, windowed by the simulation clock. The ledger
    # is clock-stamped, so the window needs the clock at
    # `since` -- which only the last-seen entry records. When the caller's
    # window does not start at the last sighting, the clock bound is unknown
    # and the ledger is skipped with a note rather than guessed at.
    since_seconds = None
    if int(last.get("turn", -1)) == since:
        try:
            since_seconds = float(last.get("elapsed_seconds"))
        except (TypeError, ValueError):
            since_seconds = None
    if since_seconds is None:
        notes.append(
            f"world events skipped: no clock recorded for turn {since}")
    else:
        ledgers.append("world_events")
        # THIS frame's clock, not whichever frame the calling thread happens
        # to have active: `simulation_clock` resolves through the contextvar,
        # so an explicit frame_id ask on the wrong thread windowed the ledger
        # by another era's seconds and the frame's own fired events vanished.
        now_seconds = float(
            (_read_key(cid, "simulation_clock", {}, frame_id) or {})
            .get("elapsed_seconds") or 0.0)
        fid = active_frame_id.get() if frame_id is None else frame_id

        def append_if_owned(row, *, turn=None):
            try:
                payload = json.loads(row["payload"] or "{}")
            except (TypeError, ValueError):
                payload = {}
            if not isinstance(payload, dict):
                payload = {}
            entry = None
            location = str(row["location_id"] or "")
            if subject["kind"] in ("room", "place"):
                if location == subject["id"]:
                    entry = {"turn": turn, "event_id": row["event_id"],
                             "summary": str(row["kind"])}
            else:
                # Attribution is structured or not at all: `entity_id` is
                # the one subject-bearing field any writer stamps. The
                # substring sweep this replaces matched payload prose, so
                # another room's event that merely NAMED the subject rode
                # into their gap with its room id -- a mention is somebody
                # else's event (offscreen._intention_owned_by's rule, on
                # the read side). A row with no structured owner is
                # nobody's content.
                owner = str(payload.get("entity_id") or "").strip().casefold()
                needles = {subject["id"].casefold()}
                if subject.get("display"):
                    needles.add(str(subject["display"]).casefold())
                if owner and owner in needles:
                    entry = {"turn": turn, "event_id": row["event_id"],
                             "summary": str(row["kind"])}
            if entry is not None:
                if is_node_id(location):
                    entry["room"] = location
                events.append(entry)

        promoted_sources = set()
        for row in q(
            "SELECT we.event_id,we.kind,we.location_id,we.payload,t.idx AS turn_idx "
            "FROM world_events we LEFT JOIN turns t ON t.id=we.turn_id "
            "WHERE we.chat_id=? AND we.frame_id IS ? AND we.occurred_at>? "
            "AND we.occurred_at<=? ORDER BY we.occurred_at",
            (cid, fid, since_seconds, now_seconds),
        ):
            try:
                payload = json.loads(row["payload"] or "{}")
            except (TypeError, ValueError):
                payload = {}
            if isinstance(payload, dict) and payload.get("source_event_id"):
                promoted_sources.add(str(payload["source_event_id"]))
            append_if_owned(row, turn=row["turn_idx"])

        # Legacy fallback: released stories may contain fired scheduled rows
        # from before world_events had a writer. Do not duplicate rows already
        # promoted into the spine.
        for row in q(
            "SELECT event_id,kind,location_id,payload FROM scheduled_events "
            "WHERE chat_id=? AND status='fired' AND due_at>? AND due_at<=? "
            "ORDER BY due_at", (cid, since_seconds, now_seconds),
        ):
            if str(row["event_id"]) in promoted_sources:
                continue
            try:
                payload = json.loads(row["payload"] or "{}")
            except (TypeError, ValueError):
                payload = {}
            if not isinstance(payload, dict) or payload.get("frame_id") != fid:
                continue
            append_if_owned(row)

    # -- offscreen ticks. Turn-stamped. Attribution: a seeded-rung tick's
    # structured `subject.id` wins; a row without one is matched by its
    # legacy `actor` field exactly (id or display spelling), never by prose.
    # CONTENT then needs provenance: the seeded rung stamps
    # `basis`/`disposition` on every tick it mints, so a row carrying
    # neither is the OLD model-driven rung's omniscient prose -- chat 9
    # holds rows like "unaware of the Kalvoss cruiser's arrival", a fact
    # ABOUT the subject's ignorance phrased with knowledge the subject
    # lacks -- and delivering it into the subject's own gap hands the mind
    # a fact that reached it through no channel. Dropped, and the drop is
    # noted (offscreen._intention_owned_by's ownership rule, on the read
    # side: prose that cannot prove its provenance is nobody's content).
    ledgers.append("offscreen_log")
    names = {subject["id"].casefold()}
    if subject.get("display"):
        names.add(str(subject["display"]).casefold())
    unproven = 0
    for batch in _read_key(cid, "offscreen_log", [], frame_id) or []:
        if not isinstance(batch, dict):
            continue
        try:
            turn = int(batch.get("turn"))
        except (TypeError, ValueError):
            continue
        if not (since < turn <= until):
            continue
        for tick in batch.get("events") or []:
            if not isinstance(tick, dict):
                continue
            sub = tick.get("subject")
            if isinstance(sub, dict) and str(sub.get("id") or "").strip():
                owned = (str(sub["id"]).strip().casefold()
                         == subject["id"].casefold())
            else:
                actor = str(tick.get("actor") or "").strip().casefold()
                owned = bool(actor) and actor in names
            if not owned:
                continue
            if not (tick.get("basis") and tick.get("disposition")):
                unproven += 1
                continue
            events.append({"turn": turn, "event_id": None,
                           "summary": str(tick.get("tick") or "")[:300]})
    if unproven:
        notes.append(
            f"dropped {unproven} offscreen tick(s) with no provenance "
            "(legacy model-written rows may not deliver prose)")

    inputs = {"ledgers": ledgers}
    if notes:
        inputs["notes"] = notes
    return moves, events, inputs


class _MediumFallback(Exception):
    pass


def _medium_overlay(cid, scene, record):
    """One bounded call over the skeleton. The model may narrate the trail;
    it may not extend the world: rooms must come from the provided list, and
    the output shape has nowhere to put an alliance, an object or a wound."""
    known_rooms = {str(r) for r in (scene.get("rooms") or {})}
    for row in q(
        "SELECT room_uid FROM room_registry "
        "WHERE chat_id=? AND retired_turn_id IS NULL", (cid,),
    ):
        known_rooms.add(str(row["room_uid"]))
    for mv in record["moves"]:
        known_rooms.update((mv["from_room"], mv["to_room"]))

    sys = (
        "You summarize what a character plausibly did during turns that "
        "happened off screen, from a deterministic trail of moves and events. "
        "Stay strictly inside the trail: you may color it, never extend it. "
        "Do NOT invent outcomes, alliances, acquisitions, injuries, or any "
        "change to the world -- describe activity, not consequence. Any room "
        "you mention MUST be named by id from rooms_available; mention no "
        "room otherwise. Output STRICT JSON "
        '{"summary": "<2-3 sentences>", "rooms": ["<ids used, possibly empty>"]}'
    )
    user = json.dumps({
        "subject": record["subject"], "since_turn": record["since_turn"],
        "until_turn": record["until_turn"], "moves": record["moves"],
        "events": record["events"],
        "rooms_available": sorted(known_rooms)[:40],
    }, ensure_ascii=False)

    last_error = "no attempt"
    for attempt in range(2):  # reject and regenerate ONCE (section 1.0.3)
        try:
            out = json.loads(chat_complete(
                "utility", sys, user, temperature=0.4, max_tokens=1000))
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {str(exc)[:200]}"
            continue
        if not isinstance(out, dict):
            last_error = "output was not an object"
            continue
        summary = str(out.get("summary") or "").strip()
        rooms = out.get("rooms") if isinstance(out.get("rooms"), list) else []
        bad = [r for r in rooms if str(r) not in known_rooms]
        if not summary:
            last_error = "empty summary"
            continue
        if bad:
            # The location gate, on the write path of this record: a room
            # the world does not contain is refused, not stored.
            last_error = f"named rooms outside the world: {bad[:3]!r}"
            continue
        record["summary"] = summary
        record["basis"] = "model"
        record["inputs"]["rooms_cited"] = [str(r) for r in rooms]
        return record
    raise _MediumFallback(last_error)


def gap_for(cid, subject_kind, subject_id, since_turn, until_turn,
            resolution=None, scene=None, frame_id=None):
    """What changed about one subject over (since_turn, until_turn].

    Returns the section 1.2 record, always -- an ask that cannot be answered
    returns ``basis: "unavailable"`` with a reason, never raises and never
    returns nothing. ``resolution`` may only LOWER the derived rung; the
    proposal's exact words are that a caller able to pick the expensive tier
    is a caller that will.
    """
    if scene is None:
        scene = _read_key(cid, "scene", {}, frame_id) or {}

    kind = str(subject_kind or "").strip().casefold()
    asked = {"kind": kind, "id": str(subject_id or "")}

    res = resolve_subject(cid, scene, kind, subject_id, frame_id)
    if not res:
        return _unavailable(asked, since_turn, until_turn, res.reason)
    subject = res.subject.as_dict()

    try:
        since = int(since_turn if since_turn is not None else 0)
        until = int(until_turn)
    except (TypeError, ValueError):
        return _unavailable(
            subject, since_turn, until_turn,
            f"window ({since_turn!r}, {until_turn!r}] is not made of turns")
    seed = f"gap:{cid}:{subject['kind']}:{subject['id']}:{since}:{until}"
    if until <= since:
        return _unavailable(
            subject, since, until,
            f"empty window: until_turn {until} is not after since_turn {since}",
            seed=seed)

    derived = _derived_resolution(cid, subject, frame_id)
    effective = "low" if (resolution == "low" or derived == "low") else "medium"

    moves, events, inputs = _skeleton(cid, scene, subject, since, until, frame_id)
    record = _record(subject, effective, since, until, basis="deterministic",
                     moves=moves, events=events, inputs=inputs, seed=seed)

    if effective == "medium":
        try:
            record = _medium_overlay(cid, scene, record)
        except _MediumFallback as fell:
            # The rung below, and the record says so: a fallen-back medium is
            # a LOW record with its history attached, never a medium-shaped
            # record whose model half silently did not run.
            record["resolution"] = "low"
            record["inputs"]["fell_back_from"] = f"medium: {fell}"
            logger.info("gap medium fell back: chat=%s subject=%s: %s",
                        cid, subject["id"], fell)
    return record


# ---------------------------------------------------------------------------
# Step 2: the reader, and the one new piece of state it needs.
# ---------------------------------------------------------------------------

def last_seen_update(scene, cast_rows, player_name, turn_idx, elapsed_seconds):
    """Who the player is with this beat, keyed by subject id. Pure.

    Returns the ``subject_last_seen`` entries to merge: every subject in the
    player's room, resolved to the id-shaped spelling it already carries --
    ``cast_entity_id`` for cast (the id every payload uses), the entity id
    for scene entities. A positions key no id owns -- an unregistered
    presence, name-keyed by convention -- is SKIPPED, not minted for: this
    ledger is born in id space and stays there.
    """
    from character_schema import cast_entity_id, character_name_from_text

    positions = (scene or {}).get("positions")
    if not isinstance(positions, dict) or not player_name:
        return {}
    player_room = room_of(scene, player_name)
    if not player_room:
        return {}

    to_id = {}

    def claim(label, sid):
        key = str(label or "").strip().casefold()
        if not key:
            return
        # Two beings answering to one spelling: neither may have it. Folding
        # a sighting onto the wrong being is worse than not recording it.
        if key in to_id and to_id[key] != sid:
            to_id[key] = None
        else:
            to_id.setdefault(key, sid)

    for row in cast_rows or []:
        try:
            sheet = json.loads(row["sheet"] or "{}")
        except Exception:
            sheet = {}
        sid = cast_entity_id(sheet, row["id"])
        claim(character_name_from_text(row["sheet"]), sid)
        claim(sid, sid)
        for alias in ((sheet.get("identity") or {}).get("aliases") or []):
            claim(alias, sid)
    for eid, ent in ((scene or {}).get("entities") or {}).items():
        if not isinstance(ent, dict):
            continue
        claim(eid, str(eid))
        claim(ent.get("name"), str(eid))
        for alias in ent.get("aliases") or []:
            claim(alias, str(eid))

    player_key = str(player_name).strip().casefold()
    stamp = {"turn": int(turn_idx), "room": str(player_room),
             "elapsed_seconds": float(elapsed_seconds or 0.0)}
    # The room itself is seen too. A room subject has no position row, so
    # without this stamp its gap could never anchor the clock and the
    # clock-windowed ledgers (scheduled_events fires on seconds, not turns)
    # would be skipped for exactly the subject kind they describe best --
    # "the market closed" is a room's gap. Section 6.1's interim-on-return
    # needs the same anchor.
    out = {str(player_room): dict(stamp)}
    for key, room in positions.items():
        if str(room or "") != str(player_room):
            continue
        folded = str(key or "").strip().casefold()
        if folded == player_key:
            continue  # the player is not a subject of their own absence
        sid = to_id.get(folded)
        if sid:
            out[sid] = dict(stamp)
    return out


def interim_for(cid, scene, subject_kind, subject_id, current_turn,
                frame_id=None):
    """The whole bottom rung: the lazy gap, produced at the moment of contact.

    ``offscreen_log`` has been written since it existed and read by nothing
    -- not at re-contact, not by the Director, not in the UI. This is the
    reader. Called when a subject is about to act after an absence, it
    returns the gap since they were last seen with the player, or None when
    there is nothing worth a payload's tokens: never seen (the ledger starts
    recording from its first commit forward, and a since-turn nobody
    recorded would dump the whole story on first contact), seen this beat or
    the last (no gap to fill), or a gap that is empty or unavailable (an
    injected "nothing happened" is noise wearing a key).

    Asks for ``low`` explicitly -- this runs ON the turn path, and section
    1.0.2 puts model-priced rungs out of band; low is the rung that is free,
    and it is the one section 1.0.1a says to ship first and completely.
    """
    ledger = _read_key(cid, LAST_SEEN_KEY, {}, frame_id) or {}
    rec = ledger.get(str(subject_id)) or {}
    try:
        last = int(rec.get("turn"))
    except (TypeError, ValueError):
        return None
    if last >= int(current_turn) - 1:
        return None
    gap = gap_for(cid, subject_kind, subject_id, last, current_turn,
                  resolution="low", scene=scene, frame_id=frame_id)
    if gap.get("basis") == "unavailable":
        return None
    if not gap.get("moves") and not gap.get("events"):
        return None
    return gap
