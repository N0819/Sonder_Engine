"""The off-screen epoch: when the world crossed a boundary, and which beat this is.

One commit domain (`persist/commit.commit_offscreen_epoch`), deterministic and
free. Every beat it stamps a stable BEAT identity on the frame-scoped
`offscreen_epoch` row -- the token the Charter advances on and is idempotent
against (`charter_runtime.schedule_charter_ticks`, `land_snapshot`) -- and
when a beat crosses a boundary (the opening, a change of top-level location, a
crossed in-world hour, a due event: `epoch_reasons`) it records an EPOCH beside
it. The row rides the ordinary checkpoint, branch key remap and portable
archive, so neither needs a serializer of its own.

WHAT USED TO LIVE HERE, AND WHAT REPLACED IT. This module carried the paid
off-screen tiers of the living world: an importance x distance spend function,
a seeded `stochastic` tick draw, `reactive` plan stages for the antagonist
ladder, an out-of-band `profile` tick and the `character_agent` rung -- about
1,700 lines. They were unreachable from 7140b9cc (2026-09-20), when the
approach ladder was emptied and `dialogue_config` forced the actor cap to 0,
and the owner's database never stored a batch from any of them (review
2026-11-01, world_offscreen_time F11). They were RETIRED on 2026-11-01 on the
owner's ruling -- "living world is supposed to be superseded by charter and
writers room" -- and deleted rather than kept switched off. What does their
work now: the Charter moves an unwatched population every beat
(`world/charter_*.py`), the Writers' Room plans what happens out of view
(`agents/story_planner.py`), and a character who walks out of reach lives a
thread of their own (`agents/offscreen_beat.py`), from their own perception and
their own private state. `docs/design/DESIGN_OFFSCREEN_SUPERSEDED.md` is the
argument; `docs/guides/LIVING_WORLD.md` says what remains.

`offscreen_log` and `offscreen_plans` stay frame-scoped world keys
(`core/db.FRAME_SCOPED_WORLD_KEYS`): bubbles append to the log and
`world/gaps.py` reads its legacy batches, and an old story's plan rows still
travel with a branch. Nothing writes a plan any more.
"""

from __future__ import annotations

import hashlib
import json

#: One epoch per crossed in-world hour, plus top-level location changes and
#: due-event fires. A conversation can consume many turns and only seconds, so
#: a boundary counted in turns would price story length rather than dramatic
#: density. Coarse on purpose: a trigger, not a claim that every setting
#: experiences time in one-hour narrative units.
EPOCH_SECONDS = 60 * 60
EPOCH_KEY = "offscreen_epoch"


# ---------------------------------------------------------------------------
# The shared world epoch. Primary state, run inside commit_all's transaction.
# ---------------------------------------------------------------------------

def _as_seconds(clock):
    try:
        return max(0.0, float((clock or {}).get("elapsed_seconds") or 0.0))
    except (TypeError, ValueError, AttributeError):
        return 0.0


def epoch_reasons(*, turn_idx, previous_scene, scene, previous_clock, clock,
                  transit_result):
    """Return the canonical reasons this beat creates one epoch opportunity.

    Pure over the pre/post scene and clock plus the already-committed mechanics
    result. Multiple causes in one beat are one epoch: one world edge, one id.
    A pre-existing story that first encounters this code is baselined rather
    than given a retroactive epoch by a migration artifact.
    """
    reasons = []
    try:
        idx = int(turn_idx)
    except (TypeError, ValueError):
        idx = -1

    before_scene = previous_scene if isinstance(previous_scene, dict) else {}
    after_scene = scene if isinstance(scene, dict) else {}
    before_location = str(before_scene.get("location") or "").strip()
    after_location = str(after_scene.get("location") or "").strip()

    if idx == 0 and not before_scene:
        reasons.append("opening")
    if before_location and after_location and before_location != after_location:
        reasons.append("location")

    before_bucket = int(_as_seconds(previous_clock) // EPOCH_SECONDS)
    after_bucket = int(_as_seconds(clock) // EPOCH_SECONDS)
    if after_bucket > before_bucket:
        reasons.append("time")

    mechanics = transit_result if isinstance(transit_result, dict) else {}
    due_count = sum(
        max(0, int(mechanics.get(key) or 0))
        for key in ("fired", "news_fired", "consequences_fired", "expired")
        if str(mechanics.get(key) or "0").lstrip("-").isdigit()
    )
    if due_count:
        reasons.append("due_event")
    return reasons


def _epoch_id(cid, frame_id, turn_idx, elapsed, location, reasons):
    material = json.dumps(
        [int(cid), frame_id, int(turn_idx), round(float(elapsed), 3),
         str(location or ""), list(reasons)],
        ensure_ascii=False, separators=(",", ":"),
    )
    return "epoch_" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:20]


def _beat_id(cid, frame_id, turn_idx, elapsed, location):
    """THIS BEAT'S STABLE IDENTITY, minted the way an epoch's already is.

    Same material and the same hash as `_epoch_id` under its own prefix,
    minus `reasons`: an epoch is a thing that HAPPENED and is named by its
    causes, a beat is simply where the story now stands. Reused rather than
    invented because the idempotence it buys is the same idempotence -- a
    reroll or a rerun-from-stage that lands the same clock at the same place
    is the same beat, and `charter_runtime.advance_snapshot` refuses to
    advance a charter twice for one token.
    """
    material = json.dumps(
        [int(cid), frame_id, int(turn_idx), round(float(elapsed), 3),
         str(location or "")],
        ensure_ascii=False, separators=(",", ":"),
    )
    return "beat_" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:20]


def _beat_context(prepared):
    """Which wall-clock budget this beat's charter advance runs under.

    Decided by WHAT THE BEAT IS, never by how much elapsed time happens to
    have accumulated -- otherwise an ordinary beat after a long real-world
    pause would silently take the generous budget. The beat's own resolve
    says so: `state_diff.time.mode`, already in the time vocabulary
    (`world/mechanics.TIME_METADATA_KEYS`) as the beat's labelling of its
    own passage. The budgets themselves are
    `charter_runtime.CHARTER_BUDGET_SECONDS`.
    """
    diff = (prepared or {}).get("diff")
    block = diff.get("time") if isinstance(diff, dict) else None
    mode = str((block or {}).get("mode") or "").strip().casefold() \
        if isinstance(block, dict) else ""
    return "time_skip" if mode == "time_skip" else "beat"


def advance_epoch(ctx, prepared_scene, transit_result):
    """Commit this beat's frame-scoped off-screen epoch and beat identity.

    A commit domain: it performs no provider call and runs under
    `commit_all`'s outer transaction, so its world-KV row is captured by the
    ordinary pre-turn checkpoint, branch key remap and portable archive paths
    without a table-specific serializer.
    """
    from core.db import wget, wset

    cid = ctx.chat.id
    frame_id = ctx.turn.frame_id
    turn_idx = ctx.turn.idx
    prepared = prepared_scene if isinstance(prepared_scene, dict) else {}
    scene = prepared.get("scene") or {}
    previous_scene = prepared.get("prev_scene") or {}
    previous_clock = prepared.get("prev_clock") or {}
    clock = prepared.get("clock") or wget(cid, "simulation_clock", {}) or {}
    elapsed = _as_seconds(clock)
    location = str(scene.get("location") or "").strip()
    reasons = epoch_reasons(
        turn_idx=turn_idx, previous_scene=previous_scene, scene=scene,
        previous_clock=previous_clock, clock=clock,
        transit_result=transit_result,
    )

    # THE BEAT, WHICH IS NOT THE EPOCH. Stamped on this row every beat --
    # opportunity or not, bootstrapped or not -- because the Charter's
    # deterministic walk advances every beat by that beat's own elapsed time
    # and needs a stable token to be idempotent on
    # (`charter_runtime.schedule_charter_ticks`). It rides inside
    # `offscreen_epoch` rather than in a key of its own so it is already
    # covered by the checkpoint, branch remap and portable archive this row
    # is in.
    beat = {
        "beat_id": _beat_id(cid, frame_id, turn_idx, elapsed, location),
        "beat_turn": int(turn_idx),
        "beat_elapsed_seconds": elapsed,
        "beat_context": _beat_context(prepared),
    }

    old = wget(cid, EPOCH_KEY, {}) or {}
    # Upgrade baseline: an old story has no epoch record. Do not invent one
    # retroactive epoch merely because new code first saw it, but do preserve
    # a real boundary crossed by this very beat.
    bootstrapped = not isinstance(old, dict) or not old
    if bootstrapped and int(turn_idx) > 0 and not reasons:
        state = {
            "sequence": 0, "epoch_id": "", "turn": int(turn_idx),
            "elapsed_seconds": elapsed,
            "time_bucket": int(elapsed // EPOCH_SECONDS),
            "location": location, "reasons": ["baseline"],
            **beat,
        }
        wset(cid, EPOCH_KEY, state)
        return {"opportunity": False, "bootstrapped": True,
                "reasons": ["baseline"], **state}

    if not reasons:
        # No epoch, but still a beat. The stored row keeps whatever epoch it
        # already carried -- a boundary that was not crossed is not recorded
        # -- and gains this beat's identity beside it.
        state = {**(old if isinstance(old, dict) else {}), **beat}
        wset(cid, EPOCH_KEY, state)
        return {"opportunity": False, "bootstrapped": bootstrapped,
                "reasons": [], "epoch_id": "", **beat}

    try:
        previous_sequence = max(0, int((old or {}).get("sequence") or 0))
    except (TypeError, ValueError):
        # A hand-edited/legacy world key must not make the whole turn
        # uncommittable. The stable epoch id still supplies idempotence.
        previous_sequence = 0
    state = {
        "sequence": previous_sequence + 1,
        "epoch_id": _epoch_id(
            cid, frame_id, turn_idx, elapsed, location, reasons),
        "turn": int(turn_idx),
        "elapsed_seconds": elapsed,
        "time_bucket": int(elapsed // EPOCH_SECONDS),
        "location": location, "reasons": reasons,
        **beat,
    }
    wset(cid, EPOCH_KEY, state)
    return {"opportunity": True, "bootstrapped": bootstrapped, **state}
