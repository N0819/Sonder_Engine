"""THE LOT ARCHITECT: a building lot (`world/lots.py`) turned into the rooms of
its building when the player or a major character first comes upon it.

ONE CALL on the room designer's role says which rooms the building holds,
on which storeys, and how they join (`LOT_STEP`, `prose_contract.layout_lot`),
from what the plan says of the lot -- its name, what the building is for,
how it looks from outside, its footprint and storeys where given, the door it
opens by -- who the charter has living and working there, and what the
story's lore says of it. Code holds the answer to the engine's rules
(`planned_rooms_of`) and plants it as the plan's own rooms
(`structure.plant_structure`): the room the outside door opens into keeps the
lot's uid, its name and its ways onto the ground, so every charter record
and every join that named the lot still names a place; every other room is a
new planned room of the lot's part of the map, marked `lot_of`. The layout
tier then lays the building out as one, whatever storeys it has
(`director_layout.lay_out_buildings`, `layout_bridge.plan_buildings`), and the
designer dresses its rooms as it dresses any planned room.

WHERE IT RUNS. In the rooms-in-view job (`director_rooms._predevelop_run`),
before the tier, for a lot in reach of an actor or standing beside the room
one stands in, whatever its door (`lots_near`): "when an actor like a player
or major character stumble upon it" (the owner, 2026-10-28). The players
first, then the cast; never for a charter body, which only ever lives at the
lot. And in the beat that walks into a lot the job has not reached yet
(`expand_entered_lots`, called where the beat chooses the planned rooms it
enters), so its entry is designed as the entry of a building rather than as
the whole building in one room -- that beat pays one call, and the building
is not laid out by the tier, since its entry is then a room the story has
seen.

FAILS OPEN: an answer that cannot be read, plants no room, or a lot the story
has already described (designed as one room before this ran) leaves the lot
as it was, and the room is designed as any planned room is. A failure waits
before it is tried again (`director_rooms.predevelop_retry_beats`), filed in
`LOT_RUNS_KEY`.
"""
from __future__ import annotations

import time

from world.lots import (LOT_KEY, LOT_OF_KEY, LOT_ROOMS_MAX, LOT_STOREYS_MAX,
                        is_unexpanded_lot, normalize_lot)

#: The call's step key, by which the capture files it (`persist/llm_capture.py`).
LOT_STEP = "director_rooms_layout_lot"
#: Lots expanded per run of the rooms-in-view job, at most: one call each,
#: and the tier then lays out one building a run (`director_layout.
#: LAYOUT_TIER_PER_RUN`), so a second lot would wait for the tier anyway.
#: Named per ask-before-limiting.
LOTS_PER_RUN = 1
#: The world key filing each lot's last failed attempt: `{lot uid: {turn,
#: failed, error}}`. Reconstructible: lost, a lot is simply tried again.
LOT_RUNS_KEY = "lot_expansion_runs"
_SIDES = ("n", "e", "s", "w")


def _words(key):
    return " ".join(str(key or "").replace("_", " ").split())


def lot_people(cid, lot_uid):
    """Who the charter has at the lot: `{"sleep_here": n, "work_here":
    [posts], "kept_here": [upkeeps]}` -- counts and kinds of work, never a
    name: the architect plans rooms for people, and a room's purpose names
    no one."""
    sleepers, work, kept = 0, [], []
    try:
        from world.charter_runtime import cached_registry
        registry = cached_registry(cid) or {}
    except Exception:
        registry = {}
    for charter in ((registry.get("items") or {}).values()):
        state = (charter or {}).get("state") or {}
        for body in (state.get("bodies") or {}).values():
            if isinstance(body, dict) and str(body.get("berth") or "") == lot_uid:
                sleepers += 1
        for key, post in (state.get("posts") or {}).items():
            if isinstance(post, dict) and str(post.get("place") or "") == lot_uid:
                work.append(_words(post.get("key") or key))
        for key, upkeep in (state.get("upkeeps") or {}).items():
            if isinstance(upkeep, dict) and str(upkeep.get("place") or "") == lot_uid:
                kept.append(_words(upkeep.get("key") or key))
    return {"sleep_here": sleepers, "work_here": sorted(set(work)),
            "kept_here": sorted(set(kept))}


def _door(cid, lot_uid, spec, rows):
    """The lot's way onto the ground outside it, as the architect is told it:
    `{"opens_onto", "side", "barrier"}` -- the first way the plan states out
    of the lot, its wall the plan's bearing where one is stated."""
    from world.spatial import normalize_bearing, opposite_bearing
    for edge in spec.get("adjacent") or ():
        if not isinstance(edge, dict) or not edge.get("to") or edge.get("vertical"):
            continue
        to = str(edge["to"])
        side = normalize_bearing(edge.get("dir"))
        if side not in _SIDES:
            back = next((e for e in (((rows.get(to) or {}).get("planned") or {})
                                     .get("adjacent") or ())
                         if isinstance(e, dict) and str(e.get("to") or "") == lot_uid), None)
            side = opposite_bearing(normalize_bearing((back or {}).get("dir")))
        return {"opens_onto": str((rows.get(to) or {}).get("name") or _words(to)),
                "side": side if side in _SIDES else None,
                "barrier": str(edge.get("barrier") or "")}
    return {"opens_onto": None, "side": None, "barrier": ""}


def lot_payload(cid, lot_uid, rows, language_id=None):
    """What the architect reads for one lot (`prose_contract.layout_lot`)."""
    entry = rows[lot_uid]
    spec = entry["planned"] or {}
    lot = normalize_lot(spec.get(LOT_KEY)) or {}
    extent = spec.get("extent") if isinstance(spec.get("extent"), dict) else None
    lore = ""
    try:
        from agents.director_layout import building_description
        lore = building_description(cid, {
            "structure": spec.get("structure"), "structure_name": entry["name"],
            "rooms": [lot_uid], "names": {lot_uid: entry["name"]}})
    except Exception:
        lore = ""
    return {
        "lot": {"name": entry["name"], "purpose": str(spec.get("purpose") or ""),
                "far_look": str(spec.get("far_look") or ""),
                "footprint": ({"w": extent.get("w"), "d": extent.get("d")} if extent else None),
                "storeys": lot.get("storeys"), "cellar": bool(lot.get("cellar")),
                "door": _door(cid, lot_uid, spec, rows)},
        "people": lot_people(cid, lot_uid),
        "lore": lore,
        "max_rooms": LOT_ROOMS_MAX,
    }


def planned_rooms_of(lot_uid, rows, answer, *, turn_idx=None):
    """The architect's answer held to the engine's rules, as the rooms to
    plant: `(rooms, notes, sleeps)` -- `rooms` `{uid: planned spec}`, the
    entry under the lot's own uid, `notes` what was set aside and why,
    `sleeps` `{uid: how many sleep there}` where the answer says.
    `({}, notes, {})` when nothing can stand.

    Held: at most `LOT_ROOMS_MAX` rooms, ids unique; every room on a storey
    the lot has -- the plan's `storeys` above the ground (`LOT_STOREYS_MAX`
    where it gives none) and the one below only with its `cellar` -- the rest
    set aside; ONE entry on the ground storey (the first room the answer
    marks, else its first room on the ground, else none); a join to a room
    the answer does not hold dropped; a stair only between neighbouring
    storeys; every room reached from the entry, the rest set aside. The entry keeps the lot's name, its far look
    and its ways onto the ground; its purpose becomes its own, and what the
    lot said of the whole building is kept on its record (`building`), as
    its footprint is."""
    from story.plot_packages import _plan_edge
    from world.spatial import normalize_bearing, normalize_room_id, normalize_vertical
    notes = []
    raw = answer.get("rooms") if isinstance(answer, dict) else None
    if not isinstance(raw, list):
        return {}, ["the answer holds no list of rooms"], {}
    lot_spec = rows[lot_uid]["planned"] or {}
    lot = normalize_lot(lot_spec.get(LOT_KEY)) or {}
    rooms, order = {}, []
    for item in raw:
        if not isinstance(item, dict):
            continue
        rid = normalize_room_id(str(item.get("id") or item.get("name") or ""))
        if not rid or rid in rooms:
            continue
        if len(order) >= LOT_ROOMS_MAX:
            notes.append(f"{rid}: past the {LOT_ROOMS_MAX} rooms a lot is built with")
            continue
        try:
            level = int(item.get("level") or 0)
        except (TypeError, ValueError):
            level = 0
        rooms[rid] = {"item": item, "level": level}
        order.append(rid)
    # THE STOREYS THE PLAN GIVES. The architect is told the lot's `storeys`
    # and whether a storey lies below the ground, and any integer `level` was
    # planted: a lot planned `storeys: 1` with no cellar stood on levels
    # -1..4, no note, its record and its building disagreeing and the layout
    # tier laying out a tower (audit of 2026-11-01, agents_runtime_loops_
    # mapping F14). A room on a storey the lot does not have is set aside and
    # said; what only it reached is set aside below, by the reachability
    # walk. Where the plan gives no storeys, `LOT_STOREYS_MAX` -- the storeys
    # a lot may ask for -- bounds the answer as it bounds the ask.
    lowest = -1 if lot.get("cellar") else 0
    highest = int(lot.get("storeys") or LOT_STOREYS_MAX) - 1
    off_storey = set()
    for rid in list(order):
        level = rooms[rid]["level"]
        if lowest <= level <= highest:
            continue
        notes.append(f"{rid}: on storey {level}, which the lot does not have "
                     f"(storeys {lowest} to {highest}), set aside")
        off_storey.add(rid)
        order.remove(rid)
        del rooms[rid]
    if not order:
        return {}, notes + ["the answer names no room"], {}
    entry = next((r for r in order if rooms[r]["item"].get("entry") is True
                  and rooms[r]["level"] == 0), None) or \
        next((r for r in order if rooms[r]["level"] == 0), None)
    if entry is None:
        return {}, notes + ["no room stands on the ground storey to be the entry"], {}
    taken = set(rows) - {lot_uid}
    uid_of = {}
    for rid in order:
        if rid == entry:
            uid_of[rid] = lot_uid
            continue
        base = f"{lot_uid}__{rid}"
        uid, k = base, 2
        while uid in taken or uid in uid_of.values():
            uid, k = f"{base}_{k}", k + 1
        uid_of[rid] = uid
    edges = {rid: [] for rid in order}
    for rid in order:
        for join in rooms[rid]["item"].get("joins") or ():
            if not isinstance(join, dict):
                continue
            to = normalize_room_id(str(join.get("to") or ""))
            if to not in rooms or to == rid:
                if to and to not in off_storey:
                    notes.append(f"{rid}: a join to {to}, no room of the answer, dropped")
                continue
            vertical = normalize_vertical(join.get("vertical"))
            step = rooms[to]["level"] - rooms[rid]["level"]
            if vertical:
                if step != {"up": 1, "down": -1}[vertical]:
                    notes.append(f"{rid}: its stair {vertical} to {to} joins no neighbouring storey")
                    continue
            elif step != 0:
                if abs(step) != 1:
                    notes.append(f"{rid}: a join to {to} on another storey, with no stair, dropped")
                    continue
                vertical = "up" if step > 0 else "down"
            edge = {"to": uid_of[to]}
            side = normalize_bearing(join.get("side"))
            if side in _SIDES:
                edge["dir"] = side
            barrier = " ".join(str(join.get("barrier") or "").split())[:80]
            if barrier:
                edge["barrier"] = barrier
            if vertical:
                edge["vertical"] = vertical
                way = str(join.get("way") or "").strip().casefold()
                edge["way"] = way if way in ("stair", "ladder", "hatch") else "stair"
            edges[rid].append(_plan_edge(edge))
    # every room reached from the entry, through the joins either way
    linked = {rid: set() for rid in order}
    back = {v: k for k, v in uid_of.items()}
    for rid, out in edges.items():
        for edge in out:
            other = back.get(edge["to"])
            if other:
                linked[rid].add(other)
                linked[other].add(rid)
    seen, queue = {entry}, [entry]
    while queue:
        cur = queue.pop(0)
        for nxt in sorted(linked[cur] - seen):
            seen.add(nxt)
            queue.append(nxt)
    for rid in order:
        if rid not in seen:
            notes.append(f"{rid}: reached from the entry by no join, set aside")
    planted, sleeps = {}, {}
    for rid in order:
        if rid not in seen:
            continue
        item = rooms[rid]["item"]
        try:
            sleepers = int(item.get("sleeps") or 0)
        except (TypeError, ValueError):
            sleepers = 0
        if sleepers > 0:
            sleeps[uid_of[rid]] = sleepers
        own = [e for e in edges[rid] if e["to"] in {uid_of[s] for s in seen}]
        spec = {"name": " ".join(str(item.get("name") or _words(rid)).split())[:120],
                "purpose": " ".join(str(item.get("purpose") or "").split())[:400],
                "exposure": "enclosed", "level": rooms[rid]["level"],
                "adjacent": own, LOT_OF_KEY: lot_uid}
        if rid == entry:
            record = dict(lot, expanded=int(turn_idx) if turn_idx is not None else 0)
            if lot_spec.get("purpose"):
                record["building"] = str(lot_spec["purpose"])
            extent = lot_spec.get("extent")
            if isinstance(extent, dict) and extent.get("w") and extent.get("d"):
                record["footprint"] = {"w": extent["w"], "d": extent["d"]}
            outside = [dict(e) for e in lot_spec.get("adjacent") or ()
                       if isinstance(e, dict) and e.get("to")]
            spec.update({"name": rows[lot_uid]["name"] or spec["name"],
                         "purpose": spec["purpose"] or str(lot_spec.get("purpose") or ""),
                         "adjacent": outside + own, LOT_KEY: record})
            for key in ("far_look", "access", "anchors"):
                if lot_spec.get(key):
                    spec[key] = lot_spec[key]
        planted[uid_of[rid]] = spec
    return planted, notes, sleeps


def _story_described(scene, uid):
    room = ((scene or {}).get("rooms") or {}).get(uid)
    return isinstance(room, dict) and bool(str(room.get("desc") or room.get("description") or "").strip())


def _waiting(cid, lot_uid, turn_idx):
    from agents.director_rooms import predevelop_retry_beats
    from core.db import wget
    from core.jobs import story_rewound_past
    runs = wget(cid, LOT_RUNS_KEY) or {}
    entry = runs.get(lot_uid) if isinstance(runs, dict) else None
    if not isinstance(entry, dict) or not int(entry.get("failed") or 0):
        return False
    at = entry.get("turn")
    if at is None or turn_idx is None or story_rewound_past(at, turn_idx):
        return False
    return int(turn_idx) - int(at) < predevelop_retry_beats(entry.get("failed"))


def _file_failure(cid, lot_uid, turn_idx, error):
    from core.db import transaction, wget, wset
    with transaction():
        runs = wget(cid, LOT_RUNS_KEY) or {}
        runs = dict(runs) if isinstance(runs, dict) else {}
        failed = int((runs.get(lot_uid) or {}).get("failed") or 0) + 1
        runs[lot_uid] = {"turn": turn_idx, "failed": failed, "error": str(error)[:300]}
        wset(cid, LOT_RUNS_KEY, runs)


def deal_berths(cid, lot_uid, sleeps, *, frame_id=None, notes=None):
    """THE LOT'S SLEEPERS GO TO THE ROOMS THEY SLEEP IN: every charter body
    berthed at the lot, by key, dealt over the rooms the architect says people
    sleep in (`sleeps`, `{uid: how many}`), in the plan's order, each filled to
    its count and the rest to the last; how many were moved. Their `place`
    stays where it is -- the entry still stands where it stood -- so a body at
    home is still at home. Nothing moves where no room says it sleeps anyone,
    and the lot's uid, the entry's, stays a berth that names a place.

    DEALT BY ARITHMETIC, AND THE OVERFLOW SAID. This built one list slot per
    bed from the answer's unbounded `sleeps` -- "sleeps": 100000000 built a
    hundred-million-element list in the job's thread -- and put every
    sleeper past the beds in the last room without a word: twelve bodies over
    beds for 2 + 2 + 1 berthed eight in the one-bed garret, past the charter's
    own `BERTH_CEILING` (audit of 2026-11-01, world_layout_bridge_structure
    F10). Where the overflow goes is unchanged -- the last sleeping room --
    and is the owner's to change; it is now appended to `notes`.

    ONE READ-MODIFY-WRITE UNDER THE WRITE LOCK: the registry is read and saved
    inside one `transaction()`, so a commit's charter flush cannot land between
    them and be overwritten (agents_runtime_loops_mapping F4)."""
    if not sleeps:
        return 0
    from core.db import transaction
    from world.charter_runtime import registry_for_update, save_registry
    beds = []
    for uid, count in sleeps.items():
        try:
            beds.append((uid, max(0, int(count))))
        except (TypeError, ValueError):
            beds.append((uid, 0))
    with transaction():
        registry = registry_for_update(cid, frame_id)
        berthed = []
        for ckey, charter in sorted((registry.get("items") or {}).items()):
            bodies = ((charter or {}).get("state") or {}).get("bodies") or {}
            for bkey in sorted(bodies):
                body = bodies[bkey]
                if isinstance(body, dict) and str(body.get("berth") or "") == lot_uid:
                    berthed.append(body)
        if not berthed:
            return 0
        dealt = 0
        for uid, count in beds:
            take = min(count, len(berthed) - dealt)
            for body in berthed[dealt:dealt + take]:
                body["berth"] = uid
            dealt += take
        last = beds[-1][0]
        over = berthed[dealt:]
        for body in over:
            body["berth"] = last
        if over and notes is not None:
            notes.append(f"{len(over)} sleepers past the {dealt} beds the "
                         f"building's rooms hold, berthed in {last}")
        save_registry(cid, registry, frame_id)
    return len(berthed)


def expand_lot(cid, lot_uid, scene=None, *, call=None, language_id=None,
               turn_idx=None, job=None, frame_id=None):
    """Expand one lot into its building: the uids planted (the lot's own
    first), or `[]` when it was not -- no lot, already expanded, described
    by the story, waiting after a failure, or the answer failed. Never
    raises."""
    from core.logging_utils import logger
    try:
        from core import jobs
        from llm.prompts import layout_prompt
        from world.structure import plant_structure, registry_rows
        from story.plot_packages import _structure_as_held
        from agents.director_layout import _default_call, _recording
        rows = registry_rows(cid)
        entry = rows.get(lot_uid)
        if not entry or not is_unexpanded_lot(entry["planned"]):
            return []
        if _story_described(scene, lot_uid) or _waiting(cid, lot_uid, turn_idx):
            return []
        started = time.time()
        recorded = _recording(cid, call or _default_call, turn_idx)
        answer = recorded(LOT_STEP, layout_prompt("lot", language_id),
                          lot_payload(cid, lot_uid, rows, language_id))
        rooms, notes, sleeps = planned_rooms_of(lot_uid, rows, answer, turn_idx=turn_idx)
        if not rooms:
            _file_failure(cid, lot_uid, turn_idx, "; ".join(notes[:4]) or "no room")
            logger.info("lot: chat=%s lot=%s not expanded: %s", cid, lot_uid,
                        "; ".join(notes[:6]))
            return []
        # ONE LOCK FROM THE RE-CHECK TO THE BERTHS. The re-check, the
        # planting and the charter registry's read-modify-write ran as three
        # separate writes, the last outside any transaction: two expansions of
        # one lot -- the job's and a beat's, or two frames' jobs -- returning
        # from their calls together could both pass the re-check and both
        # plant, and a commit's charter flush landing inside `deal_berths` was
        # overwritten (audit of 2026-11-01, agents_runtime_loops_mapping F4,
        # agents_director_prose_movement_rooms F6). `transaction()` is the
        # process-wide write lock and BEGIN IMMEDIATE; the planting's and the
        # dealing's own transactions nest inside it as savepoints.
        from core.db import transaction
        with transaction():
            if job is not None and jobs.is_cancelled(job):
                return []
            # THE PLAN MAY HAVE MOVED WHILE THE CALL RAN: the lot re-planned,
            # or expanded by the beat that walked into it
            if registry_rows(cid).get(lot_uid, {}).get("planned") != entry["planned"]:
                return []
            structure = _structure_as_held(
                cid, {"key": str(entry["planned"].get("structure") or "")})
            _structure, planted = plant_structure(cid, structure, rooms)
            dealt = deal_berths(
                cid, lot_uid, {uid: n for uid, n in sleeps.items() if uid in planted},
                frame_id=frame_id, notes=notes)
        if dealt:
            notes.append(f"{dealt} sleepers berthed in the building's rooms")
        logger.info("lot: chat=%s lot=%s expanded into %d rooms in %.1fs%s", cid, lot_uid,
                    len(planted), time.time() - started,
                    ("; " + "; ".join(notes[:6])) if notes else "")
        return [lot_uid] + sorted(uid for uid in planted if uid != lot_uid)
    except Exception as exc:  # noqa: BLE001 -- a lot never stops a beat or a run
        try:
            _file_failure(cid, lot_uid, turn_idx, exc)
        except Exception:
            pass
        logger.info("lot: chat=%s lot=%s could not be expanded: %s", cid, lot_uid,
                    " ".join(str(exc).split())[:300])
        return []


def lots_near(cid, scene, bodies):
    """The lots still waiting for their building that `bodies` have come
    upon, in the order they are wanted: for each body in turn, the lot it is
    walking to and the next room on its way (`director_rooms._heading`),
    then every lot in its reach (`director_rooms.rooms_in_reach`: in view,
    or on its way) and every lot whose door opens off the room it stands in,
    whatever the door. A street of open doors puts every house on it in
    view, and the house a body is walking to comes first."""
    from agents.director_rooms import _heading, rooms_in_reach
    from world.lots import unexpanded_lots
    from world.spatial import room_of
    from world.structure import registry_rows
    lots = unexpanded_lots(registry_rows(cid))
    if not lots:
        return []
    rooms = (scene or {}).get("rooms") or {}
    out = []
    for body in bodies or ():
        here = room_of(scene, body) if body else None
        beside = [str(e.get("to")) for e in (rooms.get(here) or {}).get("adjacent") or ()
                  if isinstance(e, dict) and e.get("to")] if here else []
        next_leg, destination = _heading(scene, body) if here else (None, None)
        for rid in [destination, next_leg] + list(rooms_in_reach(scene, body)) + beside:
            if rid in lots and rid not in out:
                out.append(rid)
    return out


def expand_lots_near(job, cid, scene, bodies, language_id, *, call=None, frame_id=None):
    """The rooms-in-view job's half: expand up to `LOTS_PER_RUN` lots the
    actors have come upon; the uids of the lots expanded."""
    done = []
    for lot_uid in lots_near(cid, scene, bodies):
        if len(done) >= LOTS_PER_RUN:
            break
        if expand_lot(cid, lot_uid, scene, call=call, language_id=language_id,
                      turn_idx=getattr(job, "base_turn", None), job=job, frame_id=frame_id):
            done.append(lot_uid)
    return done


def expand_entered_lots(cid, develop, scene, language_id, *, call=None, turn_idx=None,
                        frame_id=None):
    """The beat's half: `develop` (`{room: brief}`, the planned rooms the beat
    enters) with each lot among them expanded first and its brief read again
    as its building's entry. A lot that is not expanded keeps its brief, and
    the beat is told so.

    EVERY LOT'S BRIEF IS READ AGAIN, WHOEVER EXPANDED IT. `develop` was built
    with the stage's payload, and the rooms-in-view job expands exactly the
    lot an actor is heading for: a lot it planted between the payload and
    this call was skipped here as already expanded and kept its LOT brief --
    the whole building's purpose, designed as one room, which is what the
    lot exists to prevent; the same when this beat's own expansion lost the
    race to the job. And a lot the beat could not expand left no trace of it
    (audit of 2026-11-01, agents_director_prose_movement_rooms F5): each
    outcome is now a decision on the step, and a lot left as one room a
    warning."""
    if not develop:
        return develop
    from core.pipeline_context import note_step_decision, note_step_warning
    from world.structure import planned_room_brief, registry_rows
    rows = registry_rows(cid)
    lots = [rid for rid in develop
            if normalize_lot(((rows.get(rid) or {}).get("planned") or {}).get(LOT_KEY))
            is not None]
    if not lots:
        return develop
    out = dict(develop)
    for rid in lots:
        try:
            if is_unexpanded_lot((rows.get(rid) or {}).get("planned")):
                if expand_lot(cid, rid, scene, call=call, language_id=language_id,
                              turn_idx=turn_idx, frame_id=frame_id):
                    note_step_decision("lot_expansion", rid, "expanded",
                                       "expanded by the beat that entered it")
                elif is_unexpanded_lot((registry_rows(cid).get(rid) or {}).get("planned")):
                    runs = _lot_runs(cid).get(rid) or {}
                    why = str(runs.get("error") or "not asked: waiting after a "
                              "failure, or described by the story already")
                    note_step_decision("lot_expansion", rid, "not expanded", why[:200])
                    note_step_warning(
                        f"lot {rid}: not expanded into its building ({why[:160]}); "
                        "the beat designs it as one room")
                    continue
            brief = (planned_room_brief(cid, scene, [rid]) or {}).get(rid)
        except Exception as exc:  # noqa: BLE001 -- a lot never stops a beat; said
            note_step_warning(f"lot {rid}: its building could not be read "
                              f"({type(exc).__name__}: {str(exc)[:160]}); the "
                              "beat designs it from the brief it had")
            continue
        if brief:
            out[rid] = brief
    return out


def _lot_runs(cid):
    """`LOT_RUNS_KEY`'s record, `{lot uid: {turn, failed, error}}`, or {}."""
    from core.db import wget
    runs = wget(cid, LOT_RUNS_KEY) or {}
    return runs if isinstance(runs, dict) else {}
