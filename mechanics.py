"""Deterministic mechanics sweep (movement/space Phase 2, item 3).

One ordered orchestration of every deterministic mechanical follow-through
that used to be scattered across commit_transit_sweep's inline body and
prepare_scene_commit's tail:

    (a) fire due scheduled_events for THIS frame (transit_arrival moves
        the entity and docks it; news_arrival stages latency-gated
        awareness -- see the news note below);
    (b) schedule new arrivals from entity.state.transit eta declarations;
    (c) expire due world_conditions;
    (d) recompute derived dock edges (when an arrival fired);
    (e) vehicle-zone / companion-carry inference.

`mechanics_sweep` is pure with respect to the DATABASE: it never writes --
every durable effect is returned as an event_op for the commit domain
(commit.commit_transit_sweep) to apply inside the turn's transaction. It
mutates only the passed-in scene dict, exactly as the pieces it gathers
always did. Pass implementations shared with other consumers stay where
those consumers need them (apply_transit_dock_edges in spatial.py, because
merge_scene_with_diff must derive the same doorways for perception's
mid-turn merges; infer_vehicle_zones/infer_companion_carry in
spatial_frames.py, whose tests exercise them directly) -- this module owns
the ordering and the sweep contract, not duplicate copies.

Behavior preservation notes (the refactor this module came from is
contractually behavior-identical -- tests/test_mechanics_sweep.py pins it):
- pass (e) ALSO runs during scene preparation (prepare_scene_commit), so
  memory preparation -- which reads the prepared scene before the write
  transaction opens -- sees carried companions at their new position, as
  it always has. Both passes are idempotent, so the sweep's (e) run is a
  no-op unless pass (a) moved a vehicle this very sweep -- the one case
  the old arrangement structurally missed.
- pass (d) runs only when an arrival fired, mirroring the old sweep: on a
  no-fire turn the dock edges were already derived by
  merge_scene_with_diff during preparation.

News arrivals (item 4): a `news_arrival` event is minted by the
destruction commit path (one per audience scope, due_at = the minting
frame's clock + declared latency, deterministic stable id). Firing one
stages an engine notice carrying told/heard provenance for the next
director turn to acknowledge -- destruction is objective the moment it
commits; AWARENESS of it propagates only through this latency gate and
then through the ordinary director/perception filters, never by code
injecting knowledge directly into minds.

Reproducibility contract (unchanged from the pieces this gathers): due
times compare against the SIM clock only (never wall-clock), events are
frame-gated via the frame_id in their payload, event ids are stable hashes
of (kind, chat, frame, subject, turn), and checkpoint restore snapshots
scheduled_events/world_conditions whole -- so a rerolled turn reproduces
the exact pending/fired state.
"""

from __future__ import annotations

import hashlib
import json

from spatial import apply_transit_dock_edges
from spatial_frames import infer_companion_carry, infer_vehicle_zones


def stable_event_key(*parts):
    """Deterministic id for events/memories: same inputs, same id, so a
    rerun cannot double-schedule or double-store."""
    raw = "\x1f".join(str(part or "") for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return f"event:{digest}"


def _payload_of(row):
    try:
        payload = json.loads(row.get("payload") or "{}")
    except Exception:
        payload = {}
    return payload if isinstance(payload, dict) else {}


def _fire_due_events(scene, elapsed, frame_id, pending):
    """Pass (a). Returns (event_ops, notices, counts, pending_entity_ids).

    pending rows arrive in due_at order (the caller's query) and each is
    frame-gated by the frame_id in its payload: scheduled_events has no
    frame column while simulation clocks are frame-scoped, so an event
    minted in one frame must never fire against another frame's clock.
    """
    event_ops = []
    notices = []
    fired = news_fired = 0
    pending_entity_ids = set()
    entities = scene.get("entities") or {}
    positions = scene.setdefault("positions", {})

    for row in pending:
        payload = _payload_of(row)
        if row.get("kind") == "news_arrival":
            if payload.get("frame_id") != frame_id or row["due_at"] > elapsed:
                continue
            event_ops.append(("status", row["event_id"], "fired"))
            news_fired += 1
            audience = str(payload.get("audience") or "nearby observers")
            summary = str(payload.get("summary") or "word of a distant event")
            notices.append(
                f"News reaches {audience} (told/heard, not witnessed): "
                f"{summary}"
            )
            continue

        # transit_arrival
        eid = str(payload.get("entity_id") or "")
        if payload.get("frame_id") != frame_id or row["due_at"] > elapsed:
            pending_entity_ids.add(eid)
            continue
        ent = entities.get(eid)
        state = ent.get("state") if isinstance(ent, dict) else None
        transit = state.get("transit") if isinstance(state, dict) else None
        if not isinstance(transit, dict) \
                or str(transit.get("phase") or "").casefold() == "docked":
            # Entity gone, or the director already docked it by hand --
            # the event is moot, not fireable.
            event_ops.append(("status", row["event_id"], "cancelled"))
            continue
        destination = str(payload.get("destination_room")
                          or transit.get("destination_room") or "")
        if destination:
            positions[eid] = destination
        transit["phase"] = "docked"
        transit.pop("eta_seconds", None)
        transit.pop("destination_room", None)
        event_ops.append(("status", row["event_id"], "fired"))
        fired += 1
        label = (ent.get("name") if isinstance(ent, dict) else "") or eid
        notices.append(
            f"{label} has arrived at "
            f"{destination or 'its destination'} and is docked there."
        )

    return event_ops, notices, {"fired": fired, "news_fired": news_fired}, \
        pending_entity_ids


def _schedule_new_arrivals(scene, elapsed, frame_id, pending_entity_ids,
                           chat_id, turn_id, turn_idx):
    """Pass (b): any entity whose transit state carries eta_seconds +
    destination_room and has no pending event yet gets a deterministic
    arrival event (stable id, so a rerun cannot double-schedule)."""
    event_ops = []
    scheduled = 0
    entities = scene.get("entities") or {}
    positions = scene.get("positions") or {}

    for eid, ent in entities.items():
        if not isinstance(ent, dict):
            continue
        state = ent.get("state")
        transit = state.get("transit") if isinstance(state, dict) else None
        if not isinstance(transit, dict):
            continue
        try:
            eta = float(transit.get("eta_seconds"))
        except (TypeError, ValueError):
            continue
        destination = str(transit.get("destination_room") or "")
        if eta <= 0 or not destination or str(eid) in pending_entity_ids:
            continue
        event_id = stable_event_key(
            "transit_arrival", chat_id, frame_id, eid, turn_id)
        event_ops.append(("schedule", {
            "event_id": event_id,
            "chat_id": chat_id,
            "due_at": elapsed + eta,
            "kind": "transit_arrival",
            "location_id": positions.get(eid),
            "payload": json.dumps({"entity_id": eid,
                                   "destination_room": destination,
                                   "frame_id": frame_id},
                                  ensure_ascii=False),
            "seed": f"transit:{chat_id}:{turn_idx}",
            "status": "pending",
        }))
        scheduled += 1

    return event_ops, scheduled


def _expire_conditions(conditions, elapsed):
    """Pass (c): active conditions whose expires_at has passed on this
    frame's clock. world_conditions is chat-scoped (no frame column); the
    committing frame's clock is used, matching how started_at is written."""
    event_ops = []
    for cond in conditions or []:
        expires = cond.get("expires_at")
        if expires is not None and float(expires) <= elapsed:
            event_ops.append(("expire_condition", cond["condition_id"]))
    return event_ops


def mechanics_sweep(scene, clock, frame_id, pending, *,
                    conditions=(), prev_scene=None, chat_id=None,
                    turn_id=None, turn_idx=None, cast_names=(),
                    cast_changes=()):
    """Run the ordered passes (a)-(e). Returns (scene, event_ops, notices).

    scene is mutated in place and also returned; event_ops is the list of
    durable operations for the caller to apply inside its transaction:
        ("status", event_id, new_status)   -- scheduled_events row update
        ("schedule", row_dict)             -- scheduled_events upsert
        ("expire_condition", condition_id) -- world_conditions deactivate
    notices is the engine_notices list for this beat (overwritten every
    sweep, so notices self-expire after one beat).
    """
    elapsed = float((clock or {}).get("elapsed_seconds") or 0.0)

    # (a) fire due events for this frame.
    event_ops, notices, counts, pending_entity_ids = _fire_due_events(
        scene, elapsed, frame_id, pending or [])

    # (b) schedule new arrivals.
    schedule_ops, scheduled = _schedule_new_arrivals(
        scene, elapsed, frame_id, pending_entity_ids,
        chat_id, turn_id, turn_idx)
    event_ops.extend(schedule_ops)

    # (c) condition expiry.
    event_ops.extend(_expire_conditions(conditions, elapsed))

    # (d) dock-edge recompute: an arrival changed the inputs the dock-edge
    # rewrite derives doorways from; recompute before the scene persists.
    if counts["fired"]:
        apply_transit_dock_edges(scene)

    # (e) vehicle-zone / companion-carry inference (idempotent; also
    # applied at preparation time -- see the module docstring).
    if prev_scene is not None and chat_id is not None:
        infer_vehicle_zones(chat_id, frame_id, prev_scene, scene)
        infer_companion_carry(chat_id, frame_id, prev_scene, scene,
                              list(cast_names), list(cast_changes or []))

    return scene, event_ops, notices
