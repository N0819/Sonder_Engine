"""Deterministic mechanics sweep (movement/space Phase 2, item 3).

One ordered orchestration of every deterministic mechanical follow-through
that used to be scattered across commit_transit_sweep's inline body and
prepare_scene_commit's tail:

    (a) fire due scheduled_events for THIS frame (transit_arrival moves
        the entity and docks it; news_arrival stages latency-gated
        awareness -- see the news note below);
    (b) schedule new arrivals from entity.state.transit eta declarations;
    (c1) fire due world_conditions ticks -- a condition that declares a
        cadence ACTS while it lasts (see the pass (c1) block below), and
        (c2) expire due world_conditions;
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
injecting knowledge directly into minds. Since Phase 3b, a news entry
that declares no latency gets one DERIVED from the audience's hop
distance to the destroyed root in the lorebook containment/presence
graph (news_latency_seconds below): near regions hear sooner, distant
ones later, and an audience matching no book waits a flat day.

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

from core import jobs
from world.spatial import apply_transit_dock_edges
from world.spatial_frames import infer_companion_carry, infer_vehicle_zones


def stable_event_key(*parts):
    """Deterministic id for events/memories: same inputs, same id, so a
    rerun cannot double-schedule or double-store."""
    raw = "\x1f".join(str(part or "") for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return f"event:{digest}"


# ---- The state_diff.time vocabulary, and its ONE reader ----
#
# `state_diff.time` is declared `Optional[dict]` (llm/schemas.py), so every
# key a model can spell validates and nothing downstream is obliged to look
# at any of them. That is the right declaration -- a typed submodel with
# extra="forbid" would THROW AWAY declared fiction time, which is the defect
# itself wearing a validator -- but it means the shape has to be owned
# somewhere, by one reader, or each caller invents its own subset.
#
# Three callers had invented three: the scene commit knew `end_seconds`
# alone, the sleep floor knew end/start/duration in that order, and the
# vitals tick knew `duration_seconds` alone. So a beat could end a sleep and
# not move the clock, or move the clock and not age a body.
#
# The spellings below are the ones the ENGINE ITSELF TEACHES, which is why
# tolerating them is not leniency. The resolve payload prints the clock to
# the model every beat as `simulation_clock: {elapsed_seconds, display,
# time_scale}` (agents/director_fanout.py), so a model that answers in the
# key it was just shown is echoing us. Measured over the live corpus
# 2026-08-25 (2,450 stored time diffs; these totals grow with play, the
# five-row set below does not): `display` 38x, `elapsed_seconds` 22x,
# `time_scale` 10x. Of the 22 `elapsed_seconds` diffs, 17 sit beside a full
# canonical shape with the value always inside [start_seconds, end_seconds]
# -- an absolute POSITION, not a duration, which is what fixes its reading
# -- and 5 carry no other numeric key at all and were dropped whole: chat 74
# turns 55 and 60, chat 88 turns 61, 64 and 66. In chat 88 turns 61 and 64
# claimed 1107 and 1266 against a clock standing at 1106.0, and turn 66
# claimed 7200 against 1136.0; not one of the three moved the clock or
# warned, and the only advance in that stretch came from turn 65's
# canonically spelled diff.
#
# The house pattern for a natural synonym is weather's `_SYNONYMS`:
# normalize what the fiction plainly meant, and report only what cannot be
# read at all. The prompts keep teaching ONE canonical spelling -- the
# tolerance lives here, not in the prompt, because a prompt naming two
# spellings encourages the second.

# Keys that ASSERT A TIME. A diff carrying one of these and getting no
# advance out of the reader has been refused, and a refusal is reportable.
TIME_CLAIM_KEYS = frozenset({
    "start_seconds",      # where the beat began on the story clock
    "duration_seconds",   # how long the beat took
    "end_seconds",        # where the beat ended: the canonical position
    "elapsed_seconds",    # the same position under the clock's own name
})

# Keys this vocabulary KNOWS but does not act on: the beat's own labelling
# of its time, plus the clock's metadata echoed back. Their presence is
# never a claim, so a diff carrying only these asserts no time and gets no
# warning (5 corpus rows carry `display` alone).
TIME_METADATA_KEYS = frozenset({
    "mode",               # 'action' | 'time_skip'
    "explicit",           # did the player ask for the skip
    "display_advance",    # the phrase a reader sees
    "display",            # the same phrase under the clock's own name
    "time_scale",         # the clock's own scale, echoed back
})

# Everything the vocabulary contains. A key outside it has no meaning to any
# reader in the engine; `tools/project_check.check_time_channel_vocabulary`
# holds the prompts and the shipped output examples to exactly this set.
TIME_DIFF_KEYS = TIME_CLAIM_KEYS | TIME_METADATA_KEYS


def clock_elapsed(clock):
    """Where the STORED simulation clock stands, from its own dict.

    The other half of the same ownership: `read_time_diff` knows the shape a
    beat's claim arrives in, and this knows the shape the clock is kept in,
    so neither the scene commit nor the memory commit has to spell
    `float((clock or {}).get("elapsed_seconds", 0.0) or 0.0)` for itself and
    drift. Missing, absent or unparseable reads 0.0 -- the story has not
    started. (`agents.director_floors._sleep_elapsed` deliberately does NOT
    use this: it returns None for an unreadable clock, because "the clock
    cannot say how long you have been under" is a different answer from
    "you have been under since zero".)
    """
    try:
        return float((clock or {}).get("elapsed_seconds", 0.0) or 0.0)
    except (TypeError, ValueError, AttributeError):
        return 0.0


def read_time_diff(prev_elapsed, time_diff):
    """What a `state_diff.time` block says about the story clock.

    Returns ``(elapsed_seconds, backwards, refused)``:

    * ``elapsed_seconds`` -- where the clock stands at the END of this beat.
    * ``backwards`` -- None, or ``(claimed, was)`` when the beat asserted a
      position EARLIER than the clock already held. TIME DOES NOT RUN
      BACKWARDS: such a beat advances by its own duration instead, because
      the elapsed time is the part the fiction actually asserted, and a
      model emitting `start_seconds: 0` every beat -- an easy and entirely
      natural reading of a field named "start" -- would otherwise reset the
      world to the length of its own beat, over and over.
    * ``refused`` -- sorted keys that made a time claim this reader could
      NOT act on, and empty whenever it did act. It is empty for a diff
      that asserts no time at all (`{"display": "later"}` says nothing about
      the clock and is not a refusal), and it is empty when a position
      parsed and merely happened to equal the clock. What it names is the
      real class: `{"start_seconds": 1200}` with no end and no duration,
      `{"end_seconds": "soon"}`, `{"seconds": 300}` -- a beat that meant to
      move time and got silence. Keyed on whether the reader ACTED, not on
      whether the number changed, because those differ in both directions.

    A position may arrive under either name the engine uses for it, and the
    canonical `end_seconds` outranks the synonym when both are present (17
    corpus rows carry both; the synonym is the mid-beat position there). A
    diff carrying ONLY a duration is an advance from where the clock stood,
    not silence -- it asserted a span, and a span is a claim.
    """
    try:
        was = float(prev_elapsed or 0.0)
    except (TypeError, ValueError):
        was = 0.0
    td = time_diff if isinstance(time_diff, dict) else {}

    duration = 0.0
    duration_claimed = False
    if "duration_seconds" in td:
        try:
            duration = max(0.0, float(td.get("duration_seconds") or 0.0))
            duration_claimed = True
        except (TypeError, ValueError):
            duration = 0.0

    claim = None
    for key in ("end_seconds", "elapsed_seconds"):
        if td.get(key) is None:
            continue
        try:
            claim = float(td[key])
            break
        except (TypeError, ValueError):
            claim = None

    acted = claim is not None or duration_claimed
    refused = [] if acted else sorted(
        k for k in td if k in TIME_CLAIM_KEYS or k not in TIME_DIFF_KEYS)

    if claim is None:
        return (was + duration if duration_claimed else was), None, refused
    if claim < was:
        return was + duration, (claim, was), refused
    return claim, None, refused


def time_diff_display(time_diff):
    """The reader-facing phrase a beat gave its own passage of time, or ""
    when it gave none. `display_advance` is the taught spelling; `display`
    is the clock's own key echoed back (38 corpus rows).

    The canonical key wins BY PRESENCE, not by truthiness: a beat that
    spells `display_advance: ""` has said this beat carries no phrase, and
    an explicit clear must outrank a synonym rather than be overridden by
    it. Canonical rows constantly carry the empty string.
    """
    td = time_diff if isinstance(time_diff, dict) else {}
    if "display_advance" in td:
        return td["display_advance"] or ""
    return td.get("display") or ""


def time_diff_duration(time_diff):
    """How long a beat took, in story seconds, from the diff ALONE.

    `duration_seconds` when it parses, else the span between a parseable
    start and end. An absolute-only diff reads 0 here on purpose: this seam
    (the vitals tick inside `merge_scene_with_diff`) is handed no previous
    clock to subtract from, so the honest answer to "how long was this
    beat" is "this block does not say". Under-ageing a body is recoverable;
    ageing it by the whole elapsed history of the story is not. Registered
    as a residual in docs/UNBUILT.md 1.83.
    """
    td = time_diff if isinstance(time_diff, dict) else {}
    if "duration_seconds" in td:
        try:
            return max(0.0, float(td.get("duration_seconds") or 0.0))
        except (TypeError, ValueError):
            pass
    try:
        return max(0.0, float(td["end_seconds"]) - float(td["start_seconds"]))
    except (KeyError, TypeError, ValueError):
        return 0.0


# News latency by distance (movement/space Phase 3b): when a destruction
# declaration names a news audience WITHOUT an explicit latency_seconds,
# the minting path (commit._prepare_destruction) derives one from the
# audience's hop distance to the destroyed root in the lorebook
# containment/presence graph (parent_id + currently_within edges,
# undirected BFS). One hop = one hour of story time; an audience that
# matches no book, or is unreachable from the root, waits a flat day. A
# declared latency always wins -- the Director owns the causal narrative;
# this is only the deterministic default that makes near regions hear
# sooner and distant ones later.
NEWS_HOP_LATENCY_SECONDS = 3600.0
NEWS_UNREACHABLE_LATENCY_SECONDS = 86400.0


def news_latency_seconds(distance_hops):
    """Deterministic derived news latency: graph hops * one hour; None
    (no matching book / unreachable) -> one day."""
    if distance_hops is None:
        return NEWS_UNREACHABLE_LATENCY_SECONDS
    try:
        hops = max(0.0, float(distance_hops))
    except (TypeError, ValueError):
        return NEWS_UNREACHABLE_LATENCY_SECONDS
    return hops * NEWS_HOP_LATENCY_SECONDS


def _payload_of(row):
    """A row's payload as a dict. Already-parsed payloads pass through, so a
    caller that hands rows straight out of SQL and one that builds them in
    memory reach the same code -- the sweep owns the shape either way."""
    raw = row.get("payload")
    if isinstance(raw, dict):
        return raw
    try:
        payload = json.loads(raw or "{}")
    except Exception:
        payload = {}
    return payload if isinstance(payload, dict) else {}


def _fire_due_events(scene, elapsed, frame_id, pending, *, turn_idx=None,
                     player_room=None):
    """Pass (a). Returns (event_ops, notices, counts, pending_entity_ids).

    pending rows arrive in due_at order (the caller's query) and each is
    frame-gated by the frame_id in its payload: scheduled_events has no
    frame column while simulation clocks are frame-scoped, so an event
    minted in one frame must never fire against another frame's clock.

    ``consequence`` rows (living_world.mint_consequences) fire the same
    deterministic way and their firing is LAYER-1 FACT — it happened
    whether or not anyone was there. The notice is the only knowledge
    surface, and it is emitted ONLY when the player is standing at the
    fuse's location as it lands (walking in on it); everywhere else the
    fired row waits to be read at contact (residue, gap skeleton). That
    presence gate is the §0.2 firewall: an event elsewhere is never told,
    only encountered.
    """
    event_ops = []
    notices = []
    fired = news_fired = consequences_fired = 0
    pending_entity_ids = set()
    entities = scene.get("entities") or {}
    positions = scene.setdefault("positions", {})

    for row in pending:
        payload = _payload_of(row)
        if row.get("kind") == "consequence":
            if payload.get("frame_id") != frame_id or row["due_at"] > elapsed:
                continue
            if jobs.story_rewound_past(payload.get("base_turn"), turn_idx):
                # The base-revision check at fire time: a fuse minted from a
                # turn the story no longer contains describes a future whose
                # cause un-happened. Cancelled loudly, never fired — the
                # land_profile_ticks discipline, applied to the delay line.
                event_ops.append(("status", row["event_id"], "cancelled"))
                continue
            event_ops.append(("status", row["event_id"], "fired"))
            consequences_fired += 1
            if player_room and str(payload.get("where") or "") == \
                    str(player_room):
                notices.append(
                    "Falling due here, now: "
                    f"{payload.get('what') or 'a scheduled consequence'} "
                    "(stage it as present state resolving in front of the "
                    "party)."
                )
            continue
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
        if payload.get("frame_id") != frame_id:
            continue
        if row["due_at"] > elapsed:
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

    return event_ops, notices, \
        {"fired": fired, "news_fired": news_fired,
         "consequences_fired": consequences_fired}, \
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
        if str(transit.get("phase") or "").strip().casefold() == "docked":
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


# ---- Conditions that ACT while they last (pass (c1)) ----
#
# `world_conditions` shipped with a `next_tick` column and an
# `idx_world_conditions_due` index over it, and nothing ever wrote either.
# Measured read-only on the author's engine.db 2026-08-25: 444 rows across
# 50 chats, `next_tick` NULL in all 444, while 131 ACTIVE rows carried an
# authored `tick_interval_seconds` (0, 5, 10, 15, 20, 30, 45, 60, 300) that
# no reader in the engine consumed. The body specialist's own sheet asks for
# the field; llm/schemas.py stated the open question in its own comment --
# build the due-tick sweep, or drop the field, the column and the index.
# This pass is the build, and it runs BEFORE expiry so a condition's last
# due tick lands before the clock closes it.
#
# WHAT A TICK MAY DO IS DELIBERATELY SMALL, because the engine must not learn
# what any particular condition MEANS -- 106 distinct `kind` strings are
# active in the corpus, so `kind` is open vocabulary and a per-kind effects
# table would be an instance fix wearing a general syntax. A tick may move a
# survival vital the scene ALREADY tracks, and it may re-announce one clause
# as an engine notice. Everything else a condition does stays the Director's.
#
# Cadence is owned by THIS pass, never by the writer: a row is scheduled from
# the clock the sweep first sees it on. Every existing row meets this
# uninitialized, and an initialization that also fired would charge each of
# them for the whole of the story that happened before the sweep existed.

#: Most fires one row may take in one beat. Not a rate limit on fiction --
#: a rate limit on arithmetic, for a five-second cadence meeting a time skip.
_TICK_FIRE_CAP = 500
#: Most one tick may move one vital. A model authoring `-1.0` against a
#: five-second cadence would empty a body inside one beat; the CADENCE is how
#: a condition gets to be lethal, not the size of a single step.
_TICK_VITAL_STEP_CAP = 0.25
#: Most tick notices one sweep may stage. The sibling of
#: `director_floors._CONDITIONS_VIEW_CAP` (40) and set lower on purpose: the
#: view is a ledger the Director reads to ACT on, and these are the world
#: saying the same sentence again. One corpus chat carries 24 active rows
#: (engine.db 2026-08-25), so an uncapped sweep can spend a beat's whole
#: notice budget on ongoing processes and crowd out what just happened.
_TICK_NOTICE_CAP = 8


def _condition_field(payload, key):
    """A condition field, spelled at the payload root or inside `state`.

    Both spellings are live across the table (`story.scene._condition_state`
    tolerates the same pair), so a reader that knows only one of them is a
    reader that silently ignores half the rows.

    A root spelling present but NULL is silence, not an answer: a model that
    emits the whole field list with the ones it has nothing to say about left
    null would otherwise mask the value it did fill in under `state`. Latent
    today (0 of 444 corpus rows are in that shape, measured 2026-08-25), and
    the docstring above is the reason to close it anyway -- the failure it
    describes is exactly a reader ignoring the half of the row that speaks.
    """
    value = payload.get(key)
    if value is not None:
        return value
    state = payload.get("state")
    if isinstance(state, dict) and state.get(key) is not None:
        return state.get(key)
    return value


def _tick_interval(payload):
    """The declared cadence in simulation seconds, or None when there is not
    one. Zero is NOT "tick constantly" -- 48 of the 131 interval-bearing
    corpus rows spell `0`, the commonest authored value, and a field filled
    in with nothing is not a cadence (it is also a divisor of zero)."""
    try:
        interval = float(_condition_field(payload, "tick_interval_seconds"))
    except (TypeError, ValueError):
        return None
    if interval <= 0 or interval != interval or interval in (
            float("inf"), float("-inf")):
        return None
    return interval


def _tick_spec(payload):
    """What one tick of this condition DOES: (vitals_deltas, percept).

    `vitals` is restricted to the four keys `world.survival.VITALS` defines
    and each per-tick step is clamped -- the guard SUBTRACTS, so a vital the
    ledger does not track is dropped rather than invented. `percept` is one
    short clause the world keeps saying while the process runs.
    """
    from world.survival import VITALS

    block = _condition_field(payload, "tick")
    if not isinstance(block, dict):
        return {}, ""
    deltas = {}
    raw = block.get("vitals")
    for vital, value in (raw.items() if isinstance(raw, dict) else ()):
        name = str(vital or "").strip().casefold()
        if name not in VITALS:
            continue
        try:
            delta = float(value)
        except (TypeError, ValueError):
            continue
        if delta != delta or delta in (float("inf"), float("-inf")):
            continue
        deltas[name] = max(-_TICK_VITAL_STEP_CAP,
                           min(delta, _TICK_VITAL_STEP_CAP))
    return deltas, str(block.get("percept") or "").strip()


def _tick_subjects(scene, cond):
    """Whose bodies one ticking condition acts on.

    The row's own subject, and only that. This is the SINGLE place a ticking
    condition's subject is resolved to bodies, so a later landing that lets a
    PLACE carry a ticking condition has one function to change and nothing in
    the firing, the batching, the clamps or the op family moves. Nothing is
    declared for that here: a seam gets its fields when its consumer arrives.
    """
    subject = str(cond.get("subject_id") or "").strip()
    return [subject] if subject else []


def _vitals_entry_key(table, name):
    """The key under which `name`'s vitals are stored, or None. Casefolded,
    matching `survival.vitals_of` -- the table is keyed by display name."""
    target = str(name or "").strip().casefold()
    if not target:
        return None
    for key, record in table.items():
        if str(key).strip().casefold() == target and isinstance(record, dict):
            return key
    return None


def _tick_conditions(scene, conditions, elapsed):
    """Pass (c1). Returns (event_ops, notices).

    One op shape: ("tick_condition", condition_id, new_next_tick), applied by
    the commit domain as the `next_tick` column write the table was built for.
    """
    from world.survival import _stored_vitals

    event_ops, notices, unnamed = [], [], []
    for cond in conditions or []:
        payload = _payload_of(cond)
        interval = _tick_interval(payload)
        if interval is None:
            continue
        cid = cond.get("condition_id")
        raw_next = cond.get("next_tick")
        if raw_next is None:
            event_ops.append(("tick_condition", cid, elapsed + interval))
            continue
        try:
            t = float(raw_next)
        except (TypeError, ValueError):
            event_ops.append(("tick_condition", cid, elapsed + interval))
            continue
        try:
            expires = None if cond.get("expires_at") is None \
                else float(cond["expires_at"])
        except (TypeError, ValueError):
            expires = None

        fires = 0
        while t <= elapsed and fires < _TICK_FIRE_CAP:
            if expires is not None and t >= expires:
                break
            fires += 1
            t += interval
        if not fires:
            continue
        if fires >= _TICK_FIRE_CAP and t <= elapsed:
            # THE CAP CATCHES UP; IT DOES NOT LAG. The story clock is free to
            # jump hours in one beat (`read_time_diff`, alpha 9.8.2), so
            # carrying the capped cadence forward as next_tick + fires*
            # interval would leave the row permanently behind the clock and
            # re-hit the cap on every beat for the rest of the story.
            t = elapsed + interval
        event_ops.append(("tick_condition", cid, t))

        deltas, percept = _tick_spec(payload)
        table = scene.get("vitals") if isinstance(scene, dict) else None
        moved, missing = [], []
        for subject in _tick_subjects(scene, cond):
            if not deltas:
                break
            if not isinstance(table, dict) or not table:
                # ABSENCE IS THE OFF SWITCH (world/survival.py: "nothing
                # creates the table but an explicit write"). A tick may MOVE
                # a vital; it may never CREATE the ledger. 131 active corpus
                # rows carry intervals, so a seeding tick would have started
                # a hunger clock in every story that never enabled survival.
                # Dropped in silence: the setting being off is not a failure.
                break
            key = _vitals_entry_key(table, subject)
            if key is None:
                # The ledger EXISTS and this subject is not in it -- a real
                # miss worth saying, not a setting. Condition subjects are
                # free model text and some rows carry scene uids
                # (docs/UNBUILT.md 1.65). A mechanism that silently never
                # fires is this table's whole failure history.
                missing.append(subject)
                continue
            record = table[key]
            current = _stored_vitals(record)
            for vital, delta in deltas.items():
                before = current.get(vital, 0.0)
                after = max(0.0, min(before + delta * fires, 1.0))
                record[vital] = after
                if after != before:
                    moved.append(f"{subject} {vital} {after - before:+.2f}")

        label = str(cond.get("subject_id") or cond.get("kind") or "").strip()
        parts = [p for p in (percept, ", ".join(moved)) if p]
        if parts:
            # ONE notice per condition per sweep however many times it fired:
            # a clause repeated four times is the same fact four times.
            notices.append(
                f"Ongoing ({label}, {fires}x): " + "; ".join(parts))
        for subject in missing:
            if subject not in unnamed:
                unnamed.append(subject)

    if len(notices) > _TICK_NOTICE_CAP:
        # Truncated, and SAID. A silently dropped notice is a process the
        # world stopped mentioning while it kept running.
        dropped = len(notices) - _TICK_NOTICE_CAP
        notices = notices[:_TICK_NOTICE_CAP]
        notices.append(
            f"Ongoing: {dropped} further standing condition"
            f"{'s are' if dropped != 1 else ' is'} also acting this beat, "
            "not listed here.")
    if unnamed:
        # ONE line per sweep, not one per row. This notice restages every
        # beat until the Director re-emits with a subject the ledger names,
        # so N rows naming the same absent body is that body's name repeated
        # N times every beat for the rest of the story.
        notices.append(
            "Ongoing: standing conditions declare vitals changes for "
            + ", ".join(unnamed)
            + ", and no body of that name is in this scene's vitals ledger "
            "-- name the subject as the scene names them, or the change goes "
            "nowhere.")

    return event_ops, notices


def _expire_conditions(conditions, elapsed):
    """Pass (c2): active conditions whose expires_at has passed on this
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
                    cast_changes=(), player_room=None):
    """Run the ordered passes (a)-(e).

    Returns (scene, event_ops, notices, counts).

    scene is mutated in place and also returned; event_ops is the list of
    durable operations for the caller to apply inside its transaction:
        ("status", event_id, new_status)   -- scheduled_events row update
        ("schedule", row_dict)             -- scheduled_events upsert
        ("expire_condition", condition_id) -- world_conditions deactivate
        ("tick_condition", condition_id, next_tick) -- world_conditions
                                              cadence advance (pass (c1))
    notices is the engine_notices list for this beat (overwritten every
    sweep, so notices self-expire after one beat).

    counts is what pass (a) fired, by kind: `fired` (transit arrivals),
    `news_fired`, `consequences_fired`. Returned rather than kept private
    because the commit domain reports these numbers, and a caller that has to
    rebuild them from `event_ops` is writing a second implementation of a
    count this function already has -- which is what it did until WORLD-F3.
    `scheduled`, `expired` and `ticked` are NOT here: those are counts of ops
    the caller applies, and belong to whoever applies them.
    """
    elapsed = float((clock or {}).get("elapsed_seconds") or 0.0)

    # (a) fire due events for this frame.
    event_ops, notices, counts, pending_entity_ids = _fire_due_events(
        scene, elapsed, frame_id, pending or [],
        turn_idx=turn_idx, player_room=player_room)

    # (b) schedule new arrivals.
    schedule_ops, scheduled = _schedule_new_arrivals(
        scene, elapsed, frame_id, pending_entity_ids,
        chat_id, turn_id, turn_idx)
    event_ops.extend(schedule_ops)

    # (c1) conditions that act while they last, then (c2) condition expiry.
    # Ticks FIRST so a row's last due tick lands before the clock closes it.
    tick_ops, tick_notices = _tick_conditions(scene, conditions, elapsed)
    event_ops.extend(tick_ops)
    notices.extend(tick_notices)
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

    return scene, event_ops, notices, counts
