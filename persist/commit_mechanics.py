"""In-transaction sweeps over time and channel: transit/news arrivals and
expiry, the world-event spine, information carriers, and cast changes.

Extracted verbatim from commit.py, which re-exports every name here. The
deferred function-body imports (scene, living_world, carriers, couriers,
artifacts) are the existing cycle-breakers and stay deferred.
See docs/experiments/AUDIT_COMMIT.md for the split record.
"""

import copy
import json, time
from core.db import q, qtx, transaction, wget, wset
from story.character_schema import character_name_from_text, persona_name
from story.scene import cast_change_status, set_char_status
from world.mechanics import mechanics_sweep, stable_event_key
from persist.commit_common import _registered_name_roster, _room_of
from persist.commit_scene_state import prepare_scene_commit

# ---- Mechanics sweep: timed arrivals, expiry, news, engine notices ----

def commit_transit_sweep(ctx, nonce, *, prepared=None):
    """Commit-domain wrapper around mechanics.mechanics_sweep, run FIRST
    among commit_all's domains -- the sweep mutates the PREPARED scene, and
    commit_scene (which runs after it) is what persists those effects.

    The ordered passes themselves -- (a) fire due scheduled events for THIS
    frame (transit arrivals + news arrivals), (b) schedule new arrivals,
    (c) condition expiry, (d) dock-edge recompute, (e) vehicle-zone/
    companion-carry inference -- live in mechanics.py (see its module
    docstring for the contract). This wrapper only feeds it the database
    rows and applies the event_ops it returns: all writes run inside the
    caller's transaction (nested transaction() is a savepoint), and
    checkpoint restore snapshots scheduled_events/world_conditions whole,
    so a rerolled turn reproduces the exact pending/fired state.
    """
    cid = ctx.chat.id
    frame_id = ctx.turn.frame_id
    prepared = prepared or prepare_scene_commit(ctx)
    sc = prepared["scene"]
    clock = prepared.get("clock") or wget(cid, "simulation_clock", {}) or {}
    res = ctx.director_resolve or ctx.director_establish or {}
    diff = res.get("state_diff") or {}
    cast_names = [character_name_from_text(c["sheet"]) for c in ctx.cast]

    # The player's room in the PREPARED scene -- after this beat's movement
    # merged -- so a consequence landing exactly where the party now stands
    # is a walk-in (notice) and one anywhere else stays unencountered state.
    # Read for the presence gate only; nothing about the fuse's content or
    # priority may depend on the player (living_world's header contract).
    _player_room = None
    try:
        from story.scene import persona_of
        _player_room = _room_of(sc, persona_name(persona_of(ctx.chat)))
    except Exception:
        pass

    with transaction():
        pending = [dict(r) for r in q(
            "SELECT * FROM scheduled_events WHERE chat_id=? AND "
            "status='pending' AND kind IN "
            "('transit_arrival','news_arrival','consequence') "
            "ORDER BY due_at",
            (cid,),
        )]
        conditions = [dict(r) for r in q(
            "SELECT condition_id, expires_at FROM world_conditions "
            "WHERE chat_id=? AND active=1",
            (cid,),
        )]
        prev_scene = wget(cid, "scene", {}) or {}

        _, event_ops, notices = mechanics_sweep(
            sc, clock, frame_id, pending,
            conditions=conditions, prev_scene=prev_scene, chat_id=cid,
            turn_id=ctx.turn.id, turn_idx=ctx.turn.idx,
            cast_names=cast_names,
            cast_changes=diff.get("cast_changes") or [],
            player_room=_player_room,
        )

        kind_by_id = {row["event_id"]: row["kind"] for row in pending}
        row_by_id = {row["event_id"]: row for row in pending}
        fired = scheduled = expired = news_fired = consequences_fired = 0
        fired_consequence_rows = []
        fired_events = []
        for op in event_ops:
            if op[0] == "status":
                _, event_id, status = op
                # chat_id in the WHERE: event ids are per-chat since the
                # (chat_id, event_id) repartition -- a same-install import
                # keeps the source chat's ids verbatim, so an unscoped
                # update would flip BOTH chats' rows.
                qtx("UPDATE scheduled_events SET status=? "
                    "WHERE chat_id=? AND event_id=?",
                    (status, cid, event_id))
                if status == "fired":
                    if event_id in row_by_id:
                        fired_events.append({
                            "event_id": event_id,
                            "kind": row_by_id[event_id]["kind"],
                            "location_id": row_by_id[event_id]["location_id"],
                            "occurred_at": row_by_id[event_id]["due_at"],
                            "payload": row_by_id[event_id]["payload"],
                            "seed": row_by_id[event_id]["seed"],
                        })
                    if kind_by_id.get(event_id) == "news_arrival":
                        news_fired += 1
                    elif kind_by_id.get(event_id) == "consequence":
                        consequences_fired += 1
                        if event_id in row_by_id:
                            fired_consequence_rows.append(row_by_id[event_id])
                    else:
                        fired += 1
            elif op[0] == "schedule":
                row = op[1]
                qtx(
                    "INSERT OR REPLACE INTO scheduled_events"
                    "(event_id,chat_id,due_at,kind,location_id,payload,seed,"
                    "status) VALUES(?,?,?,?,?,?,?,?)",
                    (row["event_id"], row["chat_id"], row["due_at"],
                     row["kind"], row["location_id"], row["payload"],
                     row["seed"], row["status"]),
                )
                scheduled += 1
            elif op[0] == "expire_condition":
                qtx("UPDATE world_conditions SET active=0 "
                    "WHERE chat_id=? AND condition_id=?", (cid, op[1]))
                expired += 1

        # Living world, approach B: mint this resolution's declared fuses.
        # Gated by the chat's setting (the mint is the feature's surface);
        # FIRING above is not gated -- rows exist only if minting was on,
        # and a story that turns the setting off keeps the consequences it
        # already caused, the way it keeps its scheduled arrivals.
        consequences_minted = 0
        try:
            from world.living_world import (living_world_allows,
                                      living_world_config,
                                      mint_consequences,
                                      record_obligations)
            _declared_fuses = diff.get("consequences") or []
            if living_world_allows(living_world_config(cid),
                                   "scheduled_consequence", "floor"):
                mint_rows, mint_warnings = mint_consequences(
                    cid, sc, frame_id, ctx.turn.id, ctx.turn.idx,
                    float((clock or {}).get("elapsed_seconds") or 0.0),
                    _declared_fuses,
                    player_room=_player_room)
                for row in mint_rows:
                    qtx(
                        "INSERT OR REPLACE INTO scheduled_events"
                        "(event_id,chat_id,due_at,kind,location_id,payload,"
                        "seed,status) VALUES(?,?,?,?,?,?,?,?)",
                        (row["event_id"], row["chat_id"], row["due_at"],
                         row["kind"], row["location_id"], row["payload"],
                         row["seed"], row["status"]),
                    )
                    consequences_minted += 1
                for warning in mint_warnings:
                    ctx.add_warning(f"consequence not minted: {warning}")
            elif _declared_fuses:
                # A silently swallowed declaration would look like a quiet
                # world; the ledger's whole failure history is mechanisms
                # that never fired and nothing saying so.
                ctx.add_warning(
                    f"{len(_declared_fuses)} declared consequence(s) "
                    "dropped: the scheduled-consequence setting is off "
                    "for this chat")
            # Approach D's feed: a fuse fired at an ungenerated place is
            # history that place now owes. Recorded regardless of the D
            # setting -- layer-1 truth accumulates; settings gate surfaces
            # (the honour seam in mapping), never truth.
            if fired_consequence_rows:
                record_obligations(cid, fired_consequence_rows)
        except Exception as exc:
            ctx.add_warning(f"living-world consequences not committed: {exc}")

        # What the deterministic layer made of this beat's output, in the
        # Director's own terms. Carried on the same channel as the mechanical
        # notices because it is the same kind of message: here is what
        # actually happened, as against what you asked for.
        notices = list(notices) + list(getattr(ctx, "engine_feedback", []) or [])
        wset(cid, "engine_notices", notices)

    return {"fired": fired, "scheduled": scheduled, "expired": expired,
            "news_fired": news_fired,
            "consequences_fired": consequences_fired,
            "consequences_minted": consequences_minted,
            "fired_events": fired_events, "notices": notices}


def commit_world_event_spine(ctx, transit_result):
    """Promote fired mechanics rows into checkpointed objective history.

    ``scheduled_events`` answers what is still due; ``world_events`` answers
    what objectively happened. This seam is deliberately downstream of the
    mechanics adjudication and cannot invent an event. Stable ids make a
    repeated landing harmless, while the containing turn transaction and the
    table's checkpoint/branch/archive plumbing make reroll authoritative.
    """
    rows = []
    for fired in (transit_result or {}).get("fired_events") or []:
        if not isinstance(fired, dict) or not fired.get("event_id"):
            continue
        raw_payload = fired.get("payload")
        try:
            payload = json.loads(raw_payload or "{}") \
                if isinstance(raw_payload, str) else copy.deepcopy(raw_payload or {})
        except (json.JSONDecodeError, TypeError):
            payload = {"detail": str(raw_payload or "")[:500]}
        if not isinstance(payload, dict):
            payload = {"detail": payload}
        payload["source_event_id"] = str(fired["event_id"])
        world_event_id = stable_event_key(
            "world_event", ctx.chat.id, ctx.turn.frame_id, fired["event_id"])
        if q("SELECT 1 FROM world_events WHERE chat_id=? AND event_id=?",
             (ctx.chat.id, world_event_id), one=True):
            continue
        qtx(
            "INSERT OR IGNORE INTO world_events("
            "event_id,chat_id,turn_id,frame_id,occurred_at,duration_seconds,"
            "kind,location_id,payload,seed,committed) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (world_event_id, ctx.chat.id, ctx.turn.id, ctx.turn.frame_id,
             float(fired.get("occurred_at") or 0.0), 0.0,
             str(fired.get("kind") or "event"), fired.get("location_id"),
             json.dumps(payload, ensure_ascii=False), fired.get("seed"),
             time.time()),
        )
        rows.append({
            "event_id": world_event_id,
            "source_event_id": str(fired["event_id"]),
            "kind": str(fired.get("kind") or "event"),
            "location_id": fired.get("location_id"),
        })
    return {"offered": len((transit_result or {}).get("fired_events") or []),
            "written": len(rows), "events": rows}


def commit_information_carriers(ctx, prepared_scene, world_event_result):
    """Acquire/move character-owned public reports after memory state lands,
    then copy any that were actually passed on this beat.

    Tellings run AFTER acquisition, so a witness can pass on what they saw in
    the same beat they saw it -- which is what someone running in to say what
    just happened actually is. They run inside the same domain because a
    telling that landed while the acquisition it copied from rolled back would
    be a mind holding a report of an event that never happened.
    """
    from story.carriers import advance_carriers, apply_tellings

    scene = (prepared_scene or {}).get("scene") or {}
    result = advance_carriers(ctx, scene, world_event_result)

    resolved = ctx.director_resolve or ctx.director_establish or {}
    ops = (resolved.get("state_diff") or {}).get("telling_ops") or []
    if not isinstance(ops, list):
        ops = []
    courier_ops = (resolved.get("state_diff") or {}).get("courier_ops") or []
    if not isinstance(courier_ops, list):
        courier_ops = []
    artifact_ops = (resolved.get("state_diff") or {}).get("artifact_ops") or []
    if not isinstance(artifact_ops, list):
        artifact_ops = []
    if not result.get("enabled"):
        if ops:
            ctx.add_warning(
                "discarded %d telling(s): the rumor-ledger floor is off"
                % len(ops))
        if courier_ops:
            ctx.add_warning(
                "discarded %d courier op(s): the rumor-ledger floor is off"
                % len(courier_ops))
        if artifact_ops:
            ctx.add_warning(
                "discarded %d artifact op(s): the rumor-ledger floor is off"
                % len(artifact_ops))
        result["told"] = 0
        return result

    # What degradation is allowed to redact. The engine names its own cast and
    # rooms rather than letting a detector guess which words are people: a
    # wrong guess silently rewrites a claim into something false, and this is
    # the one module whose entire correctness argument is that it cannot
    # invent.
    names = list(_registered_name_roster(ctx.chat, ctx.cast))
    places = [str(r.get("name") or rid)
              for rid, r in (scene.get("rooms") or {}).items()
              if isinstance(r, dict)]
    places += list((scene.get("rooms") or {}).keys())

    told, rejected = apply_tellings(ctx, scene, ops, names=names,
                                    places=places)
    for reason in rejected:
        ctx.add_warning("telling refused: %s" % reason)
    result["told"] = told
    result["tellings_offered"] = len(ops)
    result["tellings_refused"] = len(rejected)

    # Couriers ride in the same domain and transaction: a dispatch copies a
    # report a mind holds NOW, so it must roll back with the acquisition it
    # copied from, exactly as tellings must. The sweep runs even on beats
    # with no ops -- the road moves whether or not anyone declares anything.
    from story.couriers import run_couriers

    courier_metrics, courier_rejected = run_couriers(
        ctx, scene, courier_ops, names=names, places=places)
    for reason in courier_rejected:
        ctx.add_warning("courier op refused: %s" % reason)
    result.update(courier_metrics)

    # Artifacts last, in the same domain and transaction: a bill posted from
    # a report acquired this beat must roll back with the acquisition it
    # copied, exactly as a dispatch must -- and running after the courier
    # sweep means a caravan reads the wall as it stood when the beat began,
    # never a bill nailed up later in the same instant.
    from story.artifacts import run_artifacts

    artifact_metrics, artifact_rejected = run_artifacts(
        ctx, scene, artifact_ops)
    for reason in artifact_rejected:
        ctx.add_warning("artifact op refused: %s" % reason)
    result.update(artifact_metrics)
    return result

# ---- Cast changes ----

def commit_cast_changes(ctx, nonce):
    chat = ctx.chat
    cid = chat.id
    res = ctx.director_resolve or {}
    diff = res.get("state_diff") or {}
    name2id = {
        character_name_from_text(r["sheet"]).lower(): r["id"]
        for r in q(
            "SELECT ch.id,COALESCE(cc.sheet,ch.sheet) AS sheet "
            "FROM chat_chars cc "
            "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
            (cid,),
        )
    }
    frame_id = ctx.turn.frame_id
    with transaction():
        for chg in (diff.get("cast_changes") or []):
            who = str(chg.get("who") or "").lower().strip()
            status = cast_change_status(chg.get("status"))
            if status is None:
                # Never silently: this used to be `stt in ("active",
                # "dormant")` with no else, so a character who walked out
                # under any other word stayed in the live roster -- present,
                # addressable, and running a step every beat -- while the
                # other readers of the SAME entry treated them as gone.
                ctx.add_warning(
                    "cast change for %r has unrecognized status %r; the "
                    "roster is unchanged (expected 'active' or 'dormant')"
                    % (chg.get("who"), chg.get("status")))
                continue
            if who not in name2id:
                ctx.add_warning(
                    "cast change names %r, who is not an attached character; "
                    "the roster is unchanged" % (chg.get("who"),))
                continue
            set_char_status(cid, name2id[who], status, frame_id=frame_id)
