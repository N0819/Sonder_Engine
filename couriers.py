"""Couriers: a message with a body, somewhere specific, that can be stopped.

The carrier network's last unbuilt leg. `carriers.py` moves a report because
its HOLDER walks and `crowds.py` moves talk because the CROWD walks; both are
people who happen to know things. A courier is the missing third kind: a body
whose whole purpose is the message, dispatched from one place toward another
along a route -- which is the shape the design commits to verbatim (§9.1):
"simulated info routes a player could potentially intercept". An antagonist is
a source, never a broadcast; money buys more riders and better roads, never
teleportation.

The constraint that shaped every field here: **a `due_seconds` fuse wearing a
courier's name would be a timer in a costume.** So a courier is never "in
transit" -- it is IN A ROOM, one of the rooms on a route computed at dispatch
over `spatial.passable_path`, the same graph every other body walks (no second
pathfinder). It advances on the simulation clock, one passable edge per
`pace_seconds`, which is what makes every verb in the design real rather than
narrated: you INTERCEPT it by standing in a room it is in, FOLLOW it because it
is always somewhere, OUTRUN it because its pace is slower than yours, QUESTION
it because it is a body that can be made to talk, and SILENCE it because a
stopped body delivers nothing. A silenced courier's message does not arrive.
That is the whole point of a route existing.

THE ENVELOPE IS carriers.py's, UNCHANGED. A courier moves the same report
shape (`world_event_id`, `claim`, `retellings`, `told_by`, `provenance`) that
tellings copy and crowds murmur, and it degrades through `degradation.py` the
same stepwise-safe way. Two methods differ only in whether handing over is a
retelling:

- **word**: the rider memorized it. Dispatch is one retelling (the sender told
  the rider) and delivery is another (the rider tells the recipient), so news
  by mouth arrives two mouths fainter -- and a story with nothing left to lose
  is refused a rider at all (`degradation.is_exhausted`).
- **letter**: sealed writing is not retold, so it crosses any distance
  verbatim (the module note in carriers.py already argues this: "a sealed
  letter carried a thousand miles arrives verbatim"). What it carries is
  whatever its SENDER held -- a letter written from a rumor is a verbatim copy
  of the rumor, not of the truth.

A courier is ANONYMOUS like a crowd: keyed by an engine-minted uid, never a
display name, and attributed as what it is ("a rider") -- minting it into the
character name space is the five-ledger defect crowds.py is written around.
Emergence into a real character is deliberately not built: question a rider
and you learn the message, not a person.

A CARAVAN IS THE SAME BODY WITH A DIFFERENT RELATION TO NEWS. Structurally it
is a `kind` on the courier object plus a stop list -- same route machinery,
same clock, same interception ops, same perception surface -- because a
parallel implementation would be two spellings of one thing. What differs is
in kind, not in route length: a courier is PAID to move one message and does
nothing else, while a caravan moves for its own reasons and news merely rides
along. So a caravan DWELLS at each stop (the halt is charged in simulation
time, like every other delay here -- never a due-date), and at a stop it
trades news both ways: it tells the standing crowd what it carries, and it
picks up what is standing in the room -- the crowd's talk, the public
surfaces still legible there, the notices on the post -- each through the
same degradation physics as everything else. A caravan that only delivered
would be a courier with extra hops, which is exactly the cheap version the
design deferred rather than build.

The market is the caravan's mouth and ear on purpose. At an intermediate
stop it exchanges news with the CROWD only, never room-to-room with every
registered mind standing there: a trader dwelling in a square talks to the
square, and a body who wants what the square heard has the two doors that
already exist -- the crowd's overheard `talk`, and an explicit telling. An
empty square teaches a caravan nothing and learns nothing from it, and both
of those are correct.

Pure functions where possible (dicts in, dicts out); the parts that must read
the cast or write state sit at the bottom, mirroring carriers.py, and run
inside the same `information_carriers` commit domain so a rollback un-sends
the rider. Persistence is the frame-scoped world key below, which is what
makes a branch that never dispatched a rider free of him, and a rewind put
him back on the road.
"""

from __future__ import annotations

import hashlib
import json

import crowds as crowds_model
import degradation
from carriers import (REPORT_CAP, STATE_KEY, TELL_FANOUT_CAP, _cast_index,
                      save_state)


#: The world-KV key couriers live under, spelled once, frame-scoped in
#: `db.FRAME_SCOPED_WORLD_KEYS`: a rider on the road is era state exactly like
#: the scene he rides through.
COURIERS_WORLD_KEY = "couriers"

#: How many couriers may be on the road (or waiting) at once. Bounded route
#: fan-out is a design requirement, not tidiness: past this the map is a
#: postal service, and "money buys more carriers" must mean these slots fill,
#: never that the cap moves.
MAX_COURIERS = 6

#: How long the search for a route may look. Wider than passable_path's
#: default 12 because a courier's whole job is distance; still bounded,
#: because a route past thirty rooms is a journey the story should stage,
#: not a dispatch.
ROUTE_LIMIT = 32

#: Simulation seconds to cross one passable edge, by how the courier travels.
#: Coarse on purpose (this is "does a rider cross a room in minutes or in an
#: hour", not gait simulation), and BOTH are slower than a walking player,
#: who crosses a room in one beat: outrunning a route is a verb the design
#: promises the player, so the fastest thing on the road must not be the
#: courier. The rider is the reach money buys; the runner is what a village
#: sends.
PACES = {"riding": 240.0, "walking": 600.0}
DEFAULT_PACE = "riding"

#: The two kinds of body on the road. One object, one list, one sweep --
#: the kind decides only whether there are stops to dwell at and whether
#: news is traded on the way.
KIND_COURIER = "courier"
KIND_CARAVAN = "caravan"

#: How long a caravan halts at each intermediate stop, in simulation
#: seconds. Half an hour: long enough that a walking player who saw it
#: arrive can reach the same market before it leaves -- "ridden with,
#: robbed, or beaten there" all require the halt to be real -- and short
#: enough that a day's time-skip still crosses several stops. Charged
#: against the same clock as the paces, so a dwell is a delay the route
#: causes, never a configured due-date.
DWELL_SECONDS = 1800.0

#: How many intermediate stops one caravan may string together. Past this
#: the route is a trade network, and a trade network is many caravans.
MAX_STOPS = 3

#: How many reports one caravan carries. It is a trader's ear for news, not
#: an archive: the oldest talk stops being repeated, exactly as a crowd's
#: does (`crowds.CROWD_REPORT_CAP` is the precedent and the same number).
CARAVAN_CARGO_CAP = 4

#: Statuses. `en_route` and `arrived` are the live ones (visible, movable,
#: interceptable); everything else is a record of how the route ended.
EN_ROUTE = "en_route"
ARRIVED = "arrived"        # standing at the destination, delivery not yet made
DELIVERED = "delivered"
SILENCED = "silenced"
_LIVE = (EN_ROUTE, ARRIVED)

#: How many finished routes to keep as a record beside the live ones. The
#: list is a road, not an archive.
_FINISHED_KEPT = 6

OP_SEND = "send"
OP_QUESTION = "question"
OP_SILENCE = "silence"
_OPS = (OP_SEND, OP_QUESTION, OP_SILENCE)


def courier_uid(chat_id, origin, destination, turn, description, stops=()):
    """A stable id minted once, from what the courier IS. Never a name.

    Stops join the material only when there are any, so every courier uid
    minted before caravans existed still resolves to the same digest.
    """
    material = "|".join([
        str(int(chat_id)), str(origin or ""), str(destination or ""),
        str(int(turn)),
        " ".join(str(description or "").split()).casefold(),
    ])
    if stops:
        material += "|" + "|".join(str(s) for s in stops)
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
    return "courier:%s" % digest


def courier_voice(courier):
    """How a delivered report is attributed. NEVER a name.

    "a rider" is a source a mind can weigh -- obviously a messenger, obviously
    somebody who could have been stopped on the road. The same rule as
    `crowds.crowd_voice`, for the same reason: naming him would mint a
    stranger into the character key space nobody interacted with.
    """
    if not isinstance(courier, dict):
        return "a messenger"
    return str(courier.get("description") or "").strip() or "a messenger"


def live_couriers(couriers):
    return [c for c in (couriers or [])
            if isinstance(c, dict) and c.get("status") in _LIVE]


def couriers_in_room(couriers, room_uid):
    """Live couriers standing in one room, in a stable order."""
    room = str(room_uid or "")
    if not room:
        return []
    return sorted(
        (c for c in live_couriers(couriers)
         if str(c.get("at") or "") == room),
        key=lambda c: str(c.get("uid") or ""))


def passed_through(couriers, room_uid):
    """Live couriers that crossed this room during THIS beat's sweep and kept
    going -- the glimpse of a rider passing, which is what makes a route
    followable rather than a thing that teleports between sightings."""
    room = str(room_uid or "")
    if not room:
        return []
    return sorted(
        (c for c in live_couriers(couriers)
         if room in (c.get("passed") or []) and str(c.get("at")) != room),
        key=lambda c: str(c.get("uid") or ""))


def _pace_seconds(pace):
    return PACES.get(
        " ".join(str(pace or "").split()).casefold(), PACES[DEFAULT_PACE])


def new_courier(chat_id, *, origin, destination, route, turn, clock_seconds,
                description, report, sealed, pace, kind=KIND_COURIER,
                stops=(), stop_legs=()):
    """One courier, standing in the origin room with the message in hand.

    `route` is every room from origin to destination INCLUSIVE; `at` is
    always `route[leg]`, which is the invariant the whole module rides on: a
    courier has a position, not an ETA.

    A caravan is the same dict with `kind`, its stop rooms, the route legs
    those stops sit at, and a `cargo` LIST in place of the single `report`:
    a courier's whole purpose is one message, a caravan's news is whatever
    it has picked up so far. The dispatched report (if any) is simply the
    first thing in the wagon.
    """
    caravan = str(kind or KIND_COURIER) == KIND_CARAVAN
    out = {
        "uid": courier_uid(chat_id, origin, destination, turn, description,
                           stops=stops),
        "description": " ".join(str(description or "").split())[:80]
                       or ("a trader's caravan" if caravan
                           else "a rider" if _pace_seconds(pace) <= PACES["riding"]
                           else "a messenger on foot"),
        "origin": str(origin), "destination": str(destination),
        "route": [str(r) for r in route],
        "leg": 0, "at": str(origin),
        "status": EN_ROUTE if len(route) > 1 else ARRIVED,
        "dispatched_turn": int(turn),
        "moved_at": float(clock_seconds),
        "pace_seconds": _pace_seconds(pace),
        "sealed": bool(sealed),
        "passed": [],
    }
    if caravan:
        out["kind"] = KIND_CARAVAN
        out["stops"] = [str(s) for s in stops]
        out["stop_legs"] = sorted(int(x) for x in stop_legs)
        out["exchanged_legs"] = []
        out["stops_due"] = []
        cargo = dict(report or {})
        if cargo:
            cargo["sealed"] = bool(sealed)
        out["cargo"] = [cargo] if cargo else []
    else:
        out["report"] = dict(report or {})
    return out


def carried_bundle(courier):
    """Everything this body carries, as ``(report, sealed)`` pairs.

    The one accessor both kinds answer, so delivery, questioning and seizure
    never fork on `kind`: a courier is a bundle of exactly one.
    """
    if courier.get("kind") == KIND_CARAVAN:
        return [(r, bool(r.get("sealed"))) for r in courier.get("cargo") or []
                if isinstance(r, dict) and r.get("claim")]
    held = courier.get("report") or {}
    return [(held, bool(courier.get("sealed")))] if held.get("claim") else []


def advance_couriers(couriers, neighbors, clock_seconds):
    """Move every en-route courier as far as the clock has paid for. Pure;
    returns ``(couriers, moves)``.

    One passable edge per `pace_seconds` of simulation time, with the
    remainder carried (`moved_at` steps by pace, never jumps to now), so a
    long time-skip covers many rooms and a short beat covers none -- the
    delay is a consequence of the route, never a configured due-date.

    Each step re-checks the edge against `neighbors` (the same
    `passable_neighbors` graph everyone walks): a door that closed since
    dispatch HOLDS the courier where he is, this sweep and every sweep until
    it opens. A held rider is not rerouted -- re-planning would be the second
    pathfinder the crowd proposal forbids, and a man stopped at a shut gate
    is somewhere specific, which is exactly what makes him catchable.

    `passed` records the rooms crossed THIS sweep and is reset first: it is
    perception's one-beat glimpse of a rider going through, never a trail.

    A caravan additionally DWELLS: stepping onto one of its stop legs
    charges `DWELL_SECONDS` against `moved_at` on top of the pace, so the
    next edge is not paid for until the halt has genuinely elapsed -- the
    same arithmetic that keeps a short beat from moving a rider keeps a
    caravan standing in the market, visible and robbable, until the clock
    says it left. Each stop reached is appended to `stops_due` for the
    exchange sweep (`run_couriers` clears it in the same transaction); a
    long time-skip that carries the wagon through a stop and out the other
    side still owes that stop its exchange, because the halt happened in
    story time whether or not any beat watched it.
    """
    out = []
    moves = []
    try:
        now = float(clock_seconds)
    except (TypeError, ValueError):
        now = 0.0
    for courier in (couriers or []):
        if not isinstance(courier, dict):
            continue
        courier = dict(courier)
        if courier.get("status") != EN_ROUTE:
            courier["passed"] = []
            out.append(courier)
            continue
        route = [str(r) for r in courier.get("route") or []]
        leg = max(0, int(courier.get("leg") or 0))
        pace = float(courier.get("pace_seconds") or PACES[DEFAULT_PACE])
        moved_at = float(courier.get("moved_at") or 0.0)
        stop_legs = {int(x) for x in courier.get("stop_legs") or []}
        stops_due = [int(x) for x in courier.get("stops_due") or []]
        passed = []
        while leg + 1 < len(route) and now - moved_at >= pace:
            nxt = route[leg + 1]
            here = route[leg]
            if nxt not in (neighbors.get(here) or ()):
                break
            passed.append(here)
            leg += 1
            moved_at += pace
            moves.append({"uid": courier.get("uid"), "from": here, "to": nxt})
            if leg in stop_legs and leg + 1 < len(route):
                if leg not in stops_due:
                    stops_due.append(leg)
                moved_at += DWELL_SECONDS
        courier["leg"] = leg
        if stop_legs:
            courier["stops_due"] = stops_due
        courier["at"] = route[leg] if route else str(courier.get("at") or "")
        courier["moved_at"] = moved_at
        # Every room he LEFT this sweep, including the one he stood in when
        # the beat began -- a body there watched him go, and that glimpse is
        # what makes the route followable. Never the room he now stands in;
        # there he is simply present.
        courier["passed"] = passed
        if route and leg == len(route) - 1:
            courier["status"] = ARRIVED
        out.append(courier)
    return out, moves


def _copy_of(courier, held, sealed, listener_room, turn):
    """The listener's copy of one report this courier carries, one handover
    on.

    Word of mouth is a retelling and degrades exactly as `apply_tellings`
    degrades (stepwise-safe: the stored claim is already what the RIDER
    heard); a sealed letter is not retold and crosses verbatim. Returns
    ``None`` when a spoken story has nothing left -- it arrived, and there
    was nothing worth repeating in it.
    """
    held = held or {}
    if sealed:
        retellings = max(0, int(held.get("retellings") or 0))
        claim = " ".join(str(held.get("claim") or "").split())
        provenance = "letter"
    else:
        retellings = max(0, int(held.get("retellings") or 0)) + 1
        if degradation.is_exhausted(retellings):
            return None
        claim = degradation.degrade(
            held.get("claim"), retellings,
            names=courier.get("_names") or (),
            places=courier.get("_places") or ())
        provenance = "told"
    return {
        "world_event_id": str(held.get("world_event_id") or ""),
        "source_event_id": str(held.get("source_event_id") or ""),
        "claim": claim,
        "kind": str(held.get("kind") or ""),
        "occurred_at": float(held.get("occurred_at") or 0.0),
        "acquired_turn": int(turn),
        "acquired_location": str(listener_room or ""),
        "current_location": str(listener_room or ""),
        "route": [str(listener_room or "")],
        "hops": 0,
        "retellings": retellings,
        "told_by": courier_voice(courier),
        "provenance": provenance,
    }


# --------------------------------------------------------------------------
# The impure half: reads the cast and crowds, writes state. Mirrors
# carriers.py and runs inside the same commit domain and transaction.
# --------------------------------------------------------------------------


def _hold_report(entry, event_id):
    """The report this cast entry holds under this id, or None."""
    state = entry.get("state") or {}
    for report in state.get(STATE_KEY) or []:
        if isinstance(report, dict) \
                and str(report.get("world_event_id")) == str(event_id):
            return report
    return None


def _give_report(cid, frame_id, entry, copy):
    """Append a report copy to one carrier's held state, player included."""
    state = entry.get("state") or {}
    reports = [dict(r) for r in state.get(STATE_KEY) or []
               if isinstance(r, dict)]
    if any(str(r.get("world_event_id")) == str(copy.get("world_event_id"))
           for r in reports):
        return False
    reports.append(copy)
    state[STATE_KEY] = reports[-REPORT_CAP:]
    entry["state"] = state
    save_state(cid, entry, state, frame_id=frame_id)
    return True


def _player_name(ctx):
    """The persona's name, so the PLAYER can stop a rider.

    `persona_of` accepts anything with ``.get`` (ChatData, dict, Row-shaped
    test doubles). A chat object without one -- bare test namespaces -- means
    no resolvable persona, and then only registered characters can interfere;
    failing toward fewer interferers is the safe direction.
    """
    from scene import persona_of

    chat = ctx.chat
    if not hasattr(chat, "get"):
        try:
            chat = {"persona_id": getattr(chat, "persona_id")}
        except AttributeError:
            return ""
    try:
        persona = persona_of(chat) or {}
    except (TypeError, KeyError):
        persona = {}
    # `persona_of` normalizes to the character shape: the name lives under
    # `identity`, and reading the top level silently made every player
    # nameless -- and a nameless player can never stop a rider.
    identity = persona.get("identity") if isinstance(persona, dict) else {}
    name = (identity or {}).get("name") or persona.get("name") or ""
    return str(name).strip()


def _deliver(ctx, scene, courier, index, crowds_standing, *, turn):
    """Hand an arrived courier's message to whoever it was for. Returns
    ``(courier, delivered_to, crowds_dirty)``.

    An addressee gets it only in person -- a courier for someone absent
    STANDS at the destination holding it, visible and interceptable, until
    they show; that wait is not a failure state, it is a man at a gate.
    A courier to a PLACE tells the place: the crowd standing there first
    (news called across a square), else the few bodies present, under the
    same fan-out cap one speaker gets. Nothing present means he waits.

    A caravan delivers its whole wagon the same way, one report at a time
    through the same copies -- and a caravan that gathered nothing on the
    road simply ends its route, which is a trader arriving with goods and
    no news, not a failure.
    """
    delivered_to = []
    crowds_dirty = False
    room = str(courier.get("at") or "")
    addressee = str(courier.get("addressee") or "").strip().casefold()
    copies = [c for c in (_copy_of(courier, held, sealed, room, turn)
                          for held, sealed in carried_bundle(courier))
              if c is not None]

    if addressee:
        entry = index.get(addressee)
        if entry is None or entry.get("room") != room:
            return courier, delivered_to, crowds_dirty
        for copy in copies:
            if _give_report(ctx.chat.id, ctx.turn.frame_id, entry, copy):
                if entry["name"] not in delivered_to:
                    delivered_to.append(entry["name"])
        courier = dict(courier)
        courier["status"] = DELIVERED
        courier["delivered_turn"] = int(turn)
        return courier, delivered_to, crowds_dirty

    for i, crowd in enumerate(crowds_standing):
        if str(crowd.get("room_uid") or "") != room:
            continue
        for copy in copies:
            updated = crowds_model.add_hearsay(crowd, copy)
            if updated is not crowd:
                crowds_standing[i] = crowd = updated
                crowds_dirty = True
                if crowds_model.crowd_voice(crowd) not in delivered_to:
                    delivered_to.append(crowds_model.crowd_voice(crowd))
        break
    if not delivered_to:
        told = 0
        for key in sorted(index):
            entry = index[key]
            if entry.get("room") != room or told >= TELL_FANOUT_CAP:
                continue
            if entry.get("name") in delivered_to:
                continue
            given = False
            for copy in copies:
                if _give_report(ctx.chat.id, ctx.turn.frame_id, entry,
                                dict(copy)):
                    given = True
            if given:
                delivered_to.append(entry["name"])
                told += 1
    if delivered_to or not copies:
        # Nothing left worth repeating (or an empty wagon) still ends the
        # route: he arrived, and arriving is the end of a road.
        courier = dict(courier)
        courier["status"] = DELIVERED
        courier["delivered_turn"] = int(turn)
    return courier, delivered_to, crowds_dirty


def _exchange_stops(ctx, couriers, crowds_standing, *, names, places, turn,
                    metrics):
    """Trade news at every stop a caravan reached. Returns crowds-dirty.

    This is the half that makes a caravan a caravan rather than a courier
    with extra hops. At each due stop, in one pass:

    **It tells the square.** Every unsealed report in the wagon goes into
    the crowd standing there, one retelling on (the trader's mouth), through
    the same degradation as any telling -- and only into the CROWD. A
    registered mind in the market learns through the doors that already
    exist (the crowd's overheard talk, an explicit telling), because a
    caravan that briefed every body in every market it crossed would be a
    broadcast wearing wheels.

    **It listens.** What is standing in the room enters the wagon: the
    crowd's talk one retelling on (the crowd told the trader), the public
    witnessed surfaces still legible there at zero retellings (the trader
    SAW the barred gate, and an eyewitness has been told nothing), and any
    posted artifact's claim verbatim at its posted count (reading is a copy,
    not a mouth -- and a bill torn down before the caravan rolled in teaches
    it nothing, which is the artifact equivalent of silencing a rider
    working exactly as intended).

    Exhausted stories neither board nor leave the wagon; the cargo cap
    drops the oldest first. A long time-skip that swept the caravan through
    a stop exchanges against the room AS IT NOW STANDS -- the same
    approximation the arrival-surfaces window already makes for a walking
    body, and the honest one available without replaying history.
    """
    from db import q

    cid = ctx.chat.id
    crowds_dirty = False
    standing_surfaces = None  # lazily loaded once; most beats have no stops

    def surfaces():
        nonlocal standing_surfaces
        if standing_surfaces is None:
            from carriers import ARRIVAL_SURFACES

            standing_surfaces = []
            for row in q(
                    "SELECT * FROM world_events WHERE chat_id=? AND "
                    "frame_id IS ? AND location_id IS NOT NULL "
                    "ORDER BY occurred_at DESC LIMIT ?",
                    (cid, ctx.turn.frame_id, ARRIVAL_SURFACES * 4)) or []:
                try:
                    payload = json.loads(row["payload"] or "{}")
                except (TypeError, ValueError):
                    payload = {}
                witnessed = " ".join(
                    str((payload or {}).get("witnessed") or "").split())
                if witnessed:
                    standing_surfaces.append(
                        (dict(row), payload, witnessed[:320]))
        return standing_surfaces

    for i, courier in enumerate(couriers):
        if courier.get("kind") != KIND_CARAVAN \
                or courier.get("status") not in _LIVE:
            continue
        due = [int(x) for x in courier.get("stops_due") or []]
        if not due:
            continue
        courier = dict(courier)
        route = [str(r) for r in courier.get("route") or []]
        cargo = [dict(r) for r in courier.get("cargo") or []
                 if isinstance(r, dict)]
        exchanged = [int(x) for x in courier.get("exchanged_legs") or []]
        for leg in due:
            if leg in exchanged or not (0 <= leg < len(route)):
                continue
            room = route[leg]
            metrics["caravan_stops"] += 1
            known = {str(r.get("world_event_id")) for r in cargo}

            crowd_here = None
            for ci, crowd in enumerate(crowds_standing):
                if str(crowd.get("room_uid") or "") == room:
                    crowd_here = ci
                    break

            # Tell the square first, listen second -- a trader calls his
            # news across the market and then stays for what comes back.
            if crowd_here is not None:
                for held in cargo:
                    if held.get("sealed"):
                        continue
                    retellings = max(0, int(held.get("retellings") or 0)) + 1
                    if degradation.is_exhausted(retellings):
                        continue
                    crowd = crowds_standing[crowd_here]
                    updated = crowds_model.add_hearsay(crowd, {
                        "world_event_id": str(held.get("world_event_id") or ""),
                        "source_event_id": str(held.get("source_event_id") or ""),
                        "claim": degradation.degrade(
                            held.get("claim"), retellings,
                            names=names, places=places),
                        "kind": str(held.get("kind") or ""),
                        "occurred_at": float(held.get("occurred_at") or 0.0),
                        "acquired_turn": int(turn),
                        "retellings": retellings,
                        "told_by": courier_voice(courier),
                        "provenance": "told",
                    })
                    if updated is not crowd:
                        crowds_standing[crowd_here] = updated
                        crowds_dirty = True
                        metrics["caravan_put_down"] += 1

            # Listening order is an epistemic ranking, not happenstance:
            # what the trader can SEE (a standing surface, a posted bill)
            # boards before what the crowd merely says, so when both carry
            # one event the wagon holds the eyewitness version and the
            # dedupe drops the fainter hearsay -- never the reverse.
            for row, payload, witnessed in surfaces():
                if str(row["location_id"]) != room \
                        or str(row["event_id"]) in known:
                    continue
                cargo.append({
                    "world_event_id": str(row["event_id"]),
                    "source_event_id": str(payload.get("source_event_id") or ""),
                    "claim": witnessed,
                    "kind": str(row["kind"]),
                    "occurred_at": float(row["occurred_at"]),
                    "acquired_turn": int(turn),
                    "acquired_location": room,
                    "current_location": room,
                    "retellings": 0,
                    "told_by": "",
                    "provenance": "witnessed_surface",
                    "sealed": False,
                })
                known.add(str(row["event_id"]))
                metrics["caravan_picked_up"] += 1

            try:
                import artifacts as artifacts_model

                posted = artifacts_model.posted_in_room(
                    artifacts_model.standing_artifacts(cid), room)
            except Exception:
                posted = []
            for artifact in posted:
                held = artifact.get("report") or {}
                event_id = str(held.get("world_event_id") or "")
                if not event_id or event_id in known \
                        or not str(held.get("claim") or "").strip():
                    continue
                cargo.append({
                    "world_event_id": event_id,
                    "source_event_id": str(held.get("source_event_id") or ""),
                    "claim": " ".join(str(held.get("claim") or "").split()),
                    "kind": str(held.get("kind") or ""),
                    "occurred_at": float(held.get("occurred_at") or 0.0),
                    "acquired_turn": int(turn),
                    "acquired_location": room,
                    "current_location": room,
                    "retellings": max(0, int(held.get("retellings") or 0)),
                    "told_by": artifacts_model.artifact_voice(artifact),
                    "provenance": "read",
                    "sealed": False,
                })
                known.add(event_id)
                metrics["caravan_picked_up"] += 1

            if crowd_here is not None:
                for heard in crowds_model.crowd_hearsay(
                        crowds_standing[crowd_here]):
                    event_id = str(heard.get("world_event_id") or "")
                    if not event_id or event_id in known:
                        continue
                    retellings = max(0, int(heard.get("retellings") or 0)) + 1
                    if degradation.is_exhausted(retellings):
                        continue
                    cargo.append({
                        "world_event_id": event_id,
                        "source_event_id": str(heard.get("source_event_id") or ""),
                        "claim": degradation.degrade(
                            heard.get("claim"), retellings,
                            names=names, places=places),
                        "kind": str(heard.get("kind") or ""),
                        "occurred_at": float(heard.get("occurred_at") or 0.0),
                        "acquired_turn": int(turn),
                        "acquired_location": room,
                        "current_location": room,
                        "retellings": retellings,
                        "told_by": crowds_model.crowd_voice(
                            crowds_standing[crowd_here]),
                        "provenance": "told",
                        "sealed": False,
                    })
                    known.add(event_id)
                    metrics["caravan_picked_up"] += 1

            exchanged.append(leg)

        # The cap forgets the oldest TALK first and never a sealed letter:
        # gathered news is what people are saying, a paid dispatch is a
        # thing in the wagon, and a full wagon must not quietly shed the
        # one item somebody bought the route for.
        letters = [r for r in cargo if r.get("sealed")]
        talk = [r for r in cargo if not r.get("sealed")]
        kept = max(0, CARAVAN_CARGO_CAP - len(letters))
        courier["cargo"] = letters + talk[-kept:]
        courier["exchanged_legs"] = exchanged
        courier["stops_due"] = []
        couriers[i] = courier
    return crowds_dirty


def run_couriers(ctx, scene, ops, *, names=(), places=()):
    """Apply this beat's courier ops, then move the road on the clock.

    Ops FIRST, against positions as this beat perceived them -- a rider the
    player cornered must still be there for the `silence` that resolves the
    cornering -- then the sweep spends the elapsed time, so a courier sent
    this beat is SEEN leaving before he has gone anywhere (the crowd
    heading-lives-one-beat lesson, inverted to fit a body with a position).
    Deliveries run last, inside the same turn transaction: a delivery that
    survived a rolled-back dispatch would be a mind holding a report of an
    event that never happened.

    Every refusal is deterministic and mirrors `apply_tellings`' physics:
    the sender must be registered and must HOLD the report (or be inventing
    a claim, which lands on their own row as `invented` exactly as a spoken
    lie does); the courier departs from the room the sender's body is in,
    along a route `spatial.passable_path` can actually walk; and nobody
    interferes with a courier from a room he is not in.
    """
    from db import wget, wset
    from spatial import passable_neighbors, passable_path, room_of

    cid = ctx.chat.id
    frame_id = ctx.turn.frame_id
    turn = int(ctx.turn.idx)
    clock = wget(cid, "simulation_clock", {}) or {}
    try:
        now = float(clock.get("elapsed_seconds") or 0.0)
    except (TypeError, ValueError):
        now = 0.0

    couriers = [dict(c) for c in wget(cid, COURIERS_WORLD_KEY, []) or []
                if isinstance(c, dict)]
    before = json.dumps(couriers, sort_keys=True, ensure_ascii=False)
    index = _cast_index(cid, frame_id, scene, chat=getattr(ctx, "chat", None))
    by_uid = {str(c.get("uid") or ""): c for c in couriers}
    rejected = []
    metrics = {"couriers_offered": 0, "dispatched": 0, "courier_moves": 0,
               "courier_delivered": 0, "courier_questioned": 0,
               "courier_silenced": 0, "couriers_standing": 0,
               "caravan_stops": 0, "caravan_put_down": 0,
               "caravan_picked_up": 0}

    player = _player_name(ctx)

    def interferer_room(name):
        """Where the named interferer's body is, or "" for nobody real.

        Registered characters and the player may act on a courier; both
        have bodies with rooms. A name the story does not know cannot stop
        a rider, because there is no body to stand in his way.
        """
        key = str(name or "").strip().casefold()
        if not key:
            return ""
        entry = index.get(key)
        if entry is not None:
            return str(entry.get("room") or "")
        if player and key == player.casefold():
            return str(room_of(scene, player) or "")
        return ""

    ops = [op.dict() if hasattr(op, "dict") else op for op in (ops or [])]
    for raw in ops:
        if not isinstance(raw, dict):
            rejected.append("courier op was not an object")
            continue
        metrics["couriers_offered"] += 1
        op = " ".join(str(raw.get("op") or OP_SEND).split()).casefold()
        if op not in _OPS:
            rejected.append("unknown courier op %r" % (raw.get("op"),))
            continue

        if op == OP_SEND:
            rooms = scene.get("rooms") or {}
            stops = [str(s).strip() for s in (raw.get("stops") or [])
                     if str(s or "").strip()]
            caravan = bool(stops)
            destination = str(raw.get("to_room") or "").strip()
            sender_key = str(raw.get("sender") or "").strip().casefold()
            sender = index.get(sender_key)
            event_id = str(raw.get("world_event_id") or "").strip()
            carries_message = bool(event_id
                                   or str(raw.get("claim") or "").strip())
            if caravan and len(stops) > MAX_STOPS:
                rejected.append(
                    "%d stops is a trade network, not a caravan; %d at most"
                    % (len(stops), MAX_STOPS))
                continue
            if caravan and len(set(stops)) != len(stops):
                rejected.append("a caravan does not stop twice at one place "
                                "on one route")
                continue
            unknown = [s for s in stops if s not in rooms]
            if unknown:
                rejected.append("caravan stop %r is not a room the scene "
                                "knows" % unknown[0])
                continue
            if carries_message or sender_key:
                # A message starts in somebody's hands, and so does a
                # caravan somebody pays for: the sender's body fixes the
                # origin, exactly as for a rider.
                if sender is None:
                    rejected.append(
                        "courier sender %r is not a registered character; a "
                        "message starts in somebody's hands"
                        % (raw.get("sender"),))
                    continue
                origin = str(sender.get("room") or "")
                if not origin:
                    rejected.append("%s is nowhere the scene can place; no "
                                    "courier departs from an unknown room"
                                    % sender["name"])
                    continue
            else:
                # An EMPTY caravan is world texture like a crowd: it forms
                # in a named, known room (the crowd-minting precedent) and
                # carries nothing until the road gives it something. A
                # courier with no message is nobody -- refused.
                if not caravan:
                    rejected.append("a courier with nothing to carry is not "
                                    "a courier; give him a report or a claim")
                    continue
                origin = str(raw.get("from_room") or "").strip()
                if origin not in rooms:
                    rejected.append(
                        "a caravan with no sender forms in a known room; "
                        "%r is not one" % (raw.get("from_room"),))
                    continue
            if destination not in rooms:
                rejected.append("courier bound for unknown room %r"
                                % destination)
                continue
            if destination == origin:
                rejected.append("a courier to the room the sender stands in "
                                "is a telling, not a route")
                continue
            if origin in stops or destination in stops:
                rejected.append("a stop that repeats the origin or the "
                                "destination is not a stop")
                continue
            if len(live_couriers(couriers)) >= MAX_COURIERS:
                rejected.append("%d couriers are already on the road; no "
                                "more until one arrives or is stopped"
                                % MAX_COURIERS)
                continue
            held = None
            if carries_message:
                held = _hold_report(sender, event_id) if event_id else None
                if held is None and not event_id \
                        and str(raw.get("claim") or "").strip():
                    from carriers import _invented_claim

                    invented = _invented_claim(raw.get("claim"), ctx, sender)
                    state = sender.get("state") or {}
                    state[STATE_KEY] = (
                        [dict(r) for r in state.get(STATE_KEY) or []
                         if isinstance(r, dict)] + [invented])[-REPORT_CAP:]
                    save_state(cid, sender, state, frame_id=frame_id)
                    sender["state"] = state
                    held = invented
                if held is None:
                    rejected.append(
                        "%s does not carry %r and cannot send it anywhere"
                        % (sender["name"], event_id or "that report"))
                    continue
            sealed = " ".join(str(raw.get("method") or "").split()) \
                .casefold() == "letter"
            if held is not None and not sealed and degradation.is_exhausted(
                    max(0, int(held.get("retellings") or 0)) + 1):
                rejected.append(
                    "that story has lost its count, its place and its name; "
                    "no rider carries it further")
                continue
            route = [origin]
            stop_legs = []
            here = origin
            for target in stops + [destination]:
                seg = passable_path(scene, here, target, limit=ROUTE_LIMIT)
                if not seg:
                    route = None
                    rejected.append(
                        "no passable route from %s to %s; a courier walks "
                        "the same doors everyone else does" % (here, target))
                    break
                route += seg
                if target != destination:
                    stop_legs.append(len(route) - 1)
                here = target
            if route is None:
                continue
            envelope = dict(held) if held is not None else {}
            if envelope and not sealed:
                retellings = max(0, int(held.get("retellings") or 0)) + 1
                envelope["retellings"] = retellings
                envelope["claim"] = degradation.degrade(
                    held.get("claim"), retellings, names=names, places=places)
                envelope["told_by"] = sender["name"]
                envelope["provenance"] = "told"
            courier = new_courier(
                cid, origin=origin, destination=destination,
                route=route, turn=turn, clock_seconds=now,
                description=raw.get("description"), report=envelope,
                sealed=sealed,
                pace=raw.get("pace") or ("walking" if caravan
                                         else DEFAULT_PACE),
                kind=KIND_CARAVAN if caravan else KIND_COURIER,
                stops=stops, stop_legs=stop_legs)
            courier["addressee"] = " ".join(
                str(raw.get("addressee") or "").split())
            if courier["uid"] in by_uid:
                rejected.append("that courier is already on the road")
                continue
            couriers.append(courier)
            by_uid[courier["uid"]] = courier
            metrics["dispatched"] += 1
            continue

        uid = str(raw.get("courier_id") or "").strip()
        courier = by_uid.get(uid)
        if courier is None or courier.get("status") not in _LIVE:
            rejected.append("no courier %r on the road; the engine mints "
                            "these ids and perception shows them" % uid)
            continue

        if op == OP_QUESTION:
            listener_key = str(raw.get("listener") or "").strip().casefold()
            listener = index.get(listener_key)
            listener_room = interferer_room(raw.get("listener"))
            if not listener_room:
                rejected.append("courier questioned by %r, whom the story "
                                "does not know" % (raw.get("listener"),))
                continue
            if listener_room != str(courier.get("at") or ""):
                rejected.append(
                    "%s is not where the %s is; a rider is questioned on "
                    "the road he is on"
                    % (raw.get("listener"), courier_voice(courier)))
                continue
            bundle = carried_bundle(courier)
            spoken = [(held, sealed) for held, sealed in bundle if not sealed]
            if bundle and not spoken:
                rejected.append(
                    "the message is sealed and the %s does not know what it "
                    "says; take it from him instead" % courier_voice(courier))
                continue
            # A transient probe, so the redaction rosters never persist onto
            # the stored courier row.
            probe = dict(courier)
            probe["_names"], probe["_places"] = list(names), list(places)
            copies = [c for c in (_copy_of(probe, held, sealed,
                                           listener_room, turn)
                                  for held, sealed in spoken)
                      if c is not None]
            if not copies:
                rejected.append("the %s's story has nothing left in it"
                                % courier_voice(courier))
                continue
            if listener is not None:
                given = False
                for copy in copies:
                    if _give_report(cid, frame_id, listener, copy):
                        given = True
                if given:
                    metrics["courier_questioned"] += 1
            elif player and listener_key == player.casefold():
                # The player's own knowledge is the transcript; perception
                # narrates what the rider says. The stopping is still real:
                # the count records that the road was made to talk.
                metrics["courier_questioned"] += 1
            continue

        if op == OP_SILENCE:
            by = raw.get("by")
            by_room = interferer_room(by)
            if not by_room:
                rejected.append(
                    "a courier is silenced by somebody, somewhere; %r is "
                    "not a body the story can place" % (by,))
                continue
            if by_room != str(courier.get("at") or ""):
                rejected.append(
                    "%s is not where the %s is; a route is cut where the "
                    "rider actually rides" % (by, courier_voice(courier)))
                continue
            taker_key = str(raw.get("listener") or by or "") \
                .strip().casefold()
            taker = index.get(taker_key)
            if taker is not None and taker.get("room") == by_room:
                # The taker takes everything the body carried: a seized
                # letter reads verbatim, a spoken story arrives one mouth on.
                probe = dict(courier)
                probe["_names"], probe["_places"] = list(names), list(places)
                for held, sealed in carried_bundle(courier):
                    copy = _copy_of(probe, held, sealed, by_room, turn)
                    if copy is not None:
                        _give_report(cid, frame_id, taker, copy)
            silenced = dict(courier)
            silenced["status"] = SILENCED
            silenced["silenced_turn"] = turn
            silenced["passed"] = []
            couriers[couriers.index(courier)] = silenced
            by_uid[uid] = silenced
            metrics["courier_silenced"] += 1
            continue

    couriers, moves = advance_couriers(
        couriers, passable_neighbors(scene), now)
    metrics["courier_moves"] = len(moves)

    crowds_standing = [dict(c) for c in
                       wget(cid, crowds_model.CROWDS_WORLD_KEY, []) or []
                       if isinstance(c, dict)]
    # Stop exchanges before deliveries, in the same transaction: a caravan
    # whose last segment completed this sweep owes its final stop its
    # exchange before what it gathered there can be delivered at the gate.
    crowds_dirty = _exchange_stops(
        ctx, couriers, crowds_standing, names=names, places=places,
        turn=turn, metrics=metrics)
    for i, courier in enumerate(couriers):
        if courier.get("status") != ARRIVED:
            continue
        courier = dict(courier)
        courier["_names"], courier["_places"] = list(names), list(places)
        courier, delivered_to, dirty = _deliver(
            ctx, scene, courier, index, crowds_standing, turn=turn)
        courier.pop("_names", None)
        courier.pop("_places", None)
        couriers[i] = courier
        crowds_dirty = crowds_dirty or dirty
        if delivered_to:
            metrics["courier_delivered"] += 1

    live = [c for c in couriers if c.get("status") in _LIVE]
    done = [c for c in couriers if c.get("status") not in _LIVE]
    couriers = done[-_FINISHED_KEPT:] + live

    if crowds_dirty:
        wset(cid, crowds_model.CROWDS_WORLD_KEY, crowds_standing)
    if json.dumps(couriers, sort_keys=True, ensure_ascii=False) != before:
        wset(cid, COURIERS_WORLD_KEY, couriers)
    metrics["couriers_standing"] = len(live)
    metrics["courier_rejected"] = len(rejected)
    return metrics, rejected
