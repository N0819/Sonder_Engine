"""Paradox detection, escalation, and mode-pluggable consequence, built on
top of frames.py's diegetic-time model.

A time-travel campaign can register FIXED POINTS -- deterministic
predicates about an entity's existence at a given diegetic frame that the
player/Director have declared load-bearing (a fixed point being altered
is the classic "grandfather paradox" shape, Doctor Who's "Father's Day"
being the reference beat). Ordinary changes to the past that touch no
fixed point are absorbed by the timeline with no drama at all -- that is
the DEFAULT, safe path (see frames.py's docstring and memory.py's
provenance model: a time-displaced encounter is just an ordinary private
memory unless it actually contradicts a declared anchor).

The consequence of a violated fixed point is deliberately NOT hard-coded
to one dramatization (a hunting monster is one show's specific device,
not a law of paradox). What's genuinely consequence-agnostic -- and is
the actual substrate here -- is:
  - detection: a deterministic predicate check against committed state
  - escalation: a severity scalar climbing from the diegetic clock while
    the paradox is unresolved, with a ceiling
  - resolution: the anchor predicate re-satisfied, checked every commit

What varies per campaign is what severity DOES, chosen via
`world.paradox_policy.mode`:
  - "dread": no mechanical consequence at all -- payload/narrative
    awareness only. Resolution is pure roleplay. (Explicitly valid: a
    consequence layer that can't be configured down to nothing was
    never a layer.)
  - "hazard": an environmental wound -- sensory wrongness escalating to
    room consumption, riding the scene's own overlay/entity machinery.
    The recommended default: it exercises this engine's actual
    strengths (scene state filtered through senses and perception)
    without depending on a well-authored antagonist.
  - "toll": cost localizes to travelers physically inside the wound --
    deterministic decay of their OWN memory confidence for rows from
    their origin frame. This engine's one genuinely native effect: other
    media hand-wave "reality is coming apart," this can make it a real,
    measurable epistemic fact via the existing confidence column.
  - "warden": a hunting entity, spawned and moved as an ordinary scene
    entity (ordinary spatial/reaction/resolution machinery treats it as
    real with no new perception code). Requires the user to have (or the
    Director to generate) an actual antagonist -- the modes below it are
    cheaper because they don't depend on one being well-written.
  - "bureau": enforcement NPCs -- mechanically identical to "warden"
    (ordinary cast entities) but framed as negotiable rather than
    predatory; resolution can be a settlement, not only restoration.
    Requires the user to attach/author the enforcement characters.

Onset is always "wound" in this minimal slice: the paradox is detected
AFTER a turn commits a change that violates an anchor, never blocked
pre-emptively. A pre-commit "this action cannot complete" deflection
(the Novikov/self-consistency shape) is real future scope, not attempted
here -- flagged in Design.md rather than half-built.
"""

from __future__ import annotations

import time as _time

from db import active_frame_id, q, qi, transaction, wget, wset
from frames import get_frame

MODES = ("dread", "hazard", "toll", "warden", "bureau")
DEFAULT_MODE = "hazard"
DEFAULT_TOLL_IN_RADIUS = True

# Severity climbs by (elapsed diegetic seconds since onset) / ESCALATION_SECONDS,
# scaled by the policy's escalation_rate. Small enough that a scene playing
# out over real in-fiction minutes-to-hours produces a few stage jumps
# rather than an instant maximum or an imperceptible crawl.
ESCALATION_SECONDS = 900.0
STAGE_THRESHOLDS = (0.0, 0.25, 0.5, 0.75, 1.0)

# "hazard" mode's own docstring promises "sensory wrongness escalating to
# room consumption" -- the room-consumption half was implemented
# (paradox_consumed flag below) but nothing ever read that flag: not
# perception.py, not narration.py, not director.py's payload. A live
# playtest confirmed the paradox escalates and marks rooms consumed
# entirely silently, invisible to the player unless an operator inspects
# the DB directly. Fixed the cheap way -- reuse the EXISTING room.notes
# field that perception_act/perception_outcome already read verbatim
# into room_notes, rather than adding a new payload field anywhere. The
# marker text is deliberately distinctive so _restore_consumed can strip
# exactly this and nothing else on resolution.
_HAZARD_WOUND_NOTE = (
    " Something about this place feels wrong now -- thin, unstable, as if "
    "reality itself is straining to reject an impossibility that happened here."
)


def get_policy(chat_id):
    stored = wget(chat_id, "paradox_policy", {}) or {}
    mode = stored.get("mode")
    return {
        "mode": mode if mode in MODES else DEFAULT_MODE,
        "escalation_rate": float(stored.get("escalation_rate", 1.0)),
        "toll_in_radius": bool(stored.get("toll_in_radius", DEFAULT_TOLL_IN_RADIUS)),
    }


def set_policy(chat_id, *, mode=None, escalation_rate=None, toll_in_radius=None):
    policy = get_policy(chat_id)
    if mode is not None:
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        policy["mode"] = mode
    if escalation_rate is not None:
        policy["escalation_rate"] = max(0.1, float(escalation_rate))
    if toll_in_radius is not None:
        policy["toll_in_radius"] = bool(toll_in_radius)
    wset(chat_id, "paradox_policy", policy)
    return policy


# ---- Fixed points ----

def fixed_points(chat_id):
    return wget(chat_id, "fixed_points", []) or []


def add_fixed_point(chat_id, *, entity_id, frame_id, required_exists, label, mode=None):
    """Declares that `entity_id` must (required_exists=True) or must not
    (required_exists=False) exist as of `frame_id`. Existence is checked
    as simple row presence in world_entities -- commit_world_entities
    already deletes a row outright on `remove_entities`, there is no
    "retired" flag actually written anywhere to check instead."""
    if frame_id is not None and get_frame(frame_id) is None:
        raise ValueError(f"frame {frame_id} not found")
    if mode is not None and mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    points = fixed_points(chat_id)
    anchor_id = (max((p["anchor_id"] for p in points), default=0)) + 1
    points.append({
        "anchor_id": anchor_id, "entity_id": str(entity_id), "frame_id": frame_id,
        "required_exists": bool(required_exists), "label": str(label),
        "mode": mode, "created": _time.time(),
    })
    wset(chat_id, "fixed_points", points)
    return anchor_id


def remove_fixed_point(chat_id, anchor_id):
    points = [p for p in fixed_points(chat_id) if p["anchor_id"] != anchor_id]
    wset(chat_id, "fixed_points", points)


def _entity_exists(chat_id, entity_id):
    return bool(q(
        "SELECT 1 FROM world_entities WHERE chat_id=? AND entity_id=?",
        (chat_id, entity_id), one=True,
    ))


def _anchor_satisfied(chat_id, anchor):
    return _entity_exists(chat_id, anchor["entity_id"]) == anchor["required_exists"]


# ---- Paradox state ----

def _frame_key(frame_id):
    return "present" if frame_id is None else str(frame_id)


def get_all_paradoxes(chat_id):
    """{frame_key: state} for every frame with a currently active
    paradox -- each frame's own paradox is fully independent, since
    concurrent play means frame A's wound must never mask frame B's
    (see check_and_apply_paradox). Chat-global storage (not redirected
    through the active-frame contextvar) is correct here: this is a
    shared registry every frame's commit reads and writes its OWN entry
    into, not per-era state."""
    stored = wget(chat_id, "paradoxes", None)
    if stored is not None:
        return stored
    # One-time read fallback for chats written before paradoxes were
    # split per-frame -- this engine's earlier single-slot "paradox" key.
    legacy = wget(chat_id, "paradox", None)
    if legacy:
        return {_frame_key(legacy.get("frame_id")): legacy}
    return {}


def get_paradox(chat_id, frame_id):
    return get_all_paradoxes(chat_id).get(_frame_key(frame_id))


def paradox_visible_to(chat_id, viewer_frame_id):
    """A paradox is only visible to (and only locks frame jumps for)
    whoever is actually IN the frame it's unfolding in -- each frame has
    its own independent slot (see get_all_paradoxes), so this is a
    direct per-frame lookup rather than a single shared record checked
    against the viewer."""
    return get_paradox(chat_id, viewer_frame_id)


def _save_paradox(chat_id, state):
    # Read-modify-write on the shared registry -- transaction() closes
    # the race between two frames' commits concurrently saving their OWN
    # entry at (almost) the same moment (each would otherwise risk
    # clobbering the other's just-written entry with a stale copy of the
    # dict read before the other's write landed).
    with transaction():
        all_paradoxes = get_all_paradoxes(chat_id)
        all_paradoxes[_frame_key(state.get("frame_id"))] = state
        wset(chat_id, "paradoxes", all_paradoxes)


def _clear_paradox(chat_id, frame_id):
    with transaction():
        all_paradoxes = get_all_paradoxes(chat_id)
        all_paradoxes.pop(_frame_key(frame_id), None)
        wset(chat_id, "paradoxes", all_paradoxes)


def _restore_consumed(chat_id, state):
    """Undoes HAZARD's room consumption on resolution -- consumed rooms
    were only ever flagged impassable in the scene blob, never deleted,
    so this is a pure scene-blob edit."""
    sc = wget(chat_id, "scene", None)
    if not isinstance(sc, dict):
        return
    rooms = sc.get("rooms") or {}
    for room_id in (state.get("consumed") or {}).get("rooms") or []:
        room = rooms.get(room_id)
        if isinstance(room, dict):
            room.pop("paradox_consumed", None)
            notes = room.get("notes") or ""
            if notes.endswith(_HAZARD_WOUND_NOTE):
                room["notes"] = notes[:-len(_HAZARD_WOUND_NOTE)]
    wset(chat_id, "scene", sc)


def _clock_elapsed(chat_id):
    clock = wget(chat_id, "simulation_clock", None) or {}
    return float(clock.get("elapsed_seconds") or 0.0)


def _stage_for(severity):
    stage = 0
    for i, threshold in enumerate(STAGE_THRESHOLDS):
        if severity >= threshold:
            stage = i
    return stage


def _apply_hazard_stage(chat_id, state, stage):
    sc = wget(chat_id, "scene", None)
    if not isinstance(sc, dict):
        return
    epicenter = state.get("epicenter_room")
    rooms = sc.get("rooms") or {}
    if epicenter not in rooms:
        return
    consumed = state.setdefault("consumed", {"rooms": [], "entities": []})
    if stage >= 2 and epicenter not in consumed["rooms"]:
        consumed["rooms"].append(epicenter)
        rooms[epicenter]["paradox_consumed"] = True
        rooms[epicenter]["notes"] = (rooms[epicenter].get("notes") or "") + _HAZARD_WOUND_NOTE
    if stage >= 3:
        # Escalate outward one adjacency ring per stage past the second --
        # reuses the room graph's own adjacency list, no new topology.
        frontier = set(consumed["rooms"])
        newly = set()
        for room_id in list(frontier):
            for adj in (rooms.get(room_id) or {}).get("adjacent") or []:
                target = adj.get("to") if isinstance(adj, dict) else adj
                if target and target in rooms and target not in consumed["rooms"]:
                    newly.add(target)
        for room_id in newly:
            consumed["rooms"].append(room_id)
            rooms[room_id]["paradox_consumed"] = True
            rooms[room_id]["notes"] = (rooms[room_id].get("notes") or "") + _HAZARD_WOUND_NOTE
    wset(chat_id, "scene", sc)


def _apply_toll(chat_id, state, policy):
    """Deterministic decay of a traveler's own memory confidence for rows
    from their origin frame, if they're physically in the wound radius.
    Marty's fading photograph, implemented as epistemology: this engine
    already has a per-memory confidence column and weights it in
    retrieval (memory.py), so "reality is coming apart" is a measurable
    fact here rather than a narrative assertion."""
    if not policy.get("toll_in_radius", True):
        return
    sc = wget(chat_id, "scene", None)
    if not isinstance(sc, dict):
        return
    consumed_rooms = set((state.get("consumed") or {}).get("rooms") or [])
    if not consumed_rooms:
        consumed_rooms = {state.get("epicenter_room")}
    positions = sc.get("positions") or {}
    frame = get_frame(active_frame_id.get())
    travelers = set(frame.get("travelers") or []) if frame else set()
    if not travelers:
        return
    name_to_id = {
        r["name"]: r["char_id"]
        for r in q(
            "SELECT ch.id AS char_id, ch.name FROM chat_chars cc "
            "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
            (chat_id,),
        )
    }
    decay = 0.05 * state.get("severity", 0.0)
    for name, room in positions.items():
        if room not in consumed_rooms:
            continue
        char_id = name_to_id.get(name)
        if char_id is None or char_id not in travelers:
            continue
        # "Rows from their origin frame" means everything EXCEPT this
        # wound's own operative frame -- the traveler's continuity from
        # wherever they came from, the thing actually destabilizing
        # here, per Marty's fading photograph: what's happening to them
        # RIGHT NOW in the wound room is still freshly perceived and
        # doesn't fade, only the memories of the timeline the paradox is
        # unraveling do.
        qi(
            "UPDATE memories SET confidence=MAX(0.05, confidence-?) "
            "WHERE chat_id=? AND char_id=? AND frame_id IS NOT ?",
            (decay, chat_id, char_id, state.get("frame_id")),
        )


def _apply_warden_stage(chat_id, state, stage):
    """Places (or moves) a hunting scene entity at the epicenter -- an
    ordinary state_diff-shaped entity/position edit, so spatial gating,
    the reaction loop, and director_resolve all treat it as real with no
    new perception/resolution code."""
    if stage < 1:
        return
    sc = wget(chat_id, "scene", None)
    if not isinstance(sc, dict):
        return
    entities = sc.setdefault("entities", {})
    positions = sc.setdefault("positions", {})
    warden_id = state.get("warden_entity_name") or f"the {state.get('label', 'paradox')} warden"
    state["warden_entity_name"] = warden_id
    entities.setdefault(warden_id, {"kind": "creature", "subtype": "paradox_warden", "hostile": True})
    positions[warden_id] = state.get("epicenter_room")
    wset(chat_id, "scene", sc)


def _apply_stage_consequence(chat_id, state, stage, policy):
    mode = state.get("mode") or policy.get("mode", DEFAULT_MODE)
    if mode == "dread":
        return
    if mode in ("warden", "bureau"):
        _apply_warden_stage(chat_id, state, stage)
        return
    if mode == "hazard":
        _apply_hazard_stage(chat_id, state, stage)
        _apply_toll(chat_id, state, policy)
        return
    if mode == "toll":
        _apply_toll(chat_id, state, policy)
        return


def _trigger_paradox(chat_id, anchor, frame_id):
    """frame_id here is the OPERATIVE frame -- whichever frame's commit
    actually triggered the violation (ctx.turn.frame_id), NOT
    anchor["frame_id"] (narrative metadata about which era the fact is
    pinned to; those usually coincide, but world_entities has no
    per-frame partitioning, so a violation can technically be committed
    from any frame). The operative frame is what matters for where
    consequences manifest -- hazard mode consumes THIS frame's rooms,
    the clock that paces escalation is THIS frame's own simulation_clock
    -- so it has to be the frame actually live when this fires, not a
    label."""
    policy = get_policy(chat_id)
    sc = wget(chat_id, "scene", None) or {}
    positions = sc.get("positions") or {}
    epicenter = positions.get(anchor["entity_id"])
    if not epicenter:
        # Fall back to wherever the player is -- there's always a scene
        # in progress when a commit runs.
        epicenter = next(iter(positions.values()), None)
    state = {
        "anchor_id": anchor["anchor_id"], "label": anchor["label"],
        "frame_id": frame_id, "epicenter_room": epicenter,
        "started_clock_seconds": _clock_elapsed(chat_id),
        "severity": 0.0, "stage": 0,
        "mode": anchor.get("mode") or policy["mode"],
        "consumed": {"rooms": [], "entities": []},
    }
    _apply_stage_consequence(chat_id, state, 0, policy)
    _save_paradox(chat_id, state)
    return state


def _advance_paradox(chat_id, state):
    policy = get_policy(chat_id)
    anchor = next((p for p in fixed_points(chat_id) if p["anchor_id"] == state["anchor_id"]), None)

    if anchor and _anchor_satisfied(chat_id, anchor):
        _restore_consumed(chat_id, state)
        _clear_paradox(chat_id, state.get("frame_id"))
        return {**state, "resolved": True}

    elapsed = max(0.0, _clock_elapsed(chat_id) - state["started_clock_seconds"])
    severity = min(1.0, (elapsed / ESCALATION_SECONDS) * policy["escalation_rate"])
    new_stage = _stage_for(severity)
    state["severity"] = severity
    if new_stage > state["stage"]:
        state["stage"] = new_stage
        _apply_stage_consequence(chat_id, state, new_stage, policy)

    if severity >= 1.0:
        # Ceiling, minimal-slice version: reality wins. The anchor is
        # forcibly restored rather than orphaning the frame (that
        # requires visibility-rule changes to the memory ledger this
        # slice doesn't attempt -- see Design.md's paradox section).
        if anchor:
            _force_restore_anchor(chat_id, anchor)
        _restore_consumed(chat_id, state)
        _clear_paradox(chat_id, state.get("frame_id"))
        return {**state, "resolved": True, "forced": True}

    _save_paradox(chat_id, state)
    return state


def _force_restore_anchor(chat_id, anchor):
    exists = _entity_exists(chat_id, anchor["entity_id"])
    if anchor["required_exists"] and not exists:
        qi(
            "INSERT INTO world_entities(entity_id,chat_id,kind,subtype,name,payload) "
            "VALUES(?,?,?,?,?,?)",
            (anchor["entity_id"], chat_id, "person", "", anchor["entity_id"], "{}"),
        )
    elif not anchor["required_exists"] and exists:
        qi("DELETE FROM world_entities WHERE chat_id=? AND entity_id=?", (chat_id, anchor["entity_id"]))
        qi("DELETE FROM world_placements WHERE chat_id=? AND subject_id=?", (chat_id, anchor["entity_id"]))


def check_and_apply_paradox(ctx, nonce):
    """The commit-time entry point: call once per turn, after commit_scene
    and commit_world_entities have applied this turn's state_diff, so the
    check runs against what actually just got committed.

    world_entities has no per-frame partitioning (a documented Stage-3
    limitation, not attempted here -- see Design.md), so an anchor's
    existence check is a flat, chat-wide fact: whatever frame the change
    happened in, if it leaves a declared anchor unsatisfied, that IS the
    paradox.

    EACH FRAME HAS ITS OWN PARADOX SLOT (get_all_paradoxes): two frames
    running pipelines truly concurrently must each be able to detect and
    escalate their OWN wound independently. An earlier single-slot
    design let one frame's active paradox silently mask detection for a
    DIFFERENT frame's own anchor violation -- fixed by looking the
    active paradox up by THIS frame's own key rather than checking one
    shared record.

    TICK OWNERSHIP still applies within a frame's own slot: escalating
    it or checking its resolution writes into "scene" and reads
    "simulation_clock" -- both frame-scoped through the ACTIVE frame's
    contextvar. If a DIFFERENT frame's commit were allowed to advance
    another frame's slot, hazard-mode room consumption would land in the
    WRONG frame's scene, and pacing would run off the wrong frame's
    clock. Since get_paradox(chat_id, frame_id) only ever returns THIS
    frame's own slot, that's structurally impossible now rather than a
    rule this function has to enforce itself.
    """
    chat_id = ctx.chat.id
    frame_id = ctx.turn.frame_id

    # Spatial frames (frames.py's OTHER frame axis: two parties simply
    # far apart right now, not a different era) are the SAME diegetic
    # "now" as their parent -- nothing temporal is being altered, so
    # this whole mechanic must stay exempt while the split is unresolved.
    # Without this guard, ordinary distance-based room authoring could
    # spuriously trip the grandfather-paradox machinery for something
    # that was never time travel at all.
    frame = get_frame(frame_id)
    if frame and frame.get("kind") == "spatial" and frame.get("merged_turn_idx") is None:
        return {"active": False, "skipped": "spatial"}

    active = get_paradox(chat_id, frame_id)
    if active:
        return _advance_paradox(chat_id, active)
    for anchor in fixed_points(chat_id):
        if not _anchor_satisfied(chat_id, anchor):
            return _trigger_paradox(chat_id, anchor, frame_id)
    return {"active": False}
