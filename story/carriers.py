"""Physical information carriers for living-world approach C.

Truth in ``world_events`` is not knowledge. This module creates the first
legitimate bridge: when a mechanically fired event has a non-empty public
``witnessed`` surface, only registered characters physically at that location
acquire that surface. The report then travels because its holder travels; it is
stored in that character's frame-specific state and exposed only to that
character's private agent payload.

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

import json

from world import crowds as crowds_model
from world import degradation
from story.character_schema import normalize_character_data
from core.db import q
from world.living_world import living_world_allows, living_world_config
from story.scene import extant_cast, set_char_state
from world.spatial import room_of


STATE_KEY = "carried_reports"
REPORT_CAP = 16
ROUTE_CAP = 12
PAYLOAD_CAP = 4

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
ARRIVAL_SURFACES = 3

#: How many listeners one speaker may reach in a single beat. Bounded route
#: fan-out, and the deterministic half of the "town of criers" answer: a story
#: told to a room does not arrive in every mind in it at once, because a beat
#: is a moment and a moment holds one telling to a few people.
TELL_FANOUT_CAP = 3


def _character_room(scene, sheet):
    identity = normalize_character_data(sheet or {}).get("identity") or {}
    keys = [identity.get("name"), identity.get("uid"),
            *(identity.get("aliases") or [])]
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


def advance_carriers(ctx, scene, world_event_result):
    """Acquire public event surfaces and update each holder's physical trail.

    Runs inside ``commit_all`` after the normal character-state/memory domain,
    so it merges onto that domain's final state instead of being overwritten by
    a prepared state update. All writes share the turn transaction.
    """
    cid = ctx.chat.id
    if not living_world_allows(
            living_world_config(cid), "rumor_ledger", "floor"):
        offered = len((world_event_result or {}).get("events") or [])
        return {"enabled": False, "events_offered": offered,
                "public_surfaces": 0, "carrier_opportunities": 0,
                "acquired": 0, "carriers_moved": 0}

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
    standing_rows = []
    for row in q("SELECT * FROM world_events WHERE chat_id=? AND frame_id IS ? "
                 "AND location_id IS NOT NULL "
                 "ORDER BY occurred_at DESC LIMIT ?",
                 (cid, ctx.turn.frame_id, ARRIVAL_SURFACES * 4)) or []:
        if str(row["event_id"]) in {str(r["event_id"]) for r, _, _ in event_rows}:
            continue
        try:
            payload = json.loads(row["payload"] or "{}")
        except (TypeError, ValueError):
            payload = {}
        witnessed = " ".join(str((payload or {}).get("witnessed") or "").split())
        if witnessed:
            standing_rows.append((dict(row), payload, witnessed[:320]))

    public_surfaces = len(event_rows)
    carrier_opportunities = acquired = moved = 0
    # Every body that can hold a report, the player among them -- see
    # `_carriers` for why the list is extant cast plus persona rather than the
    # active cast this loop started out reading.
    for entry in _carriers(cid, ctx.turn.frame_id, scene,
                           chat=getattr(ctx, "chat", None)):
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

        known = {str(r.get("world_event_id")) for r in reports}
        here = [r for r in standing_rows
                if str(r[0]["location_id"]) == current_room][:ARRIVAL_SURFACES]
        for row, payload, witnessed in event_rows + here:
            if str(row["location_id"]) != current_room:
                continue
            carrier_opportunities += 1
            if str(row["event_id"]) in known:
                continue
            reports.append({
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
            })
            known.add(str(row["event_id"]))
            acquired += 1
            changed = True

        if changed:
            state[STATE_KEY] = reports[-REPORT_CAP:]
            save_state(cid, entry, state, frame_id=ctx.turn.frame_id)

    crowd_opportunities, crowd_acquired = _crowds_acquire(
        ctx, event_rows, standing_rows)

    return {"enabled": True, "events_offered": len(event_ids),
            "public_surfaces": public_surfaces,
            "carrier_opportunities": carrier_opportunities,
            "acquired": acquired, "carriers_moved": moved,
            "crowd_opportunities": crowd_opportunities,
            "crowd_acquired": crowd_acquired}


def _crowds_acquire(ctx, event_rows, standing_rows):
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
        here = [r for r in standing_rows
                if str(r[0]["location_id"]) == room][:ARRIVAL_SURFACES]
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
    if entry.get("persona"):
        from core.db import wset, wset_for_frame

        if frame_id is not None:
            wset_for_frame(cid, PERSONA_STATE_KEY, state, frame_id)
        else:
            wset(cid, PERSONA_STATE_KEY, state)
        return
    set_char_state(cid, entry["row"]["id"],
                   json.dumps(state, ensure_ascii=False), frame_id=frame_id)


def _keys_of(entry):
    """Every name one carrier answers to, folded."""
    return [str(key).strip().casefold()
            for key in [entry.get("name"), entry.get("uid"),
                        *(entry.get("aliases") or [])] if key]


def _carriers(cid, frame_id, scene, chat=None):
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
        identity = normalize_character_data(sheet or {}).get("identity") or {}
        try:
            state = json.loads(row["cstate"] or "{}")
        except (TypeError, ValueError):
            state = {}
        entry = {
            "row": row,
            "state": state if isinstance(state, dict) else {},
            "name": str(identity.get("name") or ""),
            "uid": str(identity.get("uid") or ""),
            "aliases": [a for a in (identity.get("aliases") or []) if a],
            "room": _character_room(scene, sheet),
        }
        entries.append(entry)
        taken.update(_keys_of(entry))

    player = persona_entry(cid, chat, scene, frame_id=frame_id)
    if player and not (set(_keys_of(player)) & taken):
        entries.append(player)
    return entries


def carried_reports_view(cid, frame_id, scene, chat=None, cap=PAYLOAD_CAP):
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
    for entry in _carriers(cid, frame_id, scene, chat=chat):
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


def _cast_index(cid, frame_id, scene, chat=None):
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
    for entry in _carriers(cid, frame_id, scene, chat=chat):
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
    index = _cast_index(cid, frame_id, scene, chat=getattr(ctx, "chat", None))
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
