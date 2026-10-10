"""Physical information carriers shared by full characters and Charter.

Truth in ``world_events`` is not knowledge. This module creates the first
legitimate bridge: when a mechanically fired event has a non-empty public
``witnessed`` surface, only physical holders at that location acquire it.
Registered characters use frame-specific character state; unpromoted Charter
people use that body's own sparse mind through ``charter_runtime``'s projection.
The report then travels because its holder or its explicit carrier travels.

No timer grants knowledge, no prose is generated, and no other mind reads the
envelope. A listener learns later through the ordinary speech -> perception ->
memory path.

TELLING IS THE SECOND LAYER, and it is an explicit COPY rather than knowledge
by proximity. Standing beside someone who knows a thing teaches you nothing;
being told does. `apply_tellings` makes the Director name speaker, listener and
report, then refuses the op unless that speaker actually holds that report and
actually spoke this beat -- the same grounding rule that stops the Director
inventing an absent character's plan.

MOVEMENT AND RETELLING ARE DIFFERENT COUNTERS, kept apart deliberately. A
sealed letter carried a thousand miles arrives verbatim; a story told twice
across one room arrives vague. `hops` counts how far the holder walked and
costs a claim nothing. `retellings` counts how many mouths it has passed
through, and is the only thing that takes its specifics away.

A TOLD ROW STORES WHAT ITS HOLDER HEARD, never the original. Keeping the exact
witnessed surface beside a listener who only caught a rumor would put the truth
one careless reader away from a mind that never earned it, and this engine's
one defining constraint is that no mind uses information it did not legitimately
acquire. Degradation is stepwise-safe -- retelling a retelling lands exactly
where telling it twice would -- so nothing is lost by storing the fainter text.
"""

from __future__ import annotations

import copy
import json
import re

from world import crowds as crowds_model
from world import degradation
from story.character_schema import character_identity
from core.db import q
from core.logging_utils import logger
from story.scene import extant_cast, set_char_state
from world.spatial import room_of


STATE_KEY = "carried_reports"
REPORT_CAP = 16
ROUTE_CAP = 12
PAYLOAD_CAP = 4

#: How many carrier ledgers have been written, ever, in this process.
#:
#: NOT a cache and not state: it holds no answer, only a number that can
#: INVALIDATE one, so a module global is safe here where a memo would not be.
#: A stale read of it can only cost a recomputation; it can never hand one
#: turn's carriers to another turn or one chat's to another chat, because the
#: memo it guards lives on the turn's `PipelineContext` and is additionally
#: keyed by the chat, the frame and the scene object it was built from.
#: `save_state` bumps it, which is the one place all three storage homes meet.
_LEDGER_WRITES = 0

#: The ctx side channel the turn's carrier index lives in.
_CARRIER_MEMO = "_carrier_index_memo"

#: Where the PLAYER's carrier state lives.
#:
#: A cast member keeps held reports in `chat_chars.cstate`. A persona has no
#: such row, so the player had nowhere to hold one -- and `_cast_index`, which
#: reads cast rows, could not name the player at all. Every carrier verb
#: refused them by construction: "courier sender 'Corin' is not a registered
#: character", "artifact poster 'Corin' is not a registered character". In a
#: single-player engine the likeliest sender of news was the one participant
#: who structurally could not send it.
#:
#: A world key rather than a table, because there is exactly one persona per
#: chat. It holds the same shape a cast row's state does, so every reader
#: below is indifferent to which of the two it was handed.
#:
#: FRAME-SCOPED, and read/written through an EXPLICIT frame (see
#: `persona_entry` and `save_state`). The cast half is per-era because
#: `chat_chars`/`chat_char_frames` state is; this half was not, so one row
#: answered for every era of a story at once and what the player witnessed in
#: one survived a rewind or a branch into another. Frame scoping alone is not
#: the whole repair: a bare `wget` redirects on the AMBIENT `active_frame_id`,
#: which is the right era only by accident outside a pipeline run -- the same
#: distinction `_crowd_index` records below.
PERSONA_STATE_KEY = "persona_carrier_state"

#: How many public surfaces still standing in a room a newcomer may take in on
#: arrival. Bounded so this is walking into a room and seeing what happened,
#: not archaeology: a body reads the barred gate in front of it, and does not
#: inherit every event that room has ever hosted.
#:
#: PER ROOM, and only per room. A63 (review 2026-09-07): the window was read
#: with ONE chat-wide query ordered by time, so the newest twelve located
#: events anywhere decided what every room offered -- twelve events in the
#: busy half of a story pushed a quiet room's still-standing gate out of the
#: window forever, and nobody walking in would ever see it again.
ARRIVAL_SURFACES = 3

#: How many rows the per-room query reads to find that many SURFACES. A
#: located event is a surface only if its payload carries `witnessed`, which
#: SQL cannot see, so the scan is widened and the filter happens in Python.
#: Named rather than spelled `* 4` at two call sites: it drops nothing a
#: reader would want -- it only decides how deep to look before giving up on
#: a room whose recent events were all private.
SURFACE_SCAN_FACTOR = 4

#: How many listeners one speaker may reach in a single beat. Bounded route
#: fan-out, and the deterministic half of the "town of criers" answer: a story
#: told to a room does not arrive in every mind in it at once, because a beat
#: is a moment and a moment holds one telling to a few people.
TELL_FANOUT_CAP = 3


def _character_room(scene, sheet):
    identity = character_identity(sheet or {})
    keys = [identity["name"], identity["uid"], *identity["aliases"]]
    for key in keys:
        if key:
            room = room_of(scene, str(key))
            if room:
                return str(room)
    return ""


def reports_for_state(state, cap=PAYLOAD_CAP):
    """Capped private projection; exact witnessed surfaces, newest first."""
    state = state if isinstance(state, dict) else {}
    rows = [r for r in state.get(STATE_KEY) or []
            if isinstance(r, dict) and r.get("world_event_id") and r.get("claim")]
    try:
        cap = max(0, int(cap))
    except (TypeError, ValueError):
        cap = PAYLOAD_CAP
    return [
        {k: row[k] for k in (
            "world_event_id", "source_event_id", "claim", "kind",
            "occurred_at", "acquired_turn", "current_location", "hops",
            # How many mouths this has been through, and whose. A mind that
            # heard a story second-hand should know it heard a story, and from
            # whom -- that is what makes a wrong report read as somebody being
            # wrong rather than as the engine being wrong.
            "retellings", "told_by",
            "provenance") if k in row}
        for row in rows[-cap:]
    ]


def standing_surfaces_reader(cid, frame_id, skip_event_ids=()):
    """A reader for the public surfaces still standing in ONE room.

    Returns `f(room) -> [(row, payload, witnessed), ...]`, newest first, at
    most `ARRIVAL_SURFACES` of them, memoised per room for the life of the
    call that built it -- a turn-local memo, never a module global.

    THE ONE HELPER (A63). Three sites asked this question -- a body walking
    in, a crowd standing there, a caravan pulling up -- and all three asked
    it with a chat-wide `ORDER BY occurred_at DESC LIMIT` and then filtered
    by room in Python. That is a window over the STORY, not over the room:
    twelve located events anywhere newer than the barred gate, and the room
    holding the gate offers nothing. "Still standing HERE" has to be asked
    here, and the `(chat_id, frame_id, location_id, occurred_at)` index is
    what makes asking it per room cheap.

    `skip_event_ids` drops surfaces the caller is already handling as this
    beat's own new events, so a body does not acquire one twice.
    """
    skip = {str(e) for e in skip_event_ids or ()}
    cache = {}

    def surfaces(room):
        room = str(room or "")
        if not room:
            return []
        if room in cache:
            return cache[room]
        found = []
        for row in q(
                "SELECT * FROM world_events WHERE chat_id=? AND frame_id IS ? "
                "AND location_id=? ORDER BY occurred_at DESC LIMIT ?",
                (cid, frame_id, room,
                 ARRIVAL_SURFACES * SURFACE_SCAN_FACTOR)) or []:
            if str(row["event_id"]) in skip:
                continue
            try:
                payload = json.loads(row["payload"] or "{}")
            except (TypeError, ValueError):
                payload = {}
            witnessed = " ".join(
                str((payload or {}).get("witnessed") or "").split())
            if not witnessed:
                continue
            found.append((dict(row), payload, witnessed[:320]))
            if len(found) >= ARRIVAL_SURFACES:
                break
        cache[room] = found
        return found

    return surfaces


def advance_carriers(ctx, scene, world_event_result):
    """Acquire public event surfaces and update each holder's physical trail.

    Runs inside ``commit_all`` after the normal character-state/memory domain,
    so it merges onto that domain's final state instead of being overwritten by
    a prepared state update. All writes share the turn transaction.
    """
    cid = ctx.chat.id
    event_ids = [str(e.get("event_id")) for e in
                 (world_event_result or {}).get("events") or []
                 if isinstance(e, dict) and e.get("event_id")]
    event_rows = []
    for event_id in event_ids:
        row = q(
            "SELECT * FROM world_events WHERE chat_id=? AND event_id=? "
            "AND frame_id IS ?", (cid, event_id, ctx.turn.frame_id), one=True)
        if not row:
            continue
        try:
            payload = json.loads(row["payload"] or "{}")
        except (TypeError, ValueError):
            payload = {}
        witnessed = " ".join(str((payload or {}).get("witnessed") or "").split())
        if witnessed and row["location_id"]:
            event_rows.append((dict(row), payload, witnessed[:320]))

    # Surfaces that landed HERE EARLIER and are still standing. Without these
    # the witness path could only ever fire for a body already in the room on
    # the exact beat an event fired -- and consequences fire off-screen on a
    # clock, in rooms chosen because nobody is in them. Measured on a 20-beat
    # drive: one public surface emitted, zero acquisitions, and Mora walked
    # into that room the next turn and looked directly at the barred gate
    # while learning nothing, forever.
    #
    # The design already said the answer: consequences "are met as state when
    # someone next stands where they landed". This is that sentence.
    standing = standing_surfaces_reader(
        cid, ctx.turn.frame_id,
        skip_event_ids=[str(r["event_id"]) for r, _, _ in event_rows])

    public_surfaces = len(event_rows)
    carrier_opportunities = acquired = moved = 0
    # Every body that can hold a report, the player among them -- see
    # `_carriers` for why the list is extant cast plus persona rather than the
    # active cast this loop started out reading.
    for entry in _carriers(cid, ctx.turn.frame_id, scene,
                           chat=getattr(ctx, "chat", None), ctx=ctx):
        current_room = entry["room"]
        state = entry["state"]
        reports = [dict(r) for r in state.get(STATE_KEY) or []
                   if isinstance(r, dict) and r.get("world_event_id")]
        changed = False

        # The envelope moves only because its physical holder moved. Endpoint
        # movement is enough for provenance; no code invents intermediate
        # route rooms that the scene did not establish.
        for report in reports:
            previous = str(report.get("current_location") or "")
            if current_room and previous and current_room != previous:
                route = [str(x) for x in report.get("route") or [] if x]
                if not route or route[-1] != current_room:
                    route.append(current_room)
                report["route"] = route[-ROUTE_CAP:]
                report["current_location"] = current_room
                report["hops"] = max(0, int(report.get("hops") or 0)) + 1
                report["last_moved_turn"] = int(ctx.turn.idx)
                moved += 1
                changed = True

        known = {str(r.get("world_event_id")): r for r in reports}
        here = standing(current_room)
        for row, payload, witnessed in event_rows + here:
            if str(row["location_id"]) != current_room:
                continue
            carrier_opportunities += 1
            event_id = str(row["event_id"])
            existing = known.get(event_id)
            firsthand = {
                "world_event_id": str(row["event_id"]),
                "source_event_id": str(payload.get("source_event_id") or ""),
                "claim": witnessed,
                "kind": str(row["kind"]),
                "occurred_at": float(row["occurred_at"]),
                "acquired_turn": int(ctx.turn.idx),
                "acquired_location": current_room,
                "current_location": current_room,
                "route": [current_room],
                "hops": 0,
                # An eyewitness has been told nothing. Degrading at the source
                # would make the person who was standing there wrong about
                # what they saw.
                "retellings": 0,
                "told_by": "",
                "provenance": "witnessed_surface",
            }
            if existing is not None:
                if str(existing.get("provenance") or "") \
                        == "witnessed_surface" \
                        and int(existing.get("retellings") or 0) == 0:
                    continue
                # Seeing beats hearsay. Replace in place so chronology and the
                # report cap do not change merely because confidence improved.
                reports[reports.index(existing)] = firsthand
                known[event_id] = firsthand
                acquired += 1
                changed = True
                continue
            reports.append(firsthand)
            known[event_id] = firsthand
            acquired += 1
            changed = True

        if changed:
            state[STATE_KEY] = reports[-REPORT_CAP:]
            save_state(cid, entry, state, frame_id=ctx.turn.frame_id)

    crowd_opportunities, crowd_acquired = _crowds_acquire(
        ctx, event_rows, standing)

    return {"enabled": True, "events_offered": len(event_ids),
            "public_surfaces": public_surfaces,
            "carrier_opportunities": carrier_opportunities,
            "acquired": acquired, "carriers_moved": moved,
            "crowd_opportunities": crowd_opportunities,
            "crowd_acquired": crowd_acquired}


def _crowds_acquire(ctx, event_rows, surfaces):
    """A crowd standing where a public surface lands witnesses it too.

    The design named crowds the first anonymous carrier, and `apply_tellings`
    could already make one retell -- but nothing ever put anything IN one, so
    across a fifty-beat quest with two throngs standing in eventful rooms,
    every crowd finished holding nothing and the whole crowd-carrier layer was
    unreachable except by an explicit Director telling that never came.

    Acquisition is the same physics as a registered character's: only a
    non-empty public `witnessed` surface, only for a crowd whose own room it
    landed in (new fires plus the same bounded arrival window a walking body
    gets), stored verbatim at the source -- a crowd that watched the well seal
    contains eyewitnesses, and degrading here would make the whole square
    wrong about what it saw together. Degradation still happens where it
    always did: at each retelling.

    Runs after `commit_crowds` in the same turn transaction (the domain order
    pins this), so it reads the crowd list this beat's ops produced.
    """
    from core.db import wget, wset

    cid = ctx.chat.id
    opportunities = acquired = 0
    standing = [dict(c) for c in
                wget(cid, crowds_model.CROWDS_WORLD_KEY, []) or []
                if isinstance(c, dict)]
    dirty = False
    for i, crowd in enumerate(standing):
        room = str(crowd.get("room_uid") or "")
        if not room:
            continue
        here = surfaces(room)
        for row, payload, witnessed in event_rows + here:
            if str(row["location_id"]) != room:
                continue
            opportunities += 1
            updated = crowds_model.add_hearsay(crowd, {
                "world_event_id": str(row["event_id"]),
                "source_event_id": str(payload.get("source_event_id") or ""),
                "claim": witnessed,
                "kind": str(row["kind"]),
                "occurred_at": float(row["occurred_at"]),
                "acquired_turn": int(ctx.turn.idx),
                "retellings": 0,
                "told_by": "",
                "provenance": "witnessed_surface",
            })
            if updated is not crowd:
                standing[i] = crowd = updated
                acquired += 1
                dirty = True
    if dirty:
        wset(cid, crowds_model.CROWDS_WORLD_KEY, standing)
    return opportunities, acquired


def persona_entry(cid, chat, scene, *, frame_id=None):
    """The player, shaped like any other carrier — or None if unresolvable.

    Failing toward None rather than a placeholder keeps the old behaviour for
    a chat with no resolvable persona: only registered characters carry, which
    is the safe direction (`couriers._player_name` fails the same way).

    THE FRAME IS READ, exactly as `_crowd_index` reads it: `PERSONA_STATE_KEY`
    is frame-scoped, so a bare `wget` answers with whichever era the ambient
    `active_frame_id` happens to name -- the caller's own era only by
    accident.
    """
    from core.db import wget, wget_for_frame
    from story.scene import persona_of

    from story.character_schema import persona_name

    if chat is None or not hasattr(chat, "get"):
        return None
    try:
        persona = persona_of(chat)
    except Exception:                          # noqa: BLE001 - absent persona
        return None
    persona = persona or {}
    # A normalized persona keeps its name under `identity`, exactly as a
    # character does; reading a flat `name` off it silently yields None and
    # the player drops back out of the index, which is how this went unnoticed
    # the first time it was written.
    identity = persona.get("identity") or {}
    name = str(persona_name(persona) or identity.get("name") or "").strip()
    if not name:
        return None
    state = (wget_for_frame(cid, PERSONA_STATE_KEY, frame_id, {})
             if frame_id is not None
             else wget(cid, PERSONA_STATE_KEY, {})) or {}
    return {"row": None, "persona": True, "name": name,
            "aliases": [str(a) for a in (identity.get("aliases") or []) if a],
            "uid": str(identity.get("uid") or ""),
            "state": state if isinstance(state, dict) else {},
            "room": str(room_of(scene, name) or "")}


def save_state(cid, entry, state, *, frame_id=None):
    """Persist one carrier's state, wherever that carrier keeps it.

    The one place the two homes meet. Cast state is a column; persona state is
    a world key. Branching at each of the five call sites would be a guard
    every writer had to remember, and this project's history is unambiguous
    about what happens to those.
    """
    # Every ledger write invalidates the turn's carrier index (`_carriers`).
    # Counted HERE because this is the one place all three homes meet, so no
    # writer has to remember to say it -- the same argument the function's
    # own docstring makes about the branch. The three early returns are why
    # this is a `finally` rather than a line at the top.
    global _LEDGER_WRITES
    try:
        if entry.get("charter"):
            from world.charter_runtime import save_carrier_state

            save_carrier_state(cid, entry, state, frame_id=frame_id)
            return
        if entry.get("persona"):
            from core.db import wset, wset_for_frame

            if frame_id is not None:
                wset_for_frame(cid, PERSONA_STATE_KEY, state, frame_id)
            else:
                wset(cid, PERSONA_STATE_KEY, state)
            return
        set_char_state(cid, entry["row"]["id"],
                       json.dumps(state, ensure_ascii=False),
                       frame_id=frame_id)
    finally:
        # AFTER the write, not before. `core/db.py:2668` (`_wset_encoded`)
        # made this exact choice for the world-row read tokens and states the
        # reason: a reader landing between the bump and the write would
        # otherwise cache the OLD value under the NEW token and keep serving
        # it, where bumping after means the worst interleaving costs its
        # successor a re-fetch. This counter cites that mechanism, so it
        # matches its ordering. Unreachable today -- every ledger write runs
        # inside commit under the per-turn lock, sequentially -- and the
        # `finally` also bumps when the write RAISED, which is the same safe
        # direction: a rebuild nobody needed (review 2026-09-07, C9).
        _LEDGER_WRITES += 1


def _keys_of(entry):
    """Every name one carrier answers to, folded."""
    return [str(key).strip().casefold()
            for key in [entry.get("name"), entry.get("uid"),
                        *(entry.get("aliases") or [])] if key]


def _private_entries(entries):
    """A caller's own copy of the index.

    Every consumer of `_carriers` mutates the `state` it was handed --
    `advance_carriers` appends an acquisition, `apply_tellings` appends a
    copy, `run_couriers` and `run_artifacts` both do -- and then saves it.
    Before the memo each call built its own entries, so no consumer could see
    another's half-finished mutation; handing every caller a private copy is
    what keeps that true. The `row` is a read-only sqlite row shared by
    reference (only `row["id"]` is ever read from it); only the mutable
    ledger is deepcopied.
    """
    return [{**entry, "state": copy.deepcopy(entry.get("state"))}
            for entry in entries]


def _positions_stamp(scene):
    """What `_build_carriers` reads out of the scene, cheap enough to compare.

    Every room in the index comes from `room_of(scene, name)` -- through
    `_character_room` for a cast row and `persona_entry` for the player --
    and `room_of` answers from `scene["positions"]`. So two scenes whose
    positions agree place every carrier in the same room.

    Why the memo carries this as well as the scene's identity: identity is
    conservative for a NEW dict and OPTIMISTIC for one mutated IN PLACE, which
    has the same id. Demonstrated on bench chat 114 -- one ctx, one scene
    object, `positions["Mora"]` "square" -> "road" with no ledger write
    between two reads -- where the memo answered room "square" and a fresh
    walk answered "road". It costs 0.0007 ms where the walk it guards costs
    15.7 ms on that same scene -- 45 ms under the load the headline below was
    taken at (review 2026-09-07, C9) -- so the assumption is bought out
    rather than argued for.

    A `positions` this cannot order -- a non-string key, which JSON storage
    does not produce -- yields a fresh object equal to nothing, so the memo
    rebuilds. That is the safe direction.
    """
    try:
        return tuple(sorted(((scene or {}).get("positions") or {}).items()))
    except (AttributeError, TypeError):
        return object()


def _carriers(cid, frame_id, scene, chat=None, ctx=None):
    """The turn's carrier index, memoised on `ctx` (review 2026-09-07, C9).

    Six rebuilds per turn of one enumeration: the Director's carried-report
    view at interpret and at resolve, then `advance_carriers`, `apply_tellings`,
    `run_couriers` and `run_artifacts`, all four of them consecutive inside
    `commit_information_carriers` and all four handed the SAME scene object.
    Measured on chat 114 (the 307-body charter town, 63 charter carriers in
    reach): 45 ms a rebuild, of which 30 ms is `charter_runtime.carrier_entries`
    walking the registry -- 270 ms a turn to answer the same question six times.

    The key is what the derivation READS: the chat, the frame, the scene it
    resolves rooms against, and `_LEDGER_WRITES` -- so a write to any
    carrier's ledger, in any of the three homes, rebuilds. A caller that
    passes no ctx (or a context with no side channels) rebuilds, exactly as
    before.

    THE SCENE IS KEYED TWICE, by identity and by `_positions_stamp`, because
    identity alone answers only half the question. A fresh `get_scene` dict is
    a different object and rebuilds -- conservative. A dict mutated IN PLACE
    is the SAME object, and keying by identity alone would have served the old
    rooms: bench chat 114, one ctx, `positions["Mora"]` "square" -> "road"
    between two reads with no ledger write, memo "square" against a fresh walk
    "road". No pipeline caller does that today, but the one test that mutates
    a scene in place between two carrier reads
    (tests/test_carriers.py::test_carrier_floor_has_no_model_or_provider_call)
    survived only by the accident of an intervening acquisition write
    bumping the counter. The fingerprint costs 0.0007 ms against that walk,
    so the memo does not rest on that accident.
    """
    slot = None
    if ctx is not None:
        try:
            slot = ctx.get(_CARRIER_MEMO)
        except (TypeError, AttributeError):
            slot = None
    stamp = (cid, frame_id, _LEDGER_WRITES, _positions_stamp(scene))
    if isinstance(slot, tuple) and len(slot) == 4:
        held_stamp, held_scene, held_chat, entries = slot
        if held_stamp == stamp and held_scene is scene and held_chat is chat:
            return _private_entries(entries)
    entries = _build_carriers(cid, frame_id, scene, chat=chat)
    if ctx is not None:
        try:
            ctx[_CARRIER_MEMO] = (stamp, scene, chat, entries)
        except (TypeError, AttributeError):
            pass                   # a context that keeps no side channels
    return _private_entries(entries)


def _build_carriers(cid, frame_id, scene, chat=None):
    """Every body that can hold a report this beat, in one list.

    Two storage homes, one enumeration. A cast member's reports live in a
    `chat_chars.cstate` column and the player's in a world key, and the whole
    point of building the entries here is that nothing downstream has to know
    which -- `save_state` is handed the entry and writes it wherever that
    carrier keeps it.

    EXTANT cast, not active. Acquisition is about a body being somewhere;
    being dormant is a decision about what the engine spends on a character,
    not a claim that they have left the world. Reading only the active cast
    made the whole "an absent mind learns something" route unreachable by
    construction: `full_agent_candidates` admits a dormant subject who has
    carried reports newer than their last tick, and a dormant subject could
    never acquire one. Measured on a fifty-beat quest -- the villain stood in
    the room where his own working completed, and learned nothing until the
    hero walked in and made him active. An antagonist who has always been
    off-screen is exactly the character that tier exists for, and was the one
    character it could not reach.

    The PLAYER is the next ring out and the same argument again: a body
    standing in the room where something happened learns it. `0bed7cf` gave
    the player somewhere to hold a report and made them a sender; without
    them here they could stand in the square while the bell rang, beside an
    NPC acquiring it, and learn nothing forever.

    Last, and dropped outright if a registered body already answers to that
    name -- a body with a row is the more specific reading, and admitting the
    player beside their namesake would take the room's one surface twice into
    two different homes.
    """
    entries = []
    taken = set()
    for row in extant_cast(cid, frame_id):
        try:
            sheet = json.loads(row["sheet"] or "{}")
        except (TypeError, ValueError):
            sheet = {}
        # One identity reader for every name a carrier answers to (review
        # 2026-09-07 B12), shared with `scene.cast_scene_context` so the
        # dossier the director reads and the ledger a report lands in cannot
        # hold two different alias lists for one body.
        identity = character_identity(sheet or {})
        try:
            state = json.loads(row["cstate"] or "{}")
        except (TypeError, ValueError):
            state = {}
        entry = {
            "row": row,
            "state": state if isinstance(state, dict) else {},
            "name": identity["name"],
            "uid": identity["uid"],
            "aliases": identity["aliases"],
            "room": _character_room(scene, sheet),
        }
        entries.append(entry)
        taken.update(_keys_of(entry))

    player = persona_entry(cid, chat, scene, frame_id=frame_id)
    if player and not (set(_keys_of(player)) & taken):
        entries.append(player)
        taken.update(_keys_of(player))

    # Charter people join last: a promoted/full character or the persona is
    # the more specific owner of a colliding name. Unbound bodies expose this
    # same bounded interface, so every existing physical handoff can address
    # them without teaching each delivery mechanism about Charter.
    from world.charter_runtime import carrier_entries

    for entry in carrier_entries(cid, frame_id):
        keys = set(_keys_of(entry))
        if not keys or keys & taken:
            continue
        entries.append(entry)
        taken.update(keys)
    return entries


def carried_reports_view(cid, frame_id, scene, chat=None, cap=PAYLOAD_CAP,
                         ctx=None):
    """Who is carrying what, as [{who, world_event_id, gist, retellings}].

    THE one enumeration of held reports for anything that has to name a
    `world_event_id` in an op -- built on `_carriers`, so it answers for
    every body that can hold a report: extant cast (dormant included) and
    the player. The Director's carried-report view used to rebuild this
    walk over `active_cast`/`cstate` alone, which silently omitted the two
    carriers `_carriers`' own docstring argues for -- so a player who
    legitimately acquired a surface could never spread it: the one stage
    that writes `telling_ops`/`courier_ops` held an empty list and had
    nothing to name (docs/UNBUILT.md 1.31). Public so no caller ever has a
    reason to re-enumerate carriers itself; two spellings of one walk is
    exactly how that defect was minted.

    The gist is the holder's OWN degraded wording, not the objective event:
    handing this to the Director tells it what a carrier could say rather
    than what is true. Fine for the Director, which already owns objective
    causality -- never hand this to a character, who would be reading other
    minds.
    """
    out = []
    for entry in _carriers(cid, frame_id, scene, chat=chat, ctx=ctx):
        state = entry.get("state")
        if not isinstance(state, dict):
            continue
        for report in (state.get(STATE_KEY) or [])[-cap:]:
            if not isinstance(report, dict) or not report.get("world_event_id"):
                continue
            out.append({
                "who": entry.get("name"),
                "world_event_id": report.get("world_event_id"),
                "gist": report.get("claim"),
                "retellings": report.get("retellings", 0),
            })
    return out


#: How many claims the Writers' Room is shown at once (`unbacked_claims`),
#: the rest counted beside them. A PER-CALL cap guarding the payload of
#: every planning step, never the claims themselves: nothing is dropped from
#: any mind's ledger. The slots go first to the rows whose words carry a
#: name nobody the world holds answers to (`names_nobody_holds`) -- the case
#: the owner's D6 ruling is about -- and only then, newest first, to the
#: rest, so an invented person is not pushed out by eight later tellings of
#: what everybody saw. Eight is every distinct claim the Brackwater run made
#: in thirty beats (scratch story 166, 2026-10-10: eight ids across fifteen
#: held rows), so an ordinary story is shown all of its own; a claim's words
#: are at most 320 characters (`_invented_claim`), so the section stays near
#: 3k characters.
ROOM_CLAIMS_SHOWN = 8
#: Hearers named beside one claim, the rest counted -- a market's worth of
#: listeners is a number, not a list, to an author deciding whether a
#: person exists.
ROOM_CLAIM_HEARERS_SHOWN = 4
#: A claim's words as the Room is shown them: the length every report's
#: words are written at in the first place (`_invented_claim`, and the
#: witnessed surfaces `advance_carriers` copies), so nothing a ledger holds
#: is cut -- a bound only for a row some other writer stored longer.
ROOM_CLAIM_CHARS = 320

#: Where an introduction's `learns` stops naming and starts describing, when
#: the description is set off: the first comma, semicolon, colon, opening
#: bracket or set-off dash, as English and Japanese prose write them.
#: Punctuation, not vocabulary -- the same posture as
#: `agents/impossible_knowledge`'s sentence bounds. Measured on story 166,
#: idx 19: "Tam Elver, tallyman at the bonded store for the Marsh Agency" is
#: a name and then its bearer's work; read whole, it answered to the room its
#: description named, and the man nobody holds was held. A description NOT
#: set off stays in the head ("Tommy Reyes is a patient at Blackwood
#: Sanatorium" is one head), and so does a `learns` that is no name at all --
#: the encoder's card allows "a name, a title, or a short descriptor" -- so a
#: head marks a claim only where the claim says it whole (`_said_whole`).
_NAME_HEAD_END = re.compile(r"\s*(?:[,;:(\[，、；：（「]|\s[-–—]{1,2}\s|[–—])")


def _name_head(learns):
    """An introduction's `learns` up to any set-off description: the name,
    when the encoder wrote one, and otherwise whatever it did write."""
    text = " ".join(str(learns or "").split())
    return _NAME_HEAD_END.split(text, maxsplit=1)[0].strip() if text else ""


def _said_whole(head, words):
    """Do these words say this head WHOLE -- as the encoder wrote it, or
    without a leading article ("The Doctor" is said "Doctor",
    `commit_common._ADDRESS_ARTICLES`) -- at a name boundary in either pack
    (`commit_common._form_in`)?

    Never by a part of it. A head is whatever an introduction's `learns`
    began with, and its last word is a surname only when the head is a name:
    read by their last words and last two, the clauses and descriptors
    play.db holds as heads mark claims that name nobody -- "days ago" from
    "something escaped from the bio wing three days ago", "name" from
    "Tamamo is Kaa Sama's real name", "inspector" from "health-board
    inspector" (review RP2-N1, 2026-10-10: of the 43 heads nobody holds
    across play.db's 85 chat-frames with introductions, 16 are a person's
    name alone and 13 whole clauses). The surname alone is read where the
    name is known to be one -- a person a model chose to plant
    (`room_sketch._claimed`)."""
    from persist.commit import _ADDRESS_ARTICLES, _form_in
    head = str(head or "").strip()
    if not head:
        return False
    forms = [head]
    folded = head.casefold()
    for article in _ADDRESS_ARTICLES:
        rest = head[len(article):].strip()
        if folded.startswith(article) and rest:
            forms.append(rest)
    body = str(words or "")
    return any(_form_in(form, body) for form in forms)


def _held_identity_roster(cid, frame_id, scene, chat):
    """Every name an identity the world holds answers to, in its own
    spelling: the registered cast and their aliases, the player and theirs,
    every charter body and every plan with its aliases
    (`plot_packages.reserved_identities`, the Room's one answer to who the
    world holds), every tracked presence the story has a name for, every
    scene entity and every room. What `names_nobody_holds` resolves against,
    so "nobody holds this name" means nobody, not nobody registered."""
    from core.db import wget_for_frame
    from story.character_schema import (character_identity_from_text,
                                        persona_name)
    from story.plot_packages import reserved_identities
    from story.scene import persona_of

    names = []

    def add(value):
        value = str(value or "").strip()
        if value and value not in names:
            names.append(value)

    identities = reserved_identities(cid, frame_id)
    for row in identities.get("cast") or ():
        add(row.get("name"))
    # The per-story card over the reusable one, as `scene.active_cast`
    # resolves it: an alias the story's own card gives is a name it holds.
    for row in q("SELECT COALESCE(cc.sheet, c.sheet) AS sheet FROM chat_chars cc "
                 "JOIN characters c ON c.id=cc.char_id WHERE cc.chat_id=?", (cid,)):
        identity = character_identity_from_text(row["sheet"])
        add(identity.get("name"))
        for alias in identity.get("aliases") or ():
            add(alias)
    for bodies in (identities.get("charter_bodies") or {}).values():
        for body in bodies:
            add(body)
    for plan in (identities.get("plans") or {}).values():
        add(plan.get("name"))
        for alias in plan.get("aliases") or ():
            add(alias)
    if chat:
        try:
            persona = persona_of(dict(chat))
            add(persona_name(persona))
            for alias in ((persona or {}).get("identity") or {}).get("aliases") or ():
                add(alias)
        except Exception:
            pass
    try:
        from persist.commit import presence_display_name, presence_is_unnamed
        # The frame's own tracked people: `background_presences` is a
        # frame-scoped key, read for the frame asked, not the ambient one.
        presences = wget_for_frame(cid, "background_presences", frame_id, {}) or {}
        for key, record in presences.items():
            if isinstance(record, dict) and not presence_is_unnamed(key, record):
                add(presence_display_name(key, record))
    except Exception:
        pass
    for eid, entity in ((scene or {}).get("entities") or {}).items():
        if isinstance(entity, dict):
            add(entity.get("name"))
            for alias in entity.get("aliases") or ():
                add(alias)
    for rid, room in ((scene or {}).get("rooms") or {}).items():
        add(rid)
        if isinstance(room, dict):
            add(room.get("name"))
    return names


def names_nobody_holds(cid, frame_id, scene=None, chat=None):
    """``{head: first beat}``: what the story has heard given to someone as
    who they are that no identity the world holds answers to.

    READ FROM THE ENCODER'S OWN RECORD, NEVER FROM PROSE. Which words of a
    claim are a name is not something code can read in every language this
    engine writes: `agents/impossible_knowledge.naming_tokens` reads a name
    from where it is capitalised, and says itself that a script with no
    letter case yields none, so in the Japanese pack it would find nothing;
    and the engine's identity resolution (`commit_common._resolve_roster_name`
    and the address forms under it) answers in both packs but only "which
    name the world HOLDS does this text say", never "what name does it say
    that nobody holds". The one record of who somebody was revealed to be is
    the encoder's `introductions` -- `{who, learns}`, "identity or name
    knowledge explicitly exchanged or revealed in this beat" -- on each
    beat's committed diff. So the heads are the `learns` of every
    introduction this frame's beats recorded, up to any set-off description
    (`_name_head`), and nobody holds one when neither of the engine's two
    readings of a name answers to it over every identity the world holds
    (`_held_identity_roster`): `agents.common._recognizes`, a title or a part
    of a held name ("Mrs Gale" is Hester Gale, "Sabine" is Sabine Oyelaran),
    and `commit_common._resolve_roster_name`, the one `commit_mapping` gives
    this same field (a held name inside it, an honorific attached in the
    Japanese pack). The description after a head is never read: "Tam Elver,
    tallyman at the bonded store" read whole answered to the room named "the
    bonded store" (story 166). `commit_mapping` drops such an introduction,
    because nobody is there to be known; this keeps the head. When in doubt
    it is HELD -- a held row is shown in its turn, as it always was, where an
    unheld one is put first.

    A HEAD IS NOT ALWAYS A NAME. The encoder's card lets `learns` be "a name,
    a title, or a short descriptor", and play.db holds whole clauses too
    ("Tamamo is Kaa Sama's real name"): of the 43 heads this returned across
    play.db's 85 chat-frames with introductions, 16 are a person's name
    alone and 13 whole clauses, the rest titles, descriptors, places and
    institutions and one name with its description run on (review RP2-N1,
    2026-10-10). So a head marks a claim only where the claim says it whole
    (`unbacked_claims`, `_said_whole`), and whether a marked head is a
    person stays the Room's to read.

    Read afresh each time, so a person the Room has since planted under that
    name is held and drops out. A pure read: the active variant of each
    beat's Director stage, as `impossible_knowledge.already_aired` reads it.
    """
    from agents.common import _recognizes
    from persist.commit import _address_index, _resolve_roster_name

    if scene is None:
        from story.room_slice import read_scene
        scene = read_scene(cid, frame_id) or {}
    if chat is None:
        row = q("SELECT * FROM chats WHERE id=?", (cid,), one=True)
        chat = dict(row) if row else None
    rows = q("SELECT t.idx AS idx, v.content AS content FROM turns t "
             "JOIN steps s ON s.turn_id=t.id "
             "JOIN variants v ON v.step_id=s.id AND v.active=1 "
             "WHERE t.chat_id=? AND t.frame_id IS ? "
             "AND s.key IN ('director_resolve','director_establish') "
             "AND (v.content LIKE '%\"introductions\": [{%' "
             "OR v.content LIKE '%\"introductions\":[{%') ORDER BY t.idx",
             (cid, frame_id))
    heard = []
    for row in rows:
        try:
            diff = (json.loads(row["content"]) or {}).get("state_diff") or {}
        except (TypeError, ValueError, AttributeError):
            continue
        for intro in diff.get("introductions") or ():
            if isinstance(intro, dict) and str(intro.get("learns") or "").strip():
                heard.append((row["idx"], str(intro["learns"])))
    if not heard:
        return {}
    roster = _held_identity_roster(cid, frame_id, scene, chat)
    index = _address_index(roster)
    held = set(roster)
    out = {}
    for idx, learns in heard:
        head = _name_head(learns)
        if not head or head in out:
            continue
        if _recognizes(head, held) or _resolve_roster_name(head, roster, index):
            continue
        out[head] = idx
    return out


def unbacked_claims(cid, frame_id, rooms, scene=None, chat=None,
                    cap=ROOM_CLAIMS_SHOWN):
    """Words said aloud near the story with no report behind them, for the
    Writers' Room: ``(rows, total)``.

    WHAT CODE KNOWS, AND NOTHING FINER. A `claim:` id (`_invented_claim`)
    means the Director's telling cited no report its speaker carried -- and a
    happening on screen is not a world event, so most of what a character
    tells another about what both just saw is filed so too (story 166: at
    least four of its eight claims are true of the record, the coat on the
    stake among them). Some of it is a lie or a mistake; nothing here can say
    which, and nothing here says it. The owner's ruling on D6 (2026-10-09):
    an invented townsperson stays the character's claim, and the Room MAY
    ratify it when it plans -- so the Room is shown the claims, and nothing
    here plans anybody.

    THE SLOTS GO TO THE INVENTED PERSON FIRST: a row whose words say WHOLE a
    head nobody the world holds answers to (`names_nobody_holds`,
    `_said_whole`) is shown before any other, and carries those heads as
    ``unheld_names``; the rest follow newest first. Whole, because a head is
    whatever the encoder wrote down -- a name, a title, a descriptor, now and
    then a clause -- and read by its last word, a clause's "ago" or "name"
    marked claims that named nobody (review RP2-N1). Whether a marked head
    is a person or a place stays the Room's to read.

    A CLAIM THE PLAYER MADE rides only when the story's player authority
    grants the player the world (`scene.PLAYER_AUTHORITY_GRANTS`'s `world`,
    which the default `world_author` does): what the world does with a
    player's assertion belongs to the authority settings (the owner,
    2026-10-09), and making real a person the player's character only said
    exists is the world granting that assertion. Under a stricter mode it is
    left out -- uncounted, because it is not the Room's to consider.

    WITHIN REACH means somebody there holds it: the player wherever they
    stand, and any body standing in ``rooms`` (the frontier's reach, the
    player's own room among them). A room that is the inside of a body
    stands where that body stands (`room_slice.holder_room`), both ways: a
    pilot on the deck of a boat moored at the quay is near a player on the
    quay, and near a player on the same deck -- which the frontier, planning
    only places a plan can hold, leaves out of its reach (story 166's player
    and pilot stood on the Grebe's deck from beat 13). Each row is
    ``{said, by, turn, heard_by[, unheld_names]}``:

    * ``said`` -- the words as their maker holds them, the fullest copy, when
      the maker's own row survives anywhere; else the least-retold copy;
    * ``by`` -- whoever made it up (their row says `invented`), else whoever
      told a first-hand hearer, else "" when no record names a maker;
    * ``turn`` -- when it was first said, as far as any row knows;
    * ``heard_by`` -- ``[{who, from}]``, the hearers within reach, at most
      `ROOM_CLAIM_HEARERS_SHOWN` (``heard_by_more`` counts the rest).

    A maker's `invented` is private to its maker everywhere a MIND reads
    (`apply_tellings`); the Room is an author, which reads minds by design
    (`room_tools.inspect_minds`), and its only readers are the two payload
    builders (`tests/test_a_claimed_person_is_the_rooms_to_make_real.py`).
    A pure read.
    """
    from story.character_schema import persona_name
    from story.scene import (PLAYER_AUTHORITY_GRANTS, persona_of,
                             player_authority)

    if scene is None:
        from story.room_slice import read_scene
        scene = read_scene(cid, frame_id) or {}
    if chat is None:
        row = q("SELECT * FROM chats WHERE id=?", (cid,), one=True)
        chat = dict(row) if row else None
    from story.room_slice import containment, holder_room
    inside = containment(scene)
    try:
        player = str(persona_name(persona_of(dict(chat))) or "") if chat else ""
    except Exception:
        player = ""
    player_authors_world = "world" in PLAYER_AUTHORITY_GRANTS.get(
        player_authority(cid)["mode"], frozenset())

    def stands(room):
        """A room and, when it is the inside of a body, the room that body
        stands in, outward to the first room that is nobody's inside."""
        room, out = str(room or ""), set()
        while room and room not in out:
            out.add(room)
            room = str(holder_room(scene, inside[room]) or "") \
                if room in inside else ""
        return out

    near = set()
    for room in rooms or ():
        near |= stands(room)
    held = {}
    for entry in _carriers(cid, frame_id, scene, chat=chat):
        state = entry.get("state")
        if not isinstance(state, dict):
            continue
        here = bool(entry.get("persona")) or bool(stands(entry.get("room")) & near)
        for report in state.get(STATE_KEY) or ():
            if not isinstance(report, dict):
                continue
            rid = str(report.get("world_event_id") or "")
            if not rid.startswith("claim:") or not str(report.get("claim") or "").strip():
                continue
            slot = held.setdefault(rid, {"made": None, "copies": [], "near": False})
            if report.get("provenance") == "invented":
                slot["made"] = (entry, report)
            else:
                slot["copies"].append((entry, report, here))
            slot["near"] = slot["near"] or here
    unheld = {}
    if any(slot["near"] for slot in held.values()):
        try:
            unheld = names_nobody_holds(cid, frame_id, scene=scene, chat=chat)
        except Exception as exc:
            logger.info("claims: the names nobody holds are unavailable: %s", exc)
    rows = []
    for rid, slot in held.items():
        if not slot["near"]:
            continue
        copies = sorted(slot["copies"],
                        key=lambda c: int(c[1].get("retellings") or 0))
        # The earliest beat any copy was heard: a maker's row a charter
        # mind projects carries no beat of its own (`charter_runtime.
        # carrier_entries`), and the claim is at least that old.
        heard = [c[1].get("acquired_turn") for c in copies
                 if isinstance(c[1].get("acquired_turn"), int)]
        if slot["made"] is not None:
            maker, made = slot["made"]
            said, by = made.get("claim"), str(maker.get("name") or "")
            by_player = bool(maker.get("persona"))
            turn = made.get("acquired_turn")
            if not isinstance(turn, int):
                turn = min(heard) if heard else None
        else:
            said = copies[0][1].get("claim")
            first_hand = [c for c in copies
                          if int(c[1].get("retellings") or 0) == 1]
            by = str(first_hand[0][1].get("told_by") or "") if first_hand else ""
            by_player = bool(player) and by.casefold() == player.casefold()
            turn = min(heard) if heard else None
        if by_player and not player_authors_world:
            continue
        said = " ".join(str(said or "").split())[:ROOM_CLAIM_CHARS]
        hearers = [{"who": str(entry.get("name") or ""),
                    "from": str(report.get("told_by") or "")}
                   for entry, report, here in copies if here]
        row = {"said": said, "by": by, "turn": turn,
               "heard_by": hearers[:ROOM_CLAIM_HEARERS_SHOWN]}
        if len(hearers) > ROOM_CLAIM_HEARERS_SHOWN:
            row["heard_by_more"] = len(hearers) - ROOM_CLAIM_HEARERS_SHOWN
        # Each head said WHOLE, never by its last words (`_said_whole`).
        found = [name for name in unheld if _said_whole(name, said)]
        if found:
            row["unheld_names"] = found
        rows.append((rid, row))
    rows.sort(key=lambda item: (
        0 if item[1].get("unheld_names") else 1,
        -(item[1]["turn"] if isinstance(item[1]["turn"], int) else -1),
        item[0]))
    return [row for _rid, row in rows[:max(0, int(cap))]], len(rows)


def _cast_index(cid, frame_id, scene, chat=None, ctx=None):
    """Carriers this beat, by every name each answers to.

    Reading only the active cast made a dormant body in the room
    unaddressable as a LISTENER -- a messenger could stand in front of the
    villain, speak, and be refused with "names someone unregistered". Being
    told is passive; the room check still applies.

    A dormant SPEAKER stays structurally impossible without a line: the
    spoke-this-beat gate reads the dialogue_log, and a mind the engine did
    not run said nothing for it to record.
    """
    index = {}
    for entry in _carriers(cid, frame_id, scene, chat=chat, ctx=ctx):
        for key in _keys_of(entry):
            index.setdefault(key, entry)
    return index


def _invented_claim(claim, ctx, speaker):
    """A claim with no event behind it, held by whoever made it up.

    The id is minted from the text and the speaker so it can be passed on,
    disputed and recognised later like any other -- an invented claim that
    could not be referred to could not be caught out either, and being caught
    out is the only interesting thing that ever happens to a lie.

    `claim:` rather than `event:` so nothing can mistake it for objective
    history. It is never written to `world_events`; the ledger of what
    happened must not acquire rows for things that did not.
    """
    import hashlib

    text = " ".join(str(claim or "").split())[:320]
    material = "%s|%s|%s" % (ctx.chat.id, speaker.get("name") or "", text)
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
    return {
        "world_event_id": "claim:%s" % digest,
        "source_event_id": "",
        "claim": text,
        "kind": "claim",
        "occurred_at": 0.0,
        "acquired_turn": int(ctx.turn.idx),
        "acquired_location": speaker.get("room") or "",
        "current_location": speaker.get("room") or "",
        "route": [speaker.get("room") or ""],
        "hops": 0,
        "retellings": 0,
        "told_by": "",
        # Visible to its author and to nobody downstream: the copy handed to a
        # listener is provenance `told`, exactly like a copy of the truth.
        "provenance": "invented",
    }


def _crowd_index(cid, frame_id=None):
    """Crowds standing in rooms, by uid -- the anonymous carriers.

    A crowd is exactly the carrier approach C asks for and needs no new travel
    machinery at all: `crowds.advance_crowds` already walks it along the same
    spatial graph everyone else uses, so talk moves because the market moves.

    THE FRAME IS READ, not merely accepted. `crowds` is in
    `db.FRAME_SCOPED_WORLD_KEYS`, so a plain `wget` is era-correct only by
    accident -- it redirects on the ambient `active_frame_id` a pipeline run
    happens to have set, and any caller outside one, or one whose turn belongs
    to a different frame than the ambient, got another era's throng while
    passing the right frame in. The `scene` parameter is gone: a crowd's
    roster is world state, and nothing here ever read it.
    """
    from core.db import wget, wget_for_frame

    stored = (wget_for_frame(cid, crowds_model.CROWDS_WORLD_KEY, frame_id, [])
              if frame_id is not None
              else wget(cid, crowds_model.CROWDS_WORLD_KEY, []))
    index = {}
    for crowd in stored or []:
        if isinstance(crowd, dict) and crowd.get("uid"):
            index[str(crowd["uid"]).casefold()] = dict(crowd)
    return index


def apply_tellings(ctx, scene, ops, *, names=(), places=()):
    """Copy reports from speaker to listener, one retelling fainter.

    Returns ``(applied, rejected)``. Every refusal below is a firewall rather
    than tidiness, so each is deterministic and none is left to the model:

    **The speaker must actually hold the report.** Otherwise the Director could
    hand any mind any fact by writing a sentence, which is the whole thing
    approach C exists to prevent.

    **The speaker must have spoken this beat.** Knowledge does not cross a room
    because two bodies were in it. If nobody said anything, nothing was told --
    the same grounding `apply_plan_ops` demands before a plan can exist.

    **They must be in the same room.** A telling is a thing that happens
    somewhere.

    **An exhausted claim is not passed on.** A rumor that has lost its count,
    its place and its name has stopped being about anything, and a world where
    it still circulates is the town of criers.

    The listener's copy records who they heard it FROM. A second-hand report
    that could not name its source would be indistinguishable from something
    the listener saw, and a mind cannot weigh a claim whose provenance it has
    no access to.
    """
    applied, rejected = 0, []
    ops = [op.dict() if hasattr(op, "dict") else op for op in (ops or [])]
    ops = [op for op in ops if isinstance(op, dict)]
    if not ops:
        return applied, rejected

    cid = ctx.chat.id
    frame_id = ctx.turn.frame_id
    index = _cast_index(cid, frame_id, scene,
                        chat=getattr(ctx, "chat", None), ctx=ctx)
    crowd_index = _crowd_index(cid, frame_id)
    crowds_dirty = {}

    def party(key):
        """A speaker or listener: a registered character, or a crowd.

        A crowd answers only to its uid. It has no display name by
        construction, and letting one be addressed by its composition would
        put a crowd into the name key space that five ledgers already got
        wrong.
        """
        who = index.get(key)
        if who is not None:
            return who
        crowd = crowds_dirty.get(key) or crowd_index.get(key)
        if crowd is None:
            return None
        return {"crowd": crowd, "name": crowds_model.crowd_voice(crowd),
                "room": str(crowd.get("room_uid") or ""),
                "state": None, "row": None}
    spoke = {str(line.get("speaker") or "").strip().casefold()
             for line in ((ctx.director_resolve or ctx.director_establish or {})
                          .get("dialogue_log") or [])
             if isinstance(line, dict)}
    dirty = {}
    per_speaker = {}

    for op in ops:
        speaker_key = str(op.get("speaker") or "").strip().casefold()
        listener_key = str(op.get("listener") or "").strip().casefold()
        event_id = str(op.get("world_event_id") or "").strip()
        speaker = party(speaker_key)
        listener = party(listener_key)

        if not speaker or not listener:
            rejected.append("telling names someone unregistered: %r -> %r"
                            % (op.get("speaker"), op.get("listener")))
            continue
        if speaker is listener:
            rejected.append("%s cannot tell themselves" % speaker["name"])
            continue
        if speaker.get("crowd") is None and speaker_key not in spoke:
            rejected.append(
                "%s said nothing this beat; knowledge does not cross a room "
                "because two bodies were in it" % speaker["name"])
            continue
        # A crowd is exempt from the dialogue-log check and from nothing else.
        # It murmurs continuously -- that IS its speech, and it is the one
        # thing a crowd is allowed to do, so there is no line to point at. The
        # declaration is still explicit: the Director says somebody caught the
        # talk, and co-location, holding and fan-out all still apply. Catching
        # a rumor in a market is not knowledge by proximity; it is knowledge by
        # a beat that said so.
        if not speaker["room"] or speaker["room"] != listener["room"]:
            rejected.append("%s and %s are not in the same room"
                            % (speaker["name"], listener["name"]))
            continue
        if per_speaker.get(speaker_key, 0) >= TELL_FANOUT_CAP:
            rejected.append("%s has told %d people this beat already"
                            % (speaker["name"], TELL_FANOUT_CAP))
            continue

        if speaker.get("crowd") is not None:
            speaker_reports = crowds_model.crowd_hearsay(speaker["crowd"])
        else:
            speaker_reports = (dirty.get(speaker_key)
                               or speaker["state"]).get(STATE_KEY) or []
        held = None
        for report in speaker_reports:
            if isinstance(report, dict) \
                    and str(report.get("world_event_id")) == event_id:
                held = report
                break
        if held is None and not event_id and str(op.get("claim") or "").strip():
            # A LIE, or an honest mistake, entering through the same physics as
            # the truth. This is the one thing that lets an antagonist work by
            # saying something, and it is deliberately indistinguishable
            # DOWNSTREAM: the listener's row is shaped exactly like a report of
            # something real, because a mind that could tell a lie from a fact
            # by inspecting its own memory is not a mind that can be deceived,
            # and being deceivable is the whole reason the perception layer
            # exists.
            #
            # The asymmetry is at the source only. The speaker's own row says
            # `invented` -- they know what they did -- and there is no world
            # event behind it, which nothing in the fiction can query. Nothing
            # marks it false anywhere a mind reads: wrongness stays diegetic.
            if speaker.get("crowd") is not None:
                rejected.append(
                    "a crowd repeats what it heard; it does not start things")
                continue
            invented = _invented_claim(op.get("claim"), ctx, speaker)
            speaker_state = dirty.get(speaker_key) or speaker["state"]
            speaker_state[STATE_KEY] = (
                [dict(r) for r in speaker_state.get(STATE_KEY) or []
                 if isinstance(r, dict)] + [invented])[-REPORT_CAP:]
            dirty[speaker_key] = speaker_state
            held, event_id = invented, invented["world_event_id"]
        if held is None:
            rejected.append("%s does not carry %r and cannot pass it on"
                            % (speaker["name"], event_id or "that report"))
            continue

        retellings = max(0, int(held.get("retellings") or 0)) + 1
        if degradation.is_exhausted(retellings):
            rejected.append(
                "that story has lost its count, its place and its name; it "
                "stops here")
            continue

        if listener.get("crowd") is not None:
            listener_state, listener_reports = None, crowds_model.crowd_hearsay(
                crowds_dirty.get(listener_key) or listener["crowd"])
        else:
            listener_state = dirty.get(listener_key) or listener["state"]
            listener_reports = [dict(r) for r in listener_state.get(STATE_KEY) or []
                                if isinstance(r, dict)]
        if any(str(r.get("world_event_id")) == event_id
               for r in listener_reports):
            rejected.append("%s has already heard that" % listener["name"])
            continue

        copy = {
            "world_event_id": event_id,
            "source_event_id": str(held.get("source_event_id") or ""),
            # What they HEARD, not what happened. Stepwise degradation lands
            # where telling it twice would, so storing the fainter text costs
            # nothing and keeps the truth out of a row that never earned it.
            "claim": degradation.degrade(
                held.get("claim"), retellings, names=names, places=places),
            "kind": str(held.get("kind") or ""),
            "occurred_at": float(held.get("occurred_at") or 0.0),
            "acquired_turn": int(ctx.turn.idx),
            "acquired_location": listener["room"],
            "current_location": listener["room"],
            "route": [listener["room"]],
            "hops": 0,
            "retellings": retellings,
            "told_by": speaker["name"],
            "provenance": "told",
        }
        if listener.get("crowd") is not None:
            crowds_dirty[listener_key] = crowds_model.add_hearsay(
                crowds_dirty.get(listener_key) or listener["crowd"], copy)
        else:
            listener_reports.append(copy)
            listener_state[STATE_KEY] = listener_reports[-REPORT_CAP:]
            dirty[listener_key] = listener_state
        per_speaker[speaker_key] = per_speaker.get(speaker_key, 0) + 1
        applied += 1

    for key, state in dirty.items():
        save_state(cid, index[key], state, frame_id=frame_id)
    if crowds_dirty:
        from core.db import wget, wset

        standing = [dict(c) for c in wget(cid, crowds_model.CROWDS_WORLD_KEY, [])
                    or [] if isinstance(c, dict)]
        for i, crowd in enumerate(standing):
            replacement = crowds_dirty.get(str(crowd.get("uid") or "").casefold())
            if replacement is not None:
                standing[i] = replacement
        wset(cid, crowds_model.CROWDS_WORLD_KEY, standing)
    return applied, rejected
