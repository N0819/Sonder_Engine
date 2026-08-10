"""Offscreen resolution: what one absent subject's tick may spend, and the
two rungs that spend it.

Steps 3, 3a and 4 of ``docs/PROPOSAL_2026-08-06.md`` section 1.2, plus the
out-of-band producer of section 1.0.2. The goal is the proposal's section
1.0 verbatim: a high-fidelity, low-cost ILLUSION of a world that moves --
never a simulation of one -- and the cost model is the architecture's own
line, *cost scales with dramatic density, not story length*.

TWO DIALS, NOT ONE, AND THEY ANSWER DIFFERENT QUESTIONS. The chat's
``offscreen_life`` ladder (scene.py) answers what the cast is PERMITTED to
do offscreen -- a consequence ceiling, set by the author. The resolution
function here answers what a tick may SPEND on one subject -- computed per
tick from importance x distance, never stored, so the villain sharpens as
you approach their sphere and dims when you leave it without anyone editing
a setting. Folding spend into the permission ladder is the defect the
proposal names in section 1.0: a chat-level ceiling can only make
EVERYTHING richer or everything poorer at once.

RESOLUTION IS RECOMPUTED, NOT STORED. Importance is fairly stable; distance
is not. So resolution belongs in the tick decision, not as a field on the
character (section 1.0 reason 1).

THE RUNGS, and what each costs after this module:

  * lazy (gaps.interim_for)   -- zero until contact; the default for the
                                 whole cast. Built in step 2, not here.
  * deterministic seeded draw -- free. ``stochastic_ticks``: a real
                                 ``random.Random(seed)`` draw against the
                                 standing-intentions ledger, no model call.
                                 Before this module the "stochastic" rung
                                 rode the mapping_commit MODEL call and its
                                 ``tick_seed`` seeded nothing (no ``random``
                                 anywhere in commit.py) -- logged, but not
                                 replayable, and priced so that low
                                 resolution was affordable for six
                                 characters rather than free for the cast.
  * profile state tick        -- one bounded call, out of band, only for
                                 subjects the resolution function scores
                                 ``medium``. No psychology run, no
                                 adjudication, and STRUCTURALLY unable to
                                 emit a consequence: its output shape has
                                 nowhere to put an alliance, and the record
                                 it writes is the provisional tier's, which
                                 ``canon_provenance.validate_provisional``
                                 refuses to let carry deltas, standing
                                 intentions or ratified claims. Emits
                                 STATE FIELDS ({doing, at, manner}), never
                                 a summary sentence -- offscreen events are
                                 never narrated, and the earlier prose
                                 shape violated exactly that rule.
  * full agent                -- NOT BUILT. Director-adjudicated; the only
                                 rung that may ever change the world.

THE FIREWALL HOLDS IN BOTH DIRECTIONS. Nothing here hands an absent
character the player's location or recent acts: the profile rung reads the
subject's own profile surface and the deterministic trail of THEIR moves.
The player's room is read only by the DISTANCE axis -- which decides spend,
not content, so it cannot make anyone prescient; being near the player buys
a character a better-lit tick, never knowledge of them.

LOWER-RUNG TICKS DESCRIBE, NEVER COMMIT (section 1.0.1). No profile or seeded
write from this module
moves a body (``scene.positions`` changes have no warrant check -- UNBUILT
section 1.20 -- and an offscreen writer would be the missing third warrant,
built by accident), advances an intention, or touches canon. Arrival is the
resolution event: a provisional record met on screen is settled there, which
is why an in-flight tick is never cancelled when a turn starts (amendments
sections 4 and 5).

DISTANCE READS THE OBJECTIVE SCENE GRAPH ONLY -- ``scene.rooms`` adjacency,
the runtime authority -- never the per-character place graph or
``known_exits`` views. UNBUILT section 1.12 warns that a third consumer of
those views is the trigger to collapse them; this module is deliberately
not that consumer.
"""

from __future__ import annotations

import hashlib
import json
import random
import re

from logging_utils import logger

# ---------------------------------------------------------------------------
# Step 3: the two axes, and the pure function over them.
# ---------------------------------------------------------------------------

#: Importance is the engine's own line between a background presence and a
#: major character -- cast membership, a sheet, authored psychology, memory
#: -- with a manual override ON TOP of that default, never instead of it.
IMPORTANCE_LEVELS = ("background", "supporting", "major")

#: Crude on purpose: the decision this feeds has two outcomes (spend a model
#: call or not), so three buckets capture most of the value (section 1.2
#: step 3). Not metres -- beats-to-contact.
DISTANCES = ("same_room", "same_region", "elsewhere")

#: How many undirected non-wall hops still count as "you are about to walk
#: in on whatever they did". Past this, consequences cannot reach the player
#: inside the handful of beats a tick's freshness survives.
SAME_REGION_HOPS = 6

RESOLUTIONS = ("inert", "low", "medium")

# One epoch per crossed in-world hour, plus top-level location changes and
# due-event fires. A conversation can consume many turns and only seconds;
# making its cast live once per N turns prices story length rather than
# dramatic density. The bucket is intentionally coarse and is a trigger, not
# a claim that every setting experiences time in one-hour narrative units.
EPOCH_SECONDS = 60 * 60
EPOCH_KEY = "offscreen_epoch"
PLAN_KEY = "offscreen_plans"
PLAN_CAP = 8
PLAN_STAGE_CAP = 6
REACTIVE_FIRE_CAP = 3
PLAN_TRIGGER_MIN_SECONDS = 60.0
PLAN_TRIGGER_MAX_SECONDS = 30 * 86400.0
PLAN_EVENT_KINDS = frozenset({
    "consequence", "news_arrival", "transit_arrival",
})

#: The sheet field for the manual importance override:
#: ``simulation.offscreen_importance``. Deliberately NOT the
#: ``BehaviorController`` ladder: that vocabulary answers what a character
#: MAY do (permission), and reusing it for how much a character MATTERS
#: would be one field answering two questions -- the exact shape section 2D
#: measured at 79% wrong in ``flow.reactors``.
OVERRIDE_FIELD = "offscreen_importance"


def derived_importance(*, is_cast, has_sheet, tier,
                       psychology_authored=False, has_memories=False):
    """The importance the engine already knows, from facts it already holds.

    Pure. ``tier`` is ``character_schema.character_tier``'s vocabulary
    (``bg`` | ``mid`` | ``major``). A mid-tier sheet with neither authored
    psychology nor a single memory row is an auto-promoted stub wearing a
    sheet, and ticking it at supporting rate would spend the bounded tick
    budget on furniture.
    """
    if not is_cast or not has_sheet:
        return "background"
    tier = str(tier or "").strip().casefold()
    if tier == "major":
        return "major"
    if tier == "bg":
        return "background"
    if psychology_authored or has_memories:
        return "supporting"
    return "background"


def importance_for(derived, override=None):
    """The manual override applied on top of the derived default.

    An unreadable override falls to the DERIVED value, never to the floor --
    the same rule as ``scene.normalize_offscreen_life``, for the same
    reason: a typo must not silently demote a story's villain.
    """
    if derived not in IMPORTANCE_LEVELS:
        derived = "background"
    level = str(override or "").strip().casefold()
    return level if level in IMPORTANCE_LEVELS else derived


def _non_wall_hops(scene, room_a, room_b, limit):
    """Undirected BFS hop count over scene-room adjacency, excluding walls.

    A wall edge is a spatial relationship, not a route; counting it would
    put a character "one beat away" through solid stone. Every other
    barrier (a closed door, a curtain) is one beat of opening away, which
    is exactly what beats-to-contact should count. Returns None when
    unreachable within ``limit``.
    """
    if not room_a or not room_b:
        return None
    a, b = str(room_a), str(room_b)
    if a == b:
        return 0
    rooms = (scene or {}).get("rooms") or {}
    neighbors: dict[str, set] = {}
    for room_id, room in rooms.items():
        if not isinstance(room, dict):
            continue
        for edge in room.get("adjacent") or []:
            if not isinstance(edge, dict) or not edge.get("to"):
                continue
            if str(edge.get("barrier") or "").strip().casefold() == "wall":
                continue
            neighbors.setdefault(str(room_id), set()).add(str(edge["to"]))
            neighbors.setdefault(str(edge["to"]), set()).add(str(room_id))
    from collections import deque

    seen = {a}
    queue = deque([(a, 0)])
    while queue:
        cur, depth = queue.popleft()
        if depth >= limit:
            continue
        for nxt in sorted(neighbors.get(cur, ())):
            if nxt == b:
                return depth + 1
            if nxt not in seen:
                seen.add(nxt)
                queue.append((nxt, depth + 1))
    return None


def _intention_mentions(intention, needles):
    """Whether any string in one standing-intention entry names a needle.

    Prose matching, admitted as such: the ledger is untyped
    (``schemas.MappingCommitOut.standing_intentions: list[dict]``), so there
    is no structured field to read. Safe here because the answer only moves
    a distance bucket or seeds a draw -- it decides SPEND, never knowledge,
    so a false positive costs one cheap call and a false negative costs
    nothing at all.
    """
    if isinstance(intention, str):
        hay = intention.casefold()
    elif isinstance(intention, dict):
        hay = " ".join(str(v) for v in intention.values()
                       if isinstance(v, str)).casefold()
    else:
        return False
    return any(n and n in hay for n in needles)


def _intention_owned_by(intention, needles):
    """Whether one standing-intention entry BELONGS to a needle-named actor.

    Ownership, not mention. ``_intention_mentions`` above is safe where it
    decides SPEND (its own contract), but ``stochastic_ticks`` uses the match
    to pick tick CONTENT, and prose matching there moves knowledge: an
    intention that merely NAMES the subject is somebody else's aim, written by
    the omniscient mapping_commit model, and copying it into the subject's own
    ``while_you_were_offscreen`` hands the subject a fact that reached them
    through no channel. The live case is chat 9: Picard's entry names what has
    "remained untransmitted to Vrenak", and under mention-matching it sat in
    VRENAK's candidate set.

    The ledger is untyped but not shapeless -- every dict row observed in
    production carries an owner field (``actor`` or ``who``). A row with no
    readable owner, including a bare string, fails CLOSED here: it may still
    steer a spend decision, but it becomes nobody's tick content, because
    content with no owner cannot be proven to be the subject's own.
    """
    if not isinstance(intention, dict):
        return False
    for key in ("actor", "who"):
        value = intention.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().casefold() in needles
    return False


def subject_distance(scene, subject_room, player_room, *,
                     intention_at_player=False):
    """Beats-to-contact, in three buckets. Pure over the scene dict.

    ``intention_at_player`` pulls ONE step closer (elsewhere ->
    same_region), never further: a standing intention aimed at where the
    player is means its consequences are walking toward them regardless of
    the map.
    """
    hops = _non_wall_hops(scene, subject_room, player_room, SAME_REGION_HOPS)
    if hops == 0:
        return "same_room"
    if hops is not None:
        return "same_region"
    if intention_at_player:
        return "same_region"
    return "elsewhere"


def resolution_for(importance, distance):
    """The spend decision: importance x distance -> rung. Pure, total.

    Every cell is an argument from section 1.0:

      * background -> inert everywhere. The lazy rung already covers the
        whole background cast at zero standing cost; a cadenced tick for
        furniture is the O(cast x turns) shape the design exists to refuse.
      * major near the player -> medium: the world sharpens where you are
        looking. Major elsewhere -> low: "a major antagonist three
        continents away does not need medium -- you will not meet the
        consequences for fifty turns."
      * supporting in the same room -> medium: "a minor character in the
        next room may warrant it, because you are about to walk in on
        whatever they did." Anywhere further -> low.

    Unknown inputs fall to the CHEAPEST honest cell for what is known --
    a spend decision must fail toward not spending.
    """
    if importance not in IMPORTANCE_LEVELS or distance not in DISTANCES:
        return "inert" if importance not in IMPORTANCE_LEVELS else "low"
    if importance == "background":
        return "inert"
    if importance == "major":
        return "low" if distance == "elsewhere" else "medium"
    return "medium" if distance == "same_room" else "low"


# ---------------------------------------------------------------------------
# Step 4: the seeded draw. Free, replayable, and it replaces a model call.
# ---------------------------------------------------------------------------

#: Chance one dormant actor ticks at one scene boundary. Half, so a quiet
#: absence stays quiet more often than not and the log does not assert a
#: beehive; the draw is seeded, so the same boundary re-derives the same
#: answer on a reroll instead of quietly becoming a second history.
TICK_CHANCE = 0.5

#: What a tick without a matching standing intention may say. Deliberately
#: near-content-free: a deterministic rung may DESCRIBE, never commit, and
#: the less it asserts the less it can ever contradict.
_IDLE_TICKS = (
    "{who} goes about their own business, elsewhere.",
    "{who} keeps their own counsel; nothing of it reaches here.",
    "{who} carries on much as they were.",
)


def stochastic_ticks(seed, actors, intentions, cap):
    """The seeded draw against standing intentions. Pure; no model, no I/O.

    ``actors``: [{"id": subject_id, "display": name}] -- dormant cast, id
    first (``offscreen_log``'s name-keyed ``actor`` is the live section 2A
    defect; ticks minted here are keyed by subject id from birth).
    ``intentions``: the chat's ``standing_intentions`` ledger, untyped.

    Same seed + same inputs = same ticks, byte for byte. That is the
    architecture's "seeded, logged, replayable -- stochastic-unlogged ticks
    forbidden", and it is the property the shipped rung claimed and did not
    have: its ``tick_seed`` was a string shown to a model that no RNG ever
    consumed.
    """
    try:
        cap = max(0, int(cap))
    except (TypeError, ValueError):
        cap = 0
    if cap <= 0:
        return []
    rng = random.Random(str(seed))
    events = []
    for actor in actors or []:
        if not isinstance(actor, dict):
            continue
        sid = str(actor.get("id") or "").strip()
        display = str(actor.get("display") or "").strip()
        if not sid:
            continue  # id space from birth; no id, no tick
        roll = rng.random()
        # Draw the intention BEFORE the tick gate so the RNG consumption per
        # actor is fixed: an actor list reordering upstream changes their
        # draws, but adding a caller-side filter after the fact does not.
        needles = [display.casefold()] if display else []
        needles.append(sid.casefold())
        mine = [i for i in (intentions or []) if _intention_owned_by(i, needles)]
        pick = rng.randrange(len(mine)) if mine else rng.randrange(len(_IDLE_TICKS))
        if roll >= TICK_CHANCE or len(events) >= cap:
            continue
        who = display or sid
        if mine:
            chosen = mine[pick]
            text = chosen if isinstance(chosen, str) else " ".join(
                str(v) for v in chosen.values() if isinstance(v, str))
            tick = f"{who} keeps quietly at it: {' '.join(text.split())[:220]}"
            intention = " ".join(text.split())[:220]
        else:
            tick = _IDLE_TICKS[pick].format(who=who)
            intention = ""
        events.append({
            "disposition": "provisional",
            "subject": {"kind": "character", "id": sid,
                        **({"display": display} if display and
                           display.casefold() != sid.casefold() else {})},
            "basis": "deterministic",
            # Legacy aliases so the existing reader (gaps._skeleton) and the
            # mixed historical log keep one shape: {actor, tick} everywhere.
            "actor": sid,
            "actor_display": display,
            "tick": tick,
            "intention": intention,
            "roll": round(roll, 4),
        })
    return events


# ---------------------------------------------------------------------------
# The log write: one door, both writers.
# ---------------------------------------------------------------------------

def append_offscreen_log(cid, turn_idx, seed, events, *, rung="stochastic"):
    """Append one batch to ``offscreen_log``. The only writer, on purpose.

    Two writers doing wget/append/wset independently is a lost-update race
    the moment the producer lands mid-turn; folding both through one helper
    is cheaper than remembering a rule. The read-modify-write runs inside a
    database TRANSACTION rather than under a module lock: the commit path
    calls this while already holding the turn's write lock (re-entrant on
    that thread), and the producer thread simply queues behind the turn. A
    module lock here plus the database lock there is a classic two-lock
    deadlock pair, and this shape has no second lock.

    Provisional-shaped events are validated on the way in and a refused one
    is DROPPED WITH A LOG LINE, never stored -- a stored invented room
    outlives the turn that made it (section 1.0.3, the "quiet office" row).
    """
    from canon_provenance import validate_provisional
    from db import transaction, wget, wset

    kept = []
    citable = None
    for ev in events or []:
        if isinstance(ev, dict) and ev.get("disposition"):
            if citable is None:
                citable = _adjudicated_event_ids(cid)
            ev = {**ev, "base_turn": int(turn_idx)}
            check = validate_provisional(ev, adjudicated_event_ids=citable)
            if not check:
                logger.info(
                    "offscreen tick refused: chat=%s turn=%s errors=%s",
                    cid, turn_idx, "; ".join(check.errors)[:300])
                continue
        kept.append(ev)
    if not kept:
        return []
    with transaction():
        log = wget(cid, "offscreen_log", []) or []
        # Stable batch identity makes reroll/background races harmless. A
        # completed job may still be in flight while its base turn is restored;
        # if the same epoch is recomputed, either result may arrive first but
        # the fiction receives one batch. Checkpoints restore this whole log,
        # so a discarded timeline's batch disappears with its other facts.
        if any(
            isinstance(batch, dict)
            and str(batch.get("seed") or "") == str(seed)
            and str(batch.get("rung") or "") == str(rung)
            for batch in log
        ):
            return []
        log.append({"turn": int(turn_idx), "seed": str(seed),
                    "rung": rung, "events": kept})
        wset(cid, "offscreen_log", log)
    return kept


# ---------------------------------------------------------------------------
# The shared world epoch. This is primary state and runs inside commit_all's
# transaction; only the model-priced profile work is scheduled afterward.
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
    result. Multiple causes in one beat are one epoch: one world edge, one
    actor cap, one seed. A pre-existing story that first encounters this code
    is baselined rather than retroactively ticked by a migration artifact.
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


def _plan_slug(value):
    return re.sub(r"[^a-z0-9_-]+", "_", str(value or "").casefold()).strip("_")[:80]


def _plan_words(value):
    stop = {"a", "an", "and", "at", "for", "from", "i", "in", "it",
            "my", "of", "on", "or", "the", "this", "to", "we", "will"}
    return {w for w in re.findall(r"[a-z0-9']+", str(value or "").casefold())
            if len(w) > 2 and w not in stop}


def _declared_plan_actors(ctx):
    """Character-owned declaration text keyed by stable id and display name.

    The Director may adjudicate a plan but cannot mint its objective. This is
    the structural half of that ownership rule: a stored `basis` has to match
    something the named character actually returned this beat.
    """
    from character_schema import (cast_entity_id, character_name,
                                  character_name_from_text)

    out = {}
    results = getattr(ctx, "character_results", None) or {}
    for row in getattr(ctx, "cast", None) or []:
        try:
            char_id = int(row["id"])
        except (KeyError, TypeError, ValueError):
            continue
        raw_sheet = row.get("sheet") if isinstance(row, dict) else row["sheet"]
        try:
            sheet = json.loads(raw_sheet or "{}") if isinstance(raw_sheet, str) \
                else (raw_sheet or {})
        except (TypeError, ValueError):
            sheet = {}
        result = results.get(char_id) or results.get(str(char_id)) or {}
        if not isinstance(result, dict):
            continue
        pieces = []
        for event in result.get("sequence") or []:
            if not isinstance(event, dict):
                continue
            pieces.extend(str(event.get(k) or "") for k in (
                "text", "attempt", "observable", "reason") if event.get(k))
        pieces.extend(str(result.get(k) or "") for k in ("speech",) if result.get(k))
        action = result.get("action") or {}
        if isinstance(action, dict):
            pieces.extend(str(action.get(k) or "") for k in (
                "attempt", "observable", "reason") if action.get(k))
        for field in ("intent_ops", "project_ops"):
            for op in result.get(field) or []:
                if isinstance(op, dict):
                    pieces.extend(str(v) for v in op.values()
                                  if isinstance(v, str) and v.strip())
        corpus = " ".join(" ".join(pieces).split())
        if not corpus:
            continue
        display = (character_name_from_text(raw_sheet or "{}")
                   if isinstance(raw_sheet, str) else character_name(sheet))
        sid = cast_entity_id(sheet, char_id)
        entry = {"id": sid, "display": display, "char_id": char_id,
                 "corpus": corpus}
        for key in {sid.casefold(), display.casefold(), str(char_id)}:
            if key:
                out[key] = entry
    return out


def _basis_is_grounded(basis, corpus):
    basis_text = " ".join(str(basis or "").split())
    corpus_text = " ".join(str(corpus or "").split())
    if len(basis_text) < 6 or not corpus_text:
        return False
    if basis_text.casefold() in corpus_text.casefold():
        return True
    words = _plan_words(basis_text)
    if not words:
        return False
    overlap = words & _plan_words(corpus_text)
    return len(overlap) >= min(3, len(words)) and len(overlap) / len(words) >= 0.5


def _normalize_plan_stages(cid, scene, frame_id, ctx, actor, stages,
                           elapsed):
    """Validate plan stages now, while their Director adjudication is current."""
    from living_world import mint_consequences
    from subjects import resolve_subject

    normalized, warnings = [], []
    for index, raw in enumerate((stages or [])[:PLAN_STAGE_CAP]):
        if not isinstance(raw, dict):
            warnings.append(f"stage {index} is not an object")
            continue
        trigger = raw.get("trigger") or {}
        if not isinstance(trigger, dict):
            warnings.append(f"stage {index} has no trigger object")
            continue
        event_kind = str(trigger.get("event_kind") or "").strip().casefold()
        trigger_out = {}
        if event_kind:
            if event_kind not in PLAN_EVENT_KINDS:
                warnings.append(f"stage {index} has unknown event_kind {event_kind!r}")
                continue
            trigger_out["event_kind"] = event_kind
            location = str(trigger.get("location") or "").strip()
            if location:
                resolved = resolve_subject(cid, scene, "place", location, frame_id)
                if not resolved:
                    warnings.append(
                        f"stage {index} trigger location {location!r} is unknown")
                    continue
                trigger_out["location_id"] = resolved.subject.id
        else:
            try:
                after = float(trigger.get("after_seconds"))
            except (TypeError, ValueError):
                warnings.append(f"stage {index} needs after_seconds or event_kind")
                continue
            after = min(max(after, PLAN_TRIGGER_MIN_SECONDS),
                        PLAN_TRIGGER_MAX_SECONDS)
            trigger_out.update({"after_seconds": after,
                                "due_at": float(elapsed) + after})

        effect = raw.get("effect")
        effect_out = None
        if effect is not None:
            if hasattr(effect, "dict"):
                effect = effect.dict()
            if not isinstance(effect, dict):
                warnings.append(f"stage {index} effect is not an object")
                continue
            rows, effect_warnings = mint_consequences(
                cid, scene, frame_id, ctx.turn.id, ctx.turn.idx, elapsed,
                [effect], player_room="")
            if not rows:
                warnings.extend(f"stage {index}: {w}" for w in effect_warnings)
                continue
            payload = json.loads(rows[0]["payload"])
            effect_out = {
                "what": payload["what"], "where": payload["where"],
                "due_seconds": payload["declared_due_seconds"],
                "witnessed": payload.get("witnessed") or "",
                "originator": actor["id"],
            }
        normalized.append({
            "stage_id": _plan_slug(raw.get("stage_id")) or f"stage_{index + 1}",
            "trigger": trigger_out, "effect": effect_out,
        })
    return normalized, warnings


def apply_plan_ops(ctx, scene, clock):
    """Persist grounded `open|cancel` operations for the reactive rung.

    Called inside the primary turn transaction. It performs no model work and
    stores frame-scoped world KV, so checkpoints/branches/archive inherit the
    state without a parallel persistence mechanism.
    """
    from db import wget, wset
    from living_world import living_world_allows, living_world_config

    cid = ctx.chat.id
    raw_ops = ((ctx.director_resolve or ctx.director_establish or {})
               .get("state_diff") or {}).get("offscreen_plan_ops") or []
    if not isinstance(raw_ops, list):
        raw_ops = []
    allowed = living_world_allows(
        living_world_config(cid), "antagonist_ladder", "floor")
    if not allowed:
        if raw_ops:
            ctx.add_warning(
                f"discarded {len(raw_ops)} off-screen plan op(s): "
                "the antagonist-ladder floor is off or above the authority ceiling")
        return {"offered": len(raw_ops), "applied": 0, "active": 0,
                "warnings": len(raw_ops), "enabled": False}

    plans = wget(cid, PLAN_KEY, []) or []
    plans = [dict(p) for p in plans if isinstance(p, dict) and p.get("plan_id")]
    by_id = {str(p["plan_id"]): p for p in plans}
    actors = _declared_plan_actors(ctx)
    elapsed = _as_seconds(clock)
    applied = 0
    warnings = []

    for index, raw in enumerate(raw_ops[:PLAN_CAP]):
        if hasattr(raw, "dict"):
            raw = raw.dict()
        if not isinstance(raw, dict):
            warnings.append(f"op {index} is not an object")
            continue
        op = str(raw.get("op") or "open").strip().casefold()
        actor_key = str(raw.get("actor") or "").strip().casefold()
        actor = actors.get(actor_key)
        if not actor:
            warnings.append(
                f"op {index} actor {raw.get('actor')!r} made no plan declaration this beat")
            continue
        basis = " ".join(str(raw.get("basis") or "").split())[:240]
        if not _basis_is_grounded(basis, actor["corpus"]):
            warnings.append(f"op {index} basis is not grounded in {actor['display']}'s declaration")
            continue
        plan_id = _plan_slug(raw.get("plan_id"))
        if not plan_id:
            material = f"{cid}:{ctx.turn.frame_id}:{actor['id']}:{raw.get('objective')}:{ctx.turn.idx}"
            plan_id = "plan_" + hashlib.sha256(material.encode()).hexdigest()[:16]

        if op == "cancel":
            plan = by_id.get(plan_id)
            if not plan or plan.get("actor_id") != actor["id"]:
                warnings.append(f"op {index} cannot cancel unknown/unowned plan {plan_id!r}")
                continue
            if plan.get("status") == "active":
                plan["status"] = "cancelled"
                plan["updated_turn"] = int(ctx.turn.idx)
                plan.setdefault("history", []).append({
                    "event": "cancelled", "turn": int(ctx.turn.idx),
                    "basis": basis,
                })
                plan["history"] = plan["history"][-20:]
                applied += 1
            continue
        if op != "open":
            warnings.append(f"op {index} has unknown operation {op!r}")
            continue
        if plan_id in by_id:
            warnings.append(f"op {index} plan_id {plan_id!r} already exists")
            continue
        if len([p for p in plans if p.get("status") == "active"]) >= PLAN_CAP:
            warnings.append(f"active plan cap {PLAN_CAP} reached")
            break
        objective = " ".join(str(raw.get("objective") or "").split())[:240]
        if not objective:
            warnings.append(f"op {index} has no objective")
            continue
        stages, stage_warnings = _normalize_plan_stages(
            cid, scene, ctx.turn.frame_id, ctx, actor,
            raw.get("stages") or [], elapsed)
        warnings.extend(f"op {index}: {w}" for w in stage_warnings)
        if not stages:
            warnings.append(f"op {index} has no valid stages")
            continue
        plan = {
            "plan_id": plan_id, "actor_id": actor["id"],
            "actor_display": actor["display"], "char_id": actor["char_id"],
            "objective": objective, "status": "active", "stage_index": 0,
            "stages": stages, "created_turn": int(ctx.turn.idx),
            "updated_turn": int(ctx.turn.idx),
            "history": [{"event": "opened", "turn": int(ctx.turn.idx),
                         "basis": basis}],
        }
        plans.append(plan)
        by_id[plan_id] = plan
        applied += 1

    if applied:
        wset(cid, PLAN_KEY, plans[-PLAN_CAP:])
    for warning in warnings:
        ctx.add_warning(f"off-screen plan refused: {warning}")
    return {"offered": len(raw_ops), "applied": applied,
            "active": sum(p.get("status") == "active" for p in plans),
            "warnings": len(warnings), "enabled": True}


def _reactive_triggered(stage, elapsed, fired_events):
    trigger = stage.get("trigger") if isinstance(stage, dict) else None
    if not isinstance(trigger, dict):
        return False
    if "due_at" in trigger:
        try:
            return float(elapsed) >= float(trigger["due_at"])
        except (TypeError, ValueError):
            return False
    kind = str(trigger.get("event_kind") or "")
    location = str(trigger.get("location_id") or "")
    return any(
        isinstance(event, dict)
        and str(event.get("kind") or "") == kind
        and (not location or str(event.get("location_id") or "") == location)
        for event in fired_events or []
    )


def _reactive_due_crossed(plans, previous_clock, clock):
    """Whether an active time stage creates an epoch edge this beat.

    A plan due in five minutes must not wait for the next whole-hour bucket.
    The strict lower bound also prevents an invalid/temporarily unmintable
    effect from manufacturing a new epoch on every later dialogue turn: it is
    retried at the next natural epoch, not spun as a cadence loop.
    """
    before = _as_seconds(previous_clock)
    after = _as_seconds(clock)
    if after <= before:
        return False
    for plan in plans or []:
        if not isinstance(plan, dict) or plan.get("status") != "active":
            continue
        stages = plan.get("stages") or []
        try:
            index = int(plan.get("stage_index") or 0)
            stage = stages[index]
            due_at = float((stage.get("trigger") or {})["due_at"])
        except (IndexError, KeyError, TypeError, ValueError):
            continue
        if before < due_at <= after:
            return True
    return False


def advance_reactive_plans(ctx, scene, clock, transit_result, epoch_id):
    """Fire already-authored plan stages. No deliberation, no invention."""
    from db import qtx, wget, wset
    from gaps import LAST_SEEN_KEY
    from living_world import (living_world_allows, living_world_config,
                              mint_consequences)
    from mechanics import stable_event_key

    cid = ctx.chat.id
    if not living_world_allows(
            living_world_config(cid), "antagonist_ladder", "floor"):
        return {"reactive_considered": 0, "reactive_fired": 0,
                "reactive_effect_opportunities": 0,
                "reactive_effects_minted": 0}
    plans = wget(cid, PLAN_KEY, []) or []
    if not isinstance(plans, list):
        plans = []
    fired_events = ((transit_result or {}).get("fired_events") or [])
    elapsed = _as_seconds(clock)
    last_seen = wget(cid, LAST_SEEN_KEY, {}) or {}
    considered = fired = effect_opportunities = minted = 0
    changed = False

    for plan in plans:
        if fired >= REACTIVE_FIRE_CAP or not isinstance(plan, dict) \
                or plan.get("status") != "active":
            continue
        stages = plan.get("stages") or []
        try:
            index = int(plan.get("stage_index") or 0)
        except (TypeError, ValueError):
            index = 0
        if index >= len(stages):
            plan["status"] = "completed"
            changed = True
            continue
        stage = stages[index]
        considered += 1
        if not _reactive_triggered(stage, elapsed, fired_events):
            continue
        effect = stage.get("effect") if isinstance(stage, dict) else None
        rows, warnings = [], []
        if effect:
            effect_opportunities += 1
            origin_room = str(
                (last_seen.get(plan.get("actor_id")) or {}).get("room") or "")
            rows, warnings = mint_consequences(
                cid, scene, ctx.turn.frame_id, ctx.turn.id, ctx.turn.idx,
                elapsed, [effect], player_room=origin_room)
            if rows:
                row = rows[0]
                row["event_id"] = stable_event_key(
                    "reactive_plan", cid, ctx.turn.frame_id,
                    plan.get("plan_id"), stage.get("stage_id"), ctx.turn.id)
                row["seed"] = epoch_id
                qtx(
                    "INSERT OR REPLACE INTO scheduled_events"
                    "(event_id,chat_id,due_at,kind,location_id,payload,seed,status) "
                    "VALUES(?,?,?,?,?,?,?,?)",
                    (row["event_id"], row["chat_id"], row["due_at"], row["kind"],
                     row["location_id"], row["payload"], row["seed"], row["status"]),
                )
                minted += 1
        if effect and not rows:
            for warning in warnings:
                ctx.add_warning(
                    f"reactive plan {plan.get('plan_id')} held: {warning}")
            continue
        plan["stage_index"] = index + 1
        plan["updated_turn"] = int(ctx.turn.idx)
        plan.setdefault("history", []).append({
            "event": "stage_fired", "stage_id": stage.get("stage_id"),
            "turn": int(ctx.turn.idx), "epoch_id": epoch_id,
            **({"effect_event_id": rows[0]["event_id"]} if rows else {}),
        })
        plan["history"] = plan["history"][-20:]
        if plan["stage_index"] >= len(stages):
            plan["status"] = "completed"
        fired += 1
        changed = True
    if changed:
        wset(cid, PLAN_KEY, plans)
    return {"reactive_considered": considered, "reactive_fired": fired,
            "reactive_effect_opportunities": effect_opportunities,
            "reactive_effects_minted": minted}


def advance_epoch(ctx, prepared_scene, transit_result):
    """Commit this beat's frame-scoped off-screen epoch and free tick draw.

    This function is a commit domain: it performs no provider call and runs
    under `commit_all`'s outer transaction. Its world-KV state and log are
    therefore captured by the ordinary pre-turn checkpoint, branch key remap,
    and portable archive paths without a new table-specific serializer.
    """
    from db import wget, wset
    from scene import dialogue_config, offscreen_life_allows

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
    plans = wget(cid, PLAN_KEY, []) or []
    if _reactive_due_crossed(plans, previous_clock, clock):
        reasons.append("reactive_due")

    old = wget(cid, EPOCH_KEY, {}) or {}
    # Upgrade baseline: an old story has no epoch record. Do not invent one
    # retroactive tick merely because new code first saw it, but do preserve a
    # real boundary crossed by this very beat.
    bootstrapped = not isinstance(old, dict) or not old
    if bootstrapped and int(turn_idx) > 0 and not reasons:
        state = {
            "sequence": 0, "epoch_id": "", "turn": int(turn_idx),
            "elapsed_seconds": elapsed,
            "time_bucket": int(elapsed // EPOCH_SECONDS),
            "location": location, "reasons": ["baseline"],
        }
        wset(cid, EPOCH_KEY, state)
        return {
            "opportunity": False, "eligible": False,
            "bootstrapped": True, "reasons": ["baseline"],
            "actors_considered": 0, "stochastic_fired": 0,
            **state,
        }

    if not reasons:
        return {
            "opportunity": False, "eligible": False,
            "bootstrapped": bootstrapped, "reasons": [],
            "epoch_id": "", "actors_considered": 0,
            "stochastic_fired": 0,
        }

    try:
        previous_sequence = max(0, int((old or {}).get("sequence") or 0))
    except (TypeError, ValueError):
        # A hand-edited/legacy world key must not make the whole turn
        # uncommittable. The stable epoch id still supplies idempotence.
        previous_sequence = 0
    sequence = previous_sequence + 1
    epoch_id = _epoch_id(
        cid, frame_id, turn_idx, elapsed, location, reasons)
    state = {
        "sequence": sequence, "epoch_id": epoch_id, "turn": int(turn_idx),
        "elapsed_seconds": elapsed,
        "time_bucket": int(elapsed // EPOCH_SECONDS),
        "location": location, "reasons": reasons,
    }
    wset(cid, EPOCH_KEY, state)

    reactive = advance_reactive_plans(
        ctx, scene, clock, transit_result, epoch_id)

    cfg = dialogue_config(cid) or {}
    cap = max(0, int(cfg.get("max_offscreen_actors", 3) or 0))
    actors = dormant_subjects(cid, frame_id)
    eligible = (
        offscreen_life_allows(cfg.get("offscreen_life"), "stochastic")
        and cap > 0
    )
    written = []
    if eligible and actors:
        ticks = stochastic_ticks(
            epoch_id, actors, wget(cid, "standing_intentions", []) or [], cap)
        written = append_offscreen_log(
            cid, turn_idx, epoch_id, ticks, rung="stochastic")
    return {
        "opportunity": True, "eligible": eligible,
        "bootstrapped": bootstrapped, **state,
        "actors_considered": len(actors),
        "stochastic_fired": len(written),
        **reactive,
    }


def _adjudicated_event_ids(cid):
    """Every event id something already minted: the citable set.

    A provisional record may cite either the scheduled cause or its promoted
    objective world event; it may not mint an identity of its own.
    """
    from db import q

    return {
        str(r["event_id"])
        for table in ("scheduled_events", "world_events")
        for r in q(f"SELECT event_id FROM {table} WHERE chat_id=?", (cid,))
    }


# ---------------------------------------------------------------------------
# Step 3a: the profile rung. One call, no psychology, no consequence -- and
# STATE, never prose. The call is legitimate (out of band, bounded); its old
# output shape was not: it produced a 1-2 sentence summary, and an offscreen
# event has no player-legitimate prose surface (DESIGN_LIVING_WORLD.md
# section 0.2 -- ticks produce state; prose is authored at contact by the
# machinery already being paid for). The model now fills three bounded
# attribute fields; anything longer than a phrase is refused on the write
# path, because a field that can hold a sentence will be handed one.
# ---------------------------------------------------------------------------

#: Bounds on the state fields. Word counts, not characters, because the
#: failure mode is narration smuggled into an attribute -- "she spends the
#: evening arguing with the quartermaster about the missing shipment" is 11
#: words of story wearing a field name.
DOING_MAX_WORDS = 8
MANNER_MAX_WORDS = 6


def compose_tick(who, state):
    """The deterministic legacy rendering of a state tick: composition by
    CODE, so the stored string asserts exactly the fields and nothing more.
    Prose for the player is minted at contact by the character's own mouth;
    this is the log/payload spelling the existing readers (gaps._skeleton)
    already consume."""
    state = state or {}
    doing = str(state.get("doing") or "").strip()
    manner = str(state.get("manner") or "").strip()
    at = str(state.get("at") or "").strip()
    parts = f"{who} — {doing}" if doing else f"{who} — about their own business"
    if manner:
        parts += f", {manner}"
    if at:
        parts += f" (at {at})"
    return parts


def _profile_surface(sheet):
    """The observable surface a profile tick may condition on.

    Identity, appearance summary, authored standing goals. Deliberately NOT
    the psychology block: "no psychology run" is the rung's definition, and
    a drive leaking into a cheap cadenced call would make the expensive
    full-agent rung's honest version indistinguishable from this sketch.
    """
    from character_schema import (character_name_from_text,
                                  character_standing_intentions,
                                  normalize_character_data)

    data = normalize_character_data(sheet or {})
    identity = data.get("identity") or {}
    visible = ((data.get("embodiment") or {}).get("visible") or {})
    return {
        "name": str(identity.get("name") or "").strip()
        or character_name_from_text(json.dumps(sheet or {})),
        "summary": str(visible.get("summary") or "")[:300],
        "standing_goals": [
            i.get("intent") for i in character_standing_intentions(sheet or {})
        ][:4],
    }


class _ProfileFallback(Exception):
    pass


def profile_summary_record(cid, scene, subject, sheet, since_turn, until_turn,
                           frame_id=None):
    """One bounded call over the subject's profile and deterministic trail.

    Returns a PROVISIONAL record (validated by the caller's write path)
    whose model half is STATE -- ``state: {doing, at, manner}``, three
    bounded attribute fields -- never a summary sentence: offscreen events
    are never narrated, and a stored sentence is narration waiting for a
    payload. On any failure -- provider, shape, a room outside the world, a
    field that runs past its word bound -- falls back to the deterministic
    gap record after one retry: a deterministic "she was elsewhere" is
    worth more than a plausible lie (section 1.0.3).
    """
    from gaps import gap_for
    from providers import chat_complete

    trail = gap_for(cid, subject.get("kind", "character"), subject["id"],
                    since_turn, until_turn, resolution="low", scene=scene,
                    frame_id=frame_id)
    record = {
        "disposition": "provisional",
        "subject": dict(trail.get("subject") or subject),
        "base_turn": int(until_turn),
        "basis": "deterministic",
        "moves": trail.get("moves") or [],
        "events": trail.get("events") or [],
        "seed": trail.get("seed") or "",
        "producer": "offscreen.profile_summary_record",
    }
    if trail.get("basis") == "unavailable":
        record["basis"] = "unavailable"
        record["reason"] = trail.get("reason") or "gap unavailable"
        return record

    known_rooms = {str(r) for r in (scene or {}).get("rooms") or {}}
    for mv in record["moves"]:
        known_rooms.update((mv.get("from_room", ""), mv.get("to_room", "")))
    known_rooms.discard("")

    sys = (
        "You fill in what one character is plausibly occupied with off "
        "screen, from their public profile and a deterministic trail, as "
        "STATE FIELDS -- attributes, not narration. No sentences, no story: "
        "an activity a person could be found mid-way through, as they would "
        "do it. Do NOT invent outcomes, alliances, acquisitions, injuries, "
        "arrivals, discoveries, or any change to the world: an occupation, "
        "never a consequence. The character does not know where any other "
        "person is or what anyone else has done. `at` MUST be an id from "
        "rooms_available, or empty. Output STRICT JSON "
        f'{{"doing": "<what they are occupied with, {DOING_MAX_WORDS} words '
        'max, present participle>", "at": "<one room id or empty>", '
        f'"manner": "<how, {MANNER_MAX_WORDS} words max, may be empty>"}}'
    )
    user = json.dumps({
        "profile": _profile_surface(sheet),
        "since_turn": since_turn,
        "until_turn": until_turn,
        "moves": record["moves"],
        "events": record["events"],
        "rooms_available": sorted(known_rooms)[:40],
    }, ensure_ascii=False)

    last_error = "no attempt"
    for _attempt in range(2):  # reject and regenerate once, then fall back
        try:
            out = json.loads(chat_complete(
                "utility", sys, user, temperature=0.5, max_tokens=600))
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {str(exc)[:200]}"
            continue
        if not isinstance(out, dict):
            last_error = "output was not an object"
            continue
        doing = " ".join(str(out.get("doing") or "").split()).rstrip(".")
        manner = " ".join(str(out.get("manner") or "").split()).rstrip(".")
        at = str(out.get("at") or "").strip()
        if not doing:
            last_error = "state.doing missing or empty"
            continue
        if len(doing.split()) > DOING_MAX_WORDS:
            # The write-path bound that keeps this rung state-shaped: a
            # field long enough to hold a sentence has been handed one.
            last_error = (f"state.doing runs past {DOING_MAX_WORDS} words: "
                          "narration is not state")
            continue
        if len(manner.split()) > MANNER_MAX_WORDS:
            last_error = (f"state.manner runs past {MANNER_MAX_WORDS} "
                          "words: narration is not state")
            continue
        if at and at not in known_rooms:
            last_error = f"state.at {at!r} is outside the world"
            continue
        record["basis"] = "model"
        record["state"] = {"doing": doing, "at": at, "manner": manner}
        return record
    record["inputs"] = {"fell_back_from": f"profile: {last_error}"}
    logger.info("profile tick fell back: chat=%s subject=%s: %s",
                cid, subject.get("id"), last_error)
    return record


# ---------------------------------------------------------------------------
# The model-priced producer: epoch-triggered, out of band, parallel with turns,
# never cancelled merely because a new turn starts.
# ---------------------------------------------------------------------------


def dormant_subjects(cid, frame_id=None):
    """The dormant cast as subjects: [{"id", "display", "sheet"}].

    Id-shaped from birth via ``cast_entity_id`` -- the display name rides
    along for prose, it never keys anything.
    """
    from character_schema import cast_entity_id, character_name_from_text
    from db import q

    out = []
    for row in q(
        "SELECT cc.char_id AS char_id, COALESCE(cc.sheet,ch.sheet) AS sheet, "
        "COALESCE(ccf.state,cc.state) AS cstate "
        "FROM chat_chars cc JOIN characters ch ON ch.id=cc.char_id "
        "LEFT JOIN chat_char_frames ccf "
        "  ON ccf.chat_id=cc.chat_id AND ccf.char_id=cc.char_id AND ccf.frame_id IS ? "
        "WHERE cc.chat_id=? AND COALESCE(ccf.status, cc.status)='dormant' "
        "ORDER BY cc.char_id",
        (frame_id, cid),
    ):
        try:
            sheet = json.loads(row["sheet"] or "{}")
        except Exception:
            sheet = {}
        try:
            state = json.loads(row["cstate"] or "{}")
        except Exception:
            state = {}
        out.append({
            "id": cast_entity_id(sheet, row["char_id"]),
            "display": character_name_from_text(row["sheet"] or "{}"),
            "sheet": sheet,
            "char_id": row["char_id"],
            "state": state if isinstance(state, dict) else {},
        })
    return out


def full_agent_candidates(cid, *, frame_id=None, cap=1):
    """Opted-in dormant minds with a concrete reason to spend a paid tick.

    Selection is deterministic and content-firewalled. It sees only whether a
    character owns an active authored plan and whether their own carried-report
    state contains evidence newer than their last paid tick; it never reads the
    objective scene/player feed. The producer remains a separate step.
    """
    from character_schema import character_offscreen_agent
    from db import wget, wget_for_frame

    try:
        cap = max(0, int(cap))
    except (TypeError, ValueError):
        cap = 0
    plans = (wget_for_frame(cid, PLAN_KEY, frame_id, [])
             if frame_id is not None else wget(cid, PLAN_KEY, [])) or []
    active_by_actor = {
        str(plan.get("actor_id"))
        for plan in plans if isinstance(plan, dict)
        and plan.get("status") == "active" and plan.get("actor_id")
    }
    out = []
    for entry in dormant_subjects(cid, frame_id):
        if not character_offscreen_agent(entry.get("sheet") or {}):
            continue
        state = entry.get("state") if isinstance(entry.get("state"), dict) else {}
        agent_state = state.get("offscreen_agent") \
            if isinstance(state.get("offscreen_agent"), dict) else {}
        try:
            last_tick = int(agent_state.get("last_turn") or -1)
        except (TypeError, ValueError):
            last_tick = -1
        reports = [r for r in state.get("carried_reports") or []
                   if isinstance(r, dict)]
        new_reports = []
        for report in reports:
            try:
                acquired_turn = int(report.get("acquired_turn") or -1)
            except (TypeError, ValueError):
                continue
            if acquired_turn > last_tick:
                new_reports.append(report)
        reasons = []
        if entry["id"] in active_by_actor:
            reasons.append("active_plan")
        if new_reports:
            reasons.append("new_carried_report")
        if not reasons:
            continue
        out.append({**entry, "reasons": reasons,
                    "new_report_count": len(new_reports)})
        if len(out) >= cap:
            break
    return out


def _subject_importance(cid, entry):
    """Importance for one dormant subject, derived + override."""
    from character_schema import character_tier

    sheet = entry.get("sheet") or {}
    psychology = (sheet.get("psychology") or {})
    drive = psychology.get("drive") or {}
    authored = bool(str(drive.get("essence") or "").strip())
    has_memories = _has_memories(cid, entry)
    derived = derived_importance(
        is_cast=True, has_sheet=bool(sheet), tier=character_tier(sheet),
        psychology_authored=authored, has_memories=has_memories)
    override = ((sheet.get("simulation") or {}).get(OVERRIDE_FIELD))
    return importance_for(derived, override)


def _has_memories(cid, entry):
    from db import q

    char_id = entry.get("char_id")
    if char_id is None:
        return False  # no row to ask about is no memories, not a guess
    row = q("SELECT 1 FROM memories WHERE chat_id=? AND char_id=? LIMIT 1",
            (cid, char_id), one=True)
    return bool(row)


def profile_candidates(cid, scene, player_room, intentions, *, frame_id=None,
                       cap=3):
    """Which dormant subjects earn the medium rung this tick, bounded.

    Distance reads the subject's LAST-SEEN room (``gaps.LAST_SEEN_KEY``) --
    a dormant body holds no live position -- against the player's current
    room. Never seen means no anchor, which is "elsewhere" unless a standing
    intention points at the player's room.
    """
    from gaps import LAST_SEEN_KEY
    from db import wget, wget_for_frame

    ledger = (wget_for_frame(cid, LAST_SEEN_KEY, frame_id, {})
              if frame_id is not None else wget(cid, LAST_SEEN_KEY, {})) or {}
    out = []
    for entry in dormant_subjects(cid, frame_id):
        importance = _subject_importance(cid, entry)
        needles = [entry["display"].casefold()] if entry.get("display") else []
        needles.append(entry["id"].casefold())
        aimed = any(
            _intention_mentions(i, needles)
            and _intention_mentions(i, [str(player_room or "").casefold()])
            for i in (intentions or []))
        last_room = ((ledger.get(entry["id"]) or {}).get("room"))
        distance = subject_distance(scene, last_room, player_room,
                                    intention_at_player=aimed)
        if resolution_for(importance, distance) == "medium":
            out.append({**entry, "importance": importance,
                        "distance": distance})
        if len(out) >= max(0, int(cap)):
            break
    return out


def schedule_profile_ticks(ctx, epoch=None):
    """Queue this epoch's out-of-band profile ticks. Returns Job or None.

    Called from the commit tail, AFTER the turn's facts are durable; a
    failure is a warning, never a rollback. The job runs in parallel with
    whatever the player does next and is deliberately never cancelled when a
    turn starts: cancelling on turn-start makes the world's progress depend
    on player idleness -- the more engaged the player, the less alive the
    world -- which inverts the feature (amendment 4). Arrival is safe
    because every write is provisional (amendment 5).
    """
    import jobs
    from scene import dialogue_config, offscreen_life_allows
    from spatial import room_of

    cid = ctx.chat.id
    turn_idx = ctx.turn.idx
    frame_id = ctx.turn.frame_id
    epoch = epoch if isinstance(epoch, dict) else {}
    if not epoch.get("opportunity"):
        return None
    epoch_id = str(epoch.get("epoch_id") or "").strip()
    if not epoch_id:
        epoch["profile_skip"] = "missing_epoch_id"
        return None
    cfg = dialogue_config(cid) or {}
    cap = int(cfg.get("max_offscreen_actors", 3) or 0)
    if not offscreen_life_allows(cfg.get("offscreen_life"), "stochastic") or cap <= 0:
        epoch["profile_opportunity"] = False
        epoch["profile_skip"] = "ceiling_or_cap"
        return None
    epoch["profile_opportunity"] = True

    from character_schema import persona_name
    from db import wget, wget_for_frame
    from scene import persona_of

    scene = (wget_for_frame(cid, "scene", frame_id, {})
             if frame_id is not None else wget(cid, "scene", {})) or {}
    player = persona_name(persona_of(ctx.chat))
    player_room = room_of(scene, str(player)) if player else None
    if not player_room:
        # Without the player's room the distance axis has no anchor, and the
        # medium rung is the one that spends -- so nothing is scheduled,
        # rather than every distance being guessed at.
        epoch["profile_candidates"] = 0
        epoch["profile_skip"] = "no_player_room"
        return None
    intents = wget(cid, "standing_intentions", []) or []
    candidates = profile_candidates(
        cid, scene, player_room, intents, frame_id=frame_id, cap=cap)
    epoch["profile_candidates"] = len(candidates)
    if not candidates:
        epoch["profile_skip"] = "no_medium_candidates"
        return None

    since_by_subject = {}
    from gaps import LAST_SEEN_KEY

    ledger = (wget_for_frame(cid, LAST_SEEN_KEY, frame_id, {})
              if frame_id is not None else wget(cid, LAST_SEEN_KEY, {})) or {}
    for cand in candidates:
        try:
            since_by_subject[cand["id"]] = int(
                (ledger.get(cand["id"]) or {}).get("turn"))
        except (TypeError, ValueError):
            # A real medium candidate normally has a last-seen anchor. Fail
            # closed to the story origin if a legacy/custom candidate lacks
            # one; a made-up recent cadence would erase legitimate absence.
            since_by_subject[cand["id"]] = 0

    def _produce(job):
        # The job thread starts with a FRESH contextvars context --
        # threading.Thread does not inherit the submitting turn's -- so
        # every frame-scoped wget/wset below (append_offscreen_log's
        # read-modify-write above all) resolved `active_frame_id` to its
        # default, and a tick scheduled from a nested frame's turn landed
        # in the PRESENT frame's log. Pin the scheduling turn's frame for
        # the duration; copying the whole context instead would also drag
        # the turn's token_sink/cancel_event into background model calls.
        from db import active_frame_id
        token = active_frame_id.set(frame_id)
        try:
            events = []
            for cand in candidates:
                if job.cancelled.is_set():
                    break
                subject = {"kind": "character", "id": cand["id"]}
                if cand.get("display"):
                    subject["display"] = cand["display"]
                record = profile_summary_record(
                    cid, scene, subject, cand.get("sheet"),
                    since_by_subject[cand["id"]], turn_idx, frame_id=frame_id)
                state = record.get("state") or {}
                if record.get("basis") == "unavailable" or not state.get("doing"):
                    continue
                # The legacy `tick` alias is composed by CODE from the state
                # fields -- deterministic, so the stored string asserts exactly
                # what the fields assert. Prose reaches the player only at
                # contact, through the character's own mouth.
                events.append({**record, "actor": cand["id"],
                               "actor_display": cand.get("display", ""),
                               "tick": compose_tick(
                                   cand.get("display") or cand["id"], state)})
            return land_profile_ticks(
                cid, turn_idx, events, epoch_id=epoch_id)
        finally:
            active_frame_id.reset(token)

    job = jobs.submit(cid, f"offscreen_profile:{epoch_id}", _produce,
                      base_turn=turn_idx)
    epoch["profile_scheduled"] = True
    return job


def land_profile_ticks(cid, base_turn, events, *, epoch_id=None):
    """Write produced ticks, unless the world rolled back underneath them.

    The rollback guard (section 1.0.2 hazard 2): a tick computed against
    turn N describes a future that no longer happens once the player rolls
    back past N. ``base_turn`` makes that decidable; this is the landing
    check that acts on it — discard, loudly, never commit. The engine's own
    precedent is the checkpoint restore that silently undid a completed
    embedding rebuild.
    """
    from db import q, wget

    if not events:
        return {"written": 0}
    if epoch_id:
        current_epoch = wget(cid, EPOCH_KEY, {}) or {}
        if str(current_epoch.get("epoch_id") or "") != str(epoch_id):
            logger.info(
                "profile ticks discarded: chat=%s base_turn=%s epoch=%s "
                "current_epoch=%s (checkpoint/frame changed)",
                cid, base_turn, epoch_id,
                current_epoch.get("epoch_id"),
            )
            return {"written": 0, "discarded": len(events)}
    row = q("SELECT MAX(idx) AS idx FROM turns WHERE chat_id=?", (cid,),
            one=True)
    current = row["idx"] if row and row["idx"] is not None else None
    if current is not None and int(current) < int(base_turn):
        logger.info(
            "profile ticks discarded: chat=%s base_turn=%s current=%s "
            "(rolled back)", cid, base_turn, current)
        return {"written": 0, "discarded": len(events)}
    written = append_offscreen_log(
        cid, base_turn, epoch_id or f"tick:{cid}:{base_turn}", events,
        rung="profile")
    return {"written": len(written)}
