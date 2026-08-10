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

import crowds as crowds_model
import degradation
from character_schema import normalize_character_data
from db import q
from living_world import living_world_allows, living_world_config
from scene import active_cast, set_char_state
from spatial import room_of


STATE_KEY = "carried_reports"
REPORT_CAP = 16
ROUTE_CAP = 12
PAYLOAD_CAP = 4

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

    public_surfaces = len(event_rows)
    carrier_opportunities = acquired = moved = 0
    for cast_row in active_cast(cid, ctx.turn.frame_id):
        try:
            sheet = json.loads(cast_row["sheet"] or "{}")
        except (TypeError, ValueError):
            sheet = {}
        current_room = _character_room(scene, sheet)
        try:
            state = json.loads(cast_row["cstate"] or "{}")
        except (TypeError, ValueError):
            state = {}
        if not isinstance(state, dict):
            state = {}
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
        for row, payload, witnessed in event_rows:
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
            set_char_state(cid, cast_row["id"],
                           json.dumps(state, ensure_ascii=False),
                           frame_id=ctx.turn.frame_id)

    return {"enabled": True, "events_offered": len(event_ids),
            "public_surfaces": public_surfaces,
            "carrier_opportunities": carrier_opportunities,
            "acquired": acquired, "carriers_moved": moved}


def _cast_index(cid, frame_id, scene):
    """Registered characters this beat, by every name they answer to."""
    index = {}
    for row in active_cast(cid, frame_id):
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
            "room": _character_room(scene, sheet),
        }
        for key in [identity.get("name"), identity.get("uid"),
                    *(identity.get("aliases") or [])]:
            if key:
                index.setdefault(str(key).strip().casefold(), entry)
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


def _crowd_index(cid, scene, frame_id):
    """Crowds standing in rooms, by uid -- the anonymous carriers.

    A crowd is exactly the carrier approach C asks for and needs no new travel
    machinery at all: `crowds.advance_crowds` already walks it along the same
    spatial graph everyone else uses, so talk moves because the market moves.
    """
    from db import wget

    index = {}
    for crowd in wget(cid, crowds_model.CROWDS_WORLD_KEY, []) or []:
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
    index = _cast_index(cid, frame_id, scene)
    crowd_index = _crowd_index(cid, scene, frame_id)
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
        entry = index[key]
        set_char_state(cid, entry["row"]["id"],
                       json.dumps(state, ensure_ascii=False),
                       frame_id=frame_id)
    if crowds_dirty:
        from db import wget, wset

        standing = [dict(c) for c in wget(cid, crowds_model.CROWDS_WORLD_KEY, [])
                    or [] if isinstance(c, dict)]
        for i, crowd in enumerate(standing):
            replacement = crowds_dirty.get(str(crowd.get("uid") or "").casefold())
            if replacement is not None:
                standing[i] = replacement
        wset(cid, crowds_model.CROWDS_WORLD_KEY, standing)
    return applied, rejected
