"""Offscreen resolution: what one absent subject's tick may spend, and the
two rungs that spend it.

Steps 3, 3a and 4 of ``docs/archive/PROPOSAL_2026-08-06.md`` section 1.2, plus the
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
  * full agent                -- BUILT (``schedule_agent_ticks``):
                                 Director-adjudicated, and the only rung
                                 that may change the world. Two calls, two
                                 authorities -- the character proposes an
                                 attempt over ``agent_context``'s allowlist
                                 alone, and only the Director half may
                                 declare a consequence, which still passes
                                 ``living_world.mint_consequences`` into
                                 ``scheduled_events`` under a stable id, so
                                 no second writer of ``world_events`` grows
                                 here. ``land_agent_tick`` lands the fuse,
                                 the plan change, the subject's own trail,
                                 the log record and the memory in ONE
                                 transaction or lands none of them, guarded
                                 inside it on the epoch, on the base turn,
                                 and on the subject's own ``last_epoch_id``
                                 -- so a reroll re-deriving the same epoch
                                 finds the first landing's stamp and
                                 discards itself.

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
from llm.prompts import get_prompt

from core import jobs
from core.logging_utils import logger

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
#: How many plans may be ACTIVE at once. One number used to answer three
#: questions -- this ceiling, the per-beat op budget, and how long the stored
#: list may be -- and the third counts cancelled and completed rows, so a chat
#: with a full history could have an open approved by the ceiling and dropped
#: by the truncation in the same call. Three questions, three constants.
PLAN_CAP = 8
#: Plan ops read from one beat's `state_diff`. A budget on the Director's
#: appetite, not on the world's commitments.
PLAN_OPS_PER_BEAT = 8
#: Terminal (cancelled/completed) rows kept beside the active ones. History,
#: which is why it is bounded separately and generously: what a mind set out
#: to do and abandoned is the record a later beat gets to show, and it costs
#: nothing to run.
PLAN_HISTORY_CAP = 16
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
    from mind.canon_provenance import validate_provisional
    from core.db import transaction, wget, wset

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
    from story.character_schema import (cast_entity_id, character_name,
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
    from world.living_world import mint_consequences
    from world.subjects import resolve_subject

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


_TERMINAL_PLAN_STATUSES = frozenset({"cancelled", "completed", "failed"})


def _truncate_plans(plans, warnings):
    """The stored list, bounded without forgetting a live commitment.

    Order is preserved, so the ledger still reads chronologically. What gets
    dropped is HISTORY, oldest first -- a cancelled or completed plan is
    something that already happened, while an active one is a promise the
    world is still keeping and the reactive rung will still fire. The old
    `plans[-PLAN_CAP:]` counted both, so a chat carrying a full history could
    lose the oldest ACTIVE plan to make room for a new one the ceiling had
    just approved -- silently, on the write, one line after the check.

    An active plan is dropped only when there are more of them than the
    ceiling allows, which the ceiling should have prevented; it is warned
    about rather than done quietly.
    """
    def _terminal(plan):
        return (str((plan or {}).get("status") or "").casefold()
                in _TERMINAL_PLAN_STATUSES)

    live = [p for p in plans if not _terminal(p)]
    history = [p for p in plans if _terminal(p)]
    dropped_live = max(0, len(live) - PLAN_CAP)
    if dropped_live:
        warnings.append(
            f"active plan cap {PLAN_CAP} exceeded on write; dropped "
            f"{dropped_live} of the oldest active plan(s)")
        live = live[-PLAN_CAP:]
    # Identity, not equality: two plans may legitimately be equal dicts.
    keep = {id(p) for p in live} | {id(p) for p in history[-PLAN_HISTORY_CAP:]}
    return [p for p in plans if id(p) in keep]


def apply_plan_ops(ctx, scene, clock):
    """Persist grounded `open|cancel` operations for the reactive rung.

    Called inside the primary turn transaction. It performs no model work and
    stores frame-scoped world KV, so checkpoints/branches/archive inherit the
    state without a parallel persistence mechanism.
    """
    from core.db import wget, wset
    from world.living_world import living_world_allows, living_world_config

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

    for index, raw in enumerate(raw_ops[:PLAN_OPS_PER_BEAT]):
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
        wset(cid, PLAN_KEY, _truncate_plans(plans, warnings))
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
    from core.db import qtx, wget, wset
    from world.gaps import LAST_SEEN_KEY
    from world.living_world import (living_world_allows, living_world_config,
                              mint_consequences)
    from world.mechanics import stable_event_key

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
    from core.db import wget, wset
    from story.scene import dialogue_config, offscreen_life_allows

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
    from core.db import q

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
    from story.character_schema import (character_name_from_text,
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
    from world.gaps import gap_for
    from llm.providers import chat_complete

    trail = gap_for(cid, subject.get("kind", "character"), subject["id"],
                    since_turn, until_turn, scene=scene, frame_id=frame_id)
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

    sys = get_prompt("offscreen_profile")
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
    from story.character_schema import cast_entity_id, character_name_from_text
    from core.db import q

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
    from story.character_schema import character_offscreen_agent
    from core.db import wget, wget_for_frame

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
    from story.character_schema import character_tier

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
    from core.db import q

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
    from world.gaps import LAST_SEEN_KEY
    from core.db import wget, wget_for_frame

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
    from story.scene import dialogue_config, offscreen_life_allows
    from world.spatial import room_of

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

    from story.character_schema import persona_name
    from core.db import wget, wget_for_frame
    from story.scene import persona_of

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
    from world.gaps import LAST_SEEN_KEY

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
        from core.db import active_frame_id
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
    from core.db import q, wget

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
    if jobs.story_rewound_past(base_turn, current):
        logger.info(
            "profile ticks discarded: chat=%s base_turn=%s current=%s "
            "(rolled back)", cid, base_turn, current)
        return {"written": 0, "discarded": len(events)}
    written = append_offscreen_log(
        cid, base_turn, epoch_id or f"tick:{cid}:{base_turn}", events,
        rung="profile")
    return {"written": len(written)}


#: Everything a paid off-screen tick may know. An ALLOWLIST, because
#: "fail-closed" means a field nobody thought about is absent rather than
#: present: a denylist grows a hole every time the payload gains a key, and the
#: hole is silent. The roadmap names the exclusions -- no player position, no
#: recent action, no private perception, no objective event this mind did not
#: witness, no other mind's state -- and the way to honour a list of
#: exclusions is to never build the thing they would have to be removed from.
AGENT_CONTEXT_KEYS = (
    "identity",        # who they are, from their own sheet
    "psychology",      # their own interior
    "drive",           # their own, singular
    "memories",        # their own autobiographical rows
    "beliefs",         # what they think is true, including wrongly
                       #   (state["interior"]["beliefs"] -- the only place
                       #   commit_memory writes one)
    "plans",           # authored plans they own
    "mind_models",     # their own theory of other minds -- the DERIVED view
                       #   only (decay-applied leading + competitors, claim and
                       #   current confidence), never the raw ledger. Argument:
                       #   docs/design/DESIGN_OFFSCREEN_MIND_MODELS.md
    "carried_reports", # what reached them, already degraded
    "last_known",      # where they were and when, by their own reckoning
    "elapsed_seconds", # how long they have been on their own
)


def agent_context(cid, entry, *, frame_id=None, clock=None, turn_idx=None):
    """The private context for one paid off-screen tick. Fail-closed.

    This is the firewall the whole `character_agent` rung rests on, and the
    failure it exists to prevent has a name in the design: "how did he know
    that". An absent mind that receives the player's position, or an event it
    did not witness, produces a villain who reacts before evidence arrives --
    and the prose will sound completely plausible while doing it, which is why
    this is built as a structure rather than as an instruction.

    Distance and importance may decide WHETHER this runs and how much is spent
    on it. They must never become content: a character who could tell how
    important they were would be reading the engine, not the world.

    Everything here is drawn from the character's own rows. Nothing is passed
    in from the turn, and there is deliberately no `scene` parameter to forget
    to leave out.
    """
    from core.db import q

    sheet = entry.get("sheet") or {}
    state = entry.get("state") if isinstance(entry.get("state"), dict) else {}
    identity = (sheet.get("identity") or {})
    psychology = (sheet.get("psychology") or {})
    char_id = entry.get("char_id")

    memories = []
    if char_id is not None:
        # `content` is the memories table's text column; this read shipped
        # asking for a `summary` column the table has never had, and every
        # test exercised it with char_id=None -- so the query that crashes
        # on any real candidate looked measured and was not.
        memories = [
            {"summary": r["content"], "turn_idx": r["turn_idx"]}
            for r in q("SELECT content, turn_idx FROM memories "
                       "WHERE chat_id=? AND char_id=? AND archived=0 "
                       "ORDER BY turn_idx DESC LIMIT 12",
                       (cid, char_id)) or []
        ]

    plans = [p for p in (_plans_for(cid, frame_id) or [])
             if isinstance(p, dict)
             and str(p.get("actor_id")) == str(entry.get("id"))
             and p.get("status") == "active"]

    # Their own theory of other minds. Every hypothesis in the ledger was
    # formed on this mind's own firewalled turns (`apply_mind_model_updates`
    # is its only writer), so handing it back opens no channel between minds
    # -- and withholding it made the absent mind conclude LESS than its own
    # evidence supports, the one repair the firewall's doctrine forbids. What
    # travels is the DERIVED view, built by the SAME function the on-screen
    # step uses (the `beliefs` entry above is what happens when one field
    # grows two shapes): decay-applied, because an off-screen tick is exactly
    # the moment the most time has passed and conviction must arrive as it
    # stands NOW, and claim+confidence only, because the raw ledger's
    # bookkeeping (first_seen_turn, formed_under) is the engine's, not theirs.
    from mind.theory_of_mind import mind_models_for_payload

    _elapsed_s = (clock or {}).get("elapsed_seconds")
    try:
        _elapsed_s = float(_elapsed_s) if _elapsed_s is not None else None
    except (TypeError, ValueError):
        _elapsed_s = None
    mind_models = mind_models_for_payload(
        state.get("mind_models") or {}, int(turn_idx or 0),
        elapsed_seconds=_elapsed_s)
    if frame_id is not None and mind_models:
        # The nonexistent_cast recognition backstop, exactly as the on-screen
        # step applies it (agents/character.py): in a frame where a cast
        # member does not yet exist, no native may be handed back a model
        # keyed to that identity. A key that is no cast member anywhere -- a
        # stranger's description, a place, the player -- keeps the
        # -1/"recognized" fallback, as on-screen.
        from core.frames import is_recognized_in_frame
        from story.scene import all_cast_name_to_id

        name_to_id = all_cast_name_to_id(cid)
        mind_models = {
            name: mm for name, mm in mind_models.items()
            if is_recognized_in_frame(name_to_id.get(name, -1), frame_id)
        }

    context = {
        "identity": {"name": identity.get("name") or "",
                     "uid": identity.get("uid") or ""},
        "psychology": psychology.get("traits") or {},
        "drive": psychology.get("drive") or {},
        "memories": memories,
        # `commit_memory` writes the belief ledger to state["interior"], and
        # only there. Reading a top-level `beliefs` handed this rung `{}` on
        # every tick it has ever run: measured live, 0 of 100 `chat_chars`
        # rows carry the top-level key and 31 carry the interior one. An
        # allowlist entry that reads the wrong path is not a smaller payload,
        # it is a field that documents a capability the mind never had.
        "beliefs": (state.get("interior") or {}).get("beliefs")
        or state.get("beliefs") or [],
        "plans": plans,
        "mind_models": mind_models,
        # Already degraded by `degradation` at the moment each was heard, so
        # this hands over what they believe rather than what is true.
        "carried_reports": [r for r in state.get("carried_reports") or []
                            if isinstance(r, dict)],
        "last_known": (state.get("offscreen_agent") or {}).get("last_known")
        or state.get("last_known") or {},
        "elapsed_seconds": float((clock or {}).get("elapsed_seconds") or 0.0),
    }
    # The allowlist is enforced here rather than trusted above, so a key added
    # to the dict later without being added to the list cannot ride out.
    return {k: v for k, v in context.items() if k in AGENT_CONTEXT_KEYS}


def _plans_for(cid, frame_id):
    from core.db import wget, wget_for_frame

    if frame_id is not None:
        return wget_for_frame(cid, PLAN_KEY, frame_id, []) or []
    return wget(cid, PLAN_KEY, []) or []


# ---------------------------------------------------------------------------
# The full `character_agent` rung: one reduced off-screen turn per selected
# opted-in mind. Selection (`full_agent_candidates`) and the fail-closed
# private context (`agent_context`) are above; this section is the paid
# producer and the atomic landing.
#
# TWO CALLS, TWO AUTHORITIES, exactly the on-screen split. The CHARACTER call
# sees `agent_context` and nothing else — it proposes an attempt or abandons
# its own plan, and it never decides its own success. The DIRECTOR call owns
# objective causality: it may see the scene graph, and it alone may declare a
# consequence — which still goes through `living_world.mint_consequences`,
# the same deterministic validator every other fuse passes, into
# `scheduled_events` under a STABLE id. The world's objective history
# (`world_events`) is never written here: a minted fuse is promoted by the
# ordinary commit spine when it fires, so this rung cannot grow a second
# writer of what objectively happened.
#
# EVERYTHING LANDS ONCE OR NOT AT ALL. One transaction; inside it, three
# guards in order — the epoch must still be current, the story must not have
# rolled back past the base turn, and the subject's own `last_epoch_id` must
# not already carry this epoch. That last guard is the reroll answer: a
# rerolled turn re-derives the SAME epoch id (the id is a hash of the same
# inputs) and resubmits the same job key, so whichever landing runs second
# finds the first one's stamp and discards itself. Where a restore rolled the
# stamp back along with everything else, re-landing is REPLAY, not
# duplication: the memory upserts on a stable `event_key`, the fuse is
# INSERT OR REPLACE on a stable id, and the log batch dedupes on its seed.
# ---------------------------------------------------------------------------

AGENT_RUNG = "agent"
AGENT_ATTEMPT_MAX_WORDS = 12
AGENT_OUTCOMES = ("success", "partial", "failure")
#: A tick is the character's own lived act; it matters to them more than a
#: passing observation and less than a scene they played on screen.
AGENT_MEMORY_SALIENCE = 0.6

_AGENT_OUTCOME_PHRASES = {
    "success": "it came off",
    "partial": "it half came off",
    "failure": "it did not come off",
}

#: Invariant text only — the variable half is the user payload, so the whole
#: system prompt is one cacheable constant.
# Compatibility views for audits/tests; runtime fetches the active pack.
#
# Resolved on ATTRIBUTE ACCESS, not at import: `get_prompt` reads the active
# preset out of `settings`, so binding these eagerly made `import offscreen`
# require a migrated database. See the same note in `importers.py`.
_COMPAT_PROMPT_IDS = {
    "_AGENT_ATTEMPT_SYS": "offscreen_agent_attempt",
    "_AGENT_ADJUDICATE_SYS": "offscreen_agent_adjudicate",
}


def __getattr__(name):
    pid = _COMPAT_PROMPT_IDS.get(name)
    if pid is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return get_prompt(pid)


def agent_proposal(cid, entry, context):
    """ONE character call proposing an attempt or plan revision. Fail closed.

    The user payload is `agent_context`'s allowlisted output and NOTHING
    else — no scene, no rooms list, no importance. The character names where
    they are headed in their own words; grounding that to a real room is the
    Director's, because a room roster would hand the mind rooms it never
    saw. The character's TIER selects which model pays for the call (spend,
    the one thing importance may decide) and never appears in the prompt.

    On any failure — provider, shape, a field that runs past its word bound
    — retries once and then returns None: an absent mind that could not be
    heard from simply stays as it was, which is cheaper and more honest
    than inventing an attempt for it.
    """
    from story.character_schema import character_tier
    from llm.providers import chat_complete

    tier = str(character_tier(entry.get("sheet") or {})).strip().casefold()
    role = f"character_{tier}" if tier in ("bg", "mid", "major") \
        else "character_mid"
    user = json.dumps(context, ensure_ascii=False)
    last_error = "no attempt"
    for _attempt in range(2):
        try:
            out = json.loads(chat_complete(
                role, get_prompt("offscreen_agent_attempt"), user,
                temperature=0.7,
                max_tokens=400))
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {str(exc)[:200]}"
            continue
        if not isinstance(out, dict):
            last_error = "output was not an object"
            continue
        attempt = " ".join(str(out.get("attempt") or "").split()).rstrip(".")
        if not attempt:
            last_error = "attempt missing or empty"
            continue
        if len(attempt.split()) > AGENT_ATTEMPT_MAX_WORDS:
            # The same write-path bound as the profile rung: a field long
            # enough to hold a sentence has been handed one.
            last_error = (f"attempt runs past {AGENT_ATTEMPT_MAX_WORDS} "
                          "words: narration is not state")
            continue
        plan_op = str(out.get("plan_op") or "keep").strip().casefold()
        return {
            "attempt": attempt,
            "toward": " ".join(str(out.get("toward") or "").split())[:80],
            "plan_op": plan_op if plan_op in ("keep", "abandon") else "keep",
            "plan_id": _plan_slug(out.get("plan_id")),
        }
    logger.info("agent proposal fell back: chat=%s subject=%s: %s",
                cid, entry.get("id"), last_error)
    return None


def agent_adjudication(cid, scene, entry, proposal, plan, clock):
    """ONE Director call resolving success and consequences. Fail closed.

    The Director is entitled to the objective scene — it owns causality and
    cannot resolve an attempt against a world it may not see. Its payload
    still carries no player position and no recent player act: resolving an
    absent character's errand needs the map, not the protagonist. Every
    field is validated deterministically on the way out; a verdict that
    cannot be read whole is retried once and then refused entire, because a
    half-validated adjudication landing is worse than no tick at all.
    """
    from llm.providers import chat_complete

    known_rooms = {str(r) for r in (scene or {}).get("rooms") or {}}
    state = entry.get("state") if isinstance(entry.get("state"), dict) else {}
    last_known = ((state.get("offscreen_agent") or {}).get("last_known")
                  or state.get("last_known") or {})
    active_plan = None
    if isinstance(plan, dict):
        active_plan = {
            "plan_id": plan.get("plan_id"),
            "objective": plan.get("objective"),
            "stage_index": plan.get("stage_index"),
            "stage_count": len(plan.get("stages") or []),
        }
    user = json.dumps({
        "actor": {"id": entry.get("id"),
                  "display": entry.get("display") or ""},
        "attempt": proposal.get("attempt"),
        "toward": proposal.get("toward"),
        "active_plan": active_plan,
        "last_known_room": str((last_known or {}).get("room") or ""),
        "elapsed_seconds": _as_seconds(clock),
        "rooms_available": sorted(known_rooms)[:40],
    }, ensure_ascii=False)
    last_error = "no verdict"
    for _attempt in range(2):
        try:
            out = json.loads(chat_complete(
                "director", get_prompt("offscreen_agent_adjudicate"), user,
                temperature=0.4,
                max_tokens=600))
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {str(exc)[:200]}"
            continue
        if not isinstance(out, dict):
            last_error = "output was not an object"
            continue
        outcome = str(out.get("outcome") or "").strip().casefold()
        if outcome not in AGENT_OUTCOMES:
            last_error = f"outcome {out.get('outcome')!r} is not a verdict"
            continue
        moved_to = str(out.get("moved_to") or "").strip()
        if moved_to and moved_to not in known_rooms:
            # The 'quiet office' rule at the earliest stage it can apply.
            last_error = f"moved_to {moved_to!r} is outside the world"
            continue
        consequence = out.get("consequence")
        if consequence is not None and not isinstance(consequence, dict):
            last_error = "consequence is not an object"
            continue
        return {
            "outcome": outcome,
            "moved_to": moved_to,
            "consequence": dict(consequence) if consequence else None,
            "advance_plan": bool(out.get("advance_plan")),
        }
    logger.info("agent adjudication fell back: chat=%s subject=%s: %s",
                cid, entry.get("id"), last_error)
    return None


def compose_agent_tick(who, attempt, outcome, moved_to=""):
    """Deterministic log spelling of one adjudicated tick — composition by
    CODE from the bounded fields, so the stored string asserts exactly what
    was adjudicated and nothing more. Prose for the player is minted at
    contact by the machinery already being paid for."""
    text = f"{who} — {attempt}: {outcome}"
    if moved_to:
        text += f" (at {moved_to})"
    return text


def compose_agent_memory(attempt, outcome):
    """The character's own autobiographical spelling of their tick.

    Deterministic for the same reason as `compose_agent_tick`: the memory a
    reroll re-mints must be byte-identical so the `event_key` upsert reads
    as the same memory, and a stored sentence a model wrote would be
    narration nothing player-facing ever authorized.
    """
    phrase = _AGENT_OUTCOME_PHRASES.get(outcome, "the outcome stayed unclear")
    return f"I set out to {attempt}; {phrase}."


def land_agent_tick(cid, entry, proposal, verdict, *, base_turn, turn_id,
                    epoch_id, frame_id, scene, clock,
                    prepared_memories=None):
    """Atomically land one adjudicated tick, or refuse the whole of it.

    Runs on the job thread with the scheduling turn's frame pinned. All
    writes — the fuse, the plan change, the last-tick state, the log record
    and the memory — share ONE transaction, so a failure in any of them
    lands none of them.

    Reroll safety lives here, in three guards evaluated INSIDE the
    transaction (the write lock serializes them against both a concurrent
    turn commit and a duplicate landing):

      * the epoch guard — a checkpoint restore brings back the previous
        epoch record, so work computed against a discarded epoch cannot
        land on the restored world;
      * the rollback guard — a story rewound past `base_turn` no longer
        contains the turn this tick advanced from;
      * the subject's own `last_epoch_id` stamp — the double-landing guard.
        A reroll re-derives the same epoch id and resubmits the same job;
        whichever landing runs second reads the first one's stamp on the
        character's fresh state and discards itself.
    """
    from core.db import q, qtx, transaction, wget, wset
    from world.living_world import mint_consequences
    from world.mechanics import stable_event_key
    from story.scene import set_char_state

    sid = str(entry.get("id") or "")
    display = str(entry.get("display") or "")
    char_id = entry.get("char_id")
    elapsed = _as_seconds(clock)
    with transaction():
        current_epoch = wget(cid, EPOCH_KEY, {}) or {}
        if str(current_epoch.get("epoch_id") or "") != str(epoch_id):
            logger.info(
                "agent tick discarded: chat=%s subject=%s epoch=%s "
                "current_epoch=%s (checkpoint/frame changed)",
                cid, sid, epoch_id, current_epoch.get("epoch_id"))
            return {"landed": False, "reason": "epoch_changed"}
        row = q("SELECT MAX(idx) AS idx FROM turns WHERE chat_id=?", (cid,),
                one=True)
        current = row["idx"] if row and row["idx"] is not None else None
        if jobs.story_rewound_past(base_turn, current):
            logger.info(
                "agent tick discarded: chat=%s subject=%s base_turn=%s "
                "current=%s (rolled back)", cid, sid, base_turn, current)
            return {"landed": False, "reason": "rolled_back"}
        # The double-landing guard reads FRESH state, and the write below
        # merges onto that same read — a landing must never write through a
        # copy captured at schedule time, or it would resurrect whatever the
        # intervening turns did to this character.
        state_row = q(
            "SELECT COALESCE(ccf.state, cc.state) AS cstate "
            "FROM chat_chars cc LEFT JOIN chat_char_frames ccf "
            "  ON ccf.chat_id=cc.chat_id AND ccf.char_id=cc.char_id "
            "  AND ccf.frame_id IS ? "
            "WHERE cc.chat_id=? AND cc.char_id=?",
            (frame_id, cid, char_id), one=True)
        if not state_row:
            return {"landed": False, "reason": "no_cast_row"}
        try:
            state = json.loads(state_row["cstate"] or "{}")
        except (TypeError, ValueError):
            state = {}
        if not isinstance(state, dict):
            state = {}
        agent_state = state.get("offscreen_agent") \
            if isinstance(state.get("offscreen_agent"), dict) else {}
        if str(agent_state.get("last_epoch_id") or "") == str(epoch_id):
            return {"landed": False, "reason": "already_landed"}

        # The Director's consequence — the ONLY channel by which this rung
        # changes the world — through the same deterministic validator every
        # other fuse passes, under a stable id so a replay overwrites its own
        # row instead of minting a sibling.
        minted_event_id = ""
        if verdict.get("consequence"):
            origin_room = verdict.get("moved_to") or str(
                ((agent_state.get("last_known") or {}) or {}).get("room")
                or "")
            rows, warnings = mint_consequences(
                cid, scene, frame_id, turn_id, base_turn, elapsed,
                [{**verdict["consequence"], "originator": sid}],
                player_room=origin_room)
            if rows:
                fuse = rows[0]
                fuse["event_id"] = stable_event_key(
                    "offscreen_agent", cid, frame_id, epoch_id, sid)
                fuse["seed"] = str(epoch_id)
                qtx(
                    "INSERT OR REPLACE INTO scheduled_events"
                    "(event_id,chat_id,due_at,kind,location_id,payload,seed,"
                    "status) VALUES(?,?,?,?,?,?,?,?)",
                    (fuse["event_id"], fuse["chat_id"], fuse["due_at"],
                     fuse["kind"], fuse["location_id"], fuse["payload"],
                     fuse["seed"], fuse["status"]),
                )
                minted_event_id = fuse["event_id"]
            else:
                for warning in warnings:
                    logger.info("agent consequence refused: chat=%s "
                                "subject=%s: %s", cid, sid, warning)

        plans = [dict(p) for p in wget(cid, PLAN_KEY, []) or []
                 if isinstance(p, dict)]
        plans_changed = False
        for plan in plans:
            if str(plan.get("actor_id")) != sid \
                    or plan.get("status") != "active":
                continue
            history = [h for h in plan.get("history") or []
                       if isinstance(h, dict)]
            if any(str(h.get("epoch_id") or "") == str(epoch_id)
                   for h in history):
                continue  # belt behind the state stamp: never double-advance
            if proposal.get("plan_op") == "abandon" and (
                    not proposal.get("plan_id")
                    or proposal["plan_id"] == plan.get("plan_id")):
                plan["status"] = "cancelled"
                event = "abandoned_offscreen"
            elif verdict.get("advance_plan"):
                plan["stage_index"] = int(plan.get("stage_index") or 0) + 1
                event = "stage_advanced_offscreen"
                if plan["stage_index"] >= len(plan.get("stages") or []):
                    plan["status"] = "completed"
            else:
                continue
            plan["updated_turn"] = int(base_turn)
            history.append({"event": event, "turn": int(base_turn),
                            "epoch_id": str(epoch_id),
                            "outcome": verdict.get("outcome")})
            plan["history"] = history[-20:]
            plans_changed = True
        if plans_changed:
            wset(cid, PLAN_KEY, plans)

        # Movement lands in the character's OWN trail, never in
        # `scene.positions`: a dormant body holds no live position, and an
        # off-screen writer of scene positions would be the missing third
        # warrant the module docstring refuses to build by accident.
        last_known = dict((agent_state.get("last_known")
                           or state.get("last_known") or {}) or {})
        if verdict.get("moved_to"):
            last_known = {"room": verdict["moved_to"],
                          "turn": int(base_turn),
                          "elapsed_seconds": elapsed}
        state["offscreen_agent"] = {
            **agent_state,
            "last_turn": int(base_turn),
            "last_epoch_id": str(epoch_id),
            "last_known": last_known,
        }
        set_char_state(cid, char_id, json.dumps(state, ensure_ascii=False),
                       frame_id=frame_id)

        record = {
            "disposition": "provisional",
            "subject": {"kind": "character", "id": sid,
                        **({"display": display} if display and
                           display.casefold() != sid.casefold() else {})},
            "basis": "model",
            "producer": "offscreen.land_agent_tick",
            "state": {"doing": proposal.get("attempt") or "",
                      "at": verdict.get("moved_to") or "",
                      "manner": ""},
            "outcome": verdict.get("outcome"),
            "actor": sid,
            "actor_display": display,
            "tick": compose_agent_tick(
                display or sid, proposal.get("attempt") or "",
                verdict.get("outcome") or "", verdict.get("moved_to") or ""),
            **({"events": [{"event_id": minted_event_id}]}
               if minted_event_id else {}),
        }
        written = append_offscreen_log(
            cid, base_turn, f"{epoch_id}:{sid}", [record], rung=AGENT_RUNG)

        if prepared_memories:
            from mind.memory import add_memories_batch

            add_memories_batch(prepared_batch=prepared_memories)

    return {"landed": True, "event_id": minted_event_id,
            "moved_to": verdict.get("moved_to") or "",
            "log_written": len(written)}


def schedule_agent_ticks(ctx, epoch=None):
    """Queue this epoch's paid full-agent ticks. Returns Job or None.

    Called from the commit tail beside `schedule_profile_ticks`, after the
    turn's facts are durable; a failure is a warning, never a rollback, and
    a turn starting never cancels the job. Three gates compose before any
    model is asked, and each fails toward not spending:

      * the shared world epoch — no epoch, no job, so every tick carries
        one base turn, one frame and one epoch id from birth;
      * `living_world_allows(..., "antagonist_ladder", "ceiling")` — which
        itself composes the chat's `offscreen_life=character_agent` ceiling
        through `LIVING_WORLD_REQUIRES`, so no second copy of that rule
        exists to drift;
      * `full_agent_candidates` — the card opt-in and the private reason,
        capped by `max_offscreen_actors`. A character existing is not a
        reason; an owned active plan or fresh carried evidence is.
    """
    from world.living_world import living_world_allows, living_world_config
    from story.scene import dialogue_config

    cid = ctx.chat.id
    turn_idx = ctx.turn.idx
    turn_id = ctx.turn.id
    frame_id = ctx.turn.frame_id
    epoch = epoch if isinstance(epoch, dict) else {}
    if not epoch.get("opportunity"):
        return None
    epoch_id = str(epoch.get("epoch_id") or "").strip()
    if not epoch_id:
        epoch["agent_skip"] = "missing_epoch_id"
        return None
    if not living_world_allows(
            living_world_config(cid), "antagonist_ladder", "ceiling"):
        epoch["agent_opportunity"] = False
        return None
    epoch["agent_opportunity"] = True
    cap = int((dialogue_config(cid) or {}).get("max_offscreen_actors", 3) or 0)
    if cap <= 0:
        epoch["agent_skip"] = "cap_zero"
        return None
    candidates = full_agent_candidates(cid, frame_id=frame_id, cap=cap)
    epoch["agent_candidates"] = len(candidates)
    if not candidates:
        epoch["agent_skip"] = "no_private_reason"
        return None

    from core.db import wget, wget_for_frame

    scene = (wget_for_frame(cid, "scene", frame_id, {})
             if frame_id is not None else wget(cid, "scene", {})) or {}
    clock = wget(cid, "simulation_clock", {}) or {}

    def _produce(job):
        # Same frame pin as the profile producer: the job thread's fresh
        # contextvars context would otherwise land frame-scoped writes in
        # the present frame's world.
        from core.db import active_frame_id
        from world.mechanics import stable_event_key

        token = active_frame_id.set(frame_id)
        try:
            landed = skipped = 0
            for cand in candidates:
                if job.cancelled.is_set():
                    break
                context = agent_context(
                    cid, cand, frame_id=frame_id, clock=clock,
                    turn_idx=turn_idx)
                proposal = agent_proposal(cid, cand, context)
                if not proposal:
                    skipped += 1
                    continue
                plan = next(iter(context.get("plans") or []), None)
                verdict = agent_adjudication(
                    cid, scene, cand, proposal, plan, clock)
                if not verdict:
                    skipped += 1
                    continue
                prepared = None
                if cand.get("char_id") is not None:
                    from mind.memory import prepare_memories_batch

                    # Embedding is provider work and stays OUTSIDE the
                    # landing transaction, per the commit path's own rule.
                    prepared = prepare_memories_batch([{
                        "chat_id": cid,
                        "char_id": cand["char_id"],
                        "turn_id": turn_id,
                        "turn_idx": turn_idx,
                        "kind": "episodic",
                        "provenance": "witnessed",
                        "salience": AGENT_MEMORY_SALIENCE,
                        "content": compose_agent_memory(
                            proposal["attempt"], verdict["outcome"]),
                        "location": verdict.get("moved_to") or "",
                        "event_key": stable_event_key(
                            "offscreen_agent_memory", cid, frame_id,
                            epoch_id, cand["id"]),
                        "frame_id": frame_id,
                    }])
                result = land_agent_tick(
                    cid, cand, proposal, verdict, base_turn=turn_idx,
                    turn_id=turn_id, epoch_id=epoch_id, frame_id=frame_id,
                    scene=scene, clock=clock, prepared_memories=prepared)
                if result.get("landed"):
                    landed += 1
                else:
                    skipped += 1
            return {"landed": landed, "skipped": skipped,
                    "candidates": len(candidates)}
        finally:
            active_frame_id.reset(token)

    job = jobs.submit(cid, f"offscreen_agent:{epoch_id}", _produce,
                      base_turn=turn_idx)
    epoch["agent_scheduled"] = True
    return job
