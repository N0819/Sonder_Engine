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
  * profile summary           -- one bounded call, out of band, only for
                                 subjects the resolution function scores
                                 ``medium``. No psychology run, no
                                 adjudication, and STRUCTURALLY unable to
                                 emit a consequence: its output shape has
                                 nowhere to put an alliance, and the record
                                 it writes is the provisional tier's, which
                                 ``canon_provenance.validate_provisional``
                                 refuses to let carry deltas, standing
                                 intentions or ratified claims.
  * full agent                -- NOT BUILT. Director-adjudicated; the only
                                 rung that may ever change the world.

THE FIREWALL HOLDS IN BOTH DIRECTIONS. Nothing here hands an absent
character the player's location or recent acts: the profile rung reads the
subject's own profile surface and the deterministic trail of THEIR moves.
The player's room is read only by the DISTANCE axis -- which decides spend,
not content, so it cannot make anyone prescient; being near the player buys
a character a better-lit tick, never knowledge of them.

TICKS DESCRIBE, NEVER COMMIT (section 1.0.1). No write from this module
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

import json
import random

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
        mine = [i for i in (intentions or []) if _intention_mentions(i, needles)]
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
        log.append({"turn": int(turn_idx), "seed": str(seed),
                    "rung": rung, "events": kept})
        wset(cid, "offscreen_log", log)
    return kept


def _adjudicated_event_ids(cid):
    """Every event id something already minted: the citable set.

    ``scheduled_events`` is the only id-bearing event ledger with a runtime
    writer (``world_events`` has none, anywhere -- do not build one here; the
    finding is on the record in gaps.py and the proposal). A provisional
    record may CITE these; it may not mint its own.
    """
    from db import q

    return {str(r["event_id"]) for r in q(
        "SELECT event_id FROM scheduled_events WHERE chat_id=?", (cid,))}


# ---------------------------------------------------------------------------
# Step 3a: the profile-summary rung. One call, no psychology, no consequence.
# ---------------------------------------------------------------------------

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

    Returns a PROVISIONAL record (validated by the caller's write path). On
    any failure -- provider, shape, a room outside the world -- falls back
    to the deterministic gap record after one retry: a deterministic "she
    was elsewhere" is worth more than a plausible lie (section 1.0.3).
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
        "You write ONE plausible account of what a character has been doing "
        "off screen, from their public profile and a deterministic trail. "
        "Routine and manner only -- what they would do, as they would do it. "
        "Do NOT invent outcomes, alliances, acquisitions, injuries, "
        "arrivals, discoveries, or any change to the world: describe "
        "activity, never consequence. The character does not know where any "
        "other person is or what anyone else has done. Any room you mention "
        "MUST be an id from rooms_available; mention no room otherwise. "
        'Output STRICT JSON {"summary": "<1-2 sentences>", '
        '"rooms": ["<ids used, possibly empty>"]}'
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
        summary = str(out.get("summary") or "").strip()
        rooms = out.get("rooms") if isinstance(out.get("rooms"), list) else []
        bad = [r for r in rooms if str(r) not in known_rooms]
        if not summary:
            last_error = "empty summary"
            continue
        if bad:
            last_error = f"named rooms outside the world: {bad[:3]!r}"
            continue
        record["basis"] = "model"
        record["summary"] = summary[:600]
        return record
    record["inputs"] = {"fell_back_from": f"profile: {last_error}"}
    logger.info("profile tick fell back: chat=%s subject=%s: %s",
                cid, subject.get("id"), last_error)
    return record


# ---------------------------------------------------------------------------
# The producer: cadenced, out of band, parallel with turns, never cancelled.
# ---------------------------------------------------------------------------

#: Produce every ~3 turns (section 1.0.2: production bounds cost and gives
#: the world a heartbeat; DELIVERY still happens at re-contact). A pure
#: function of the turn index -- no wall clock, no unseeded RNG -- so rerun
#: and reroll cannot silently change whether the world was alive.
TICK_CADENCE_TURNS = 3


def tick_due(turn_idx):
    """Pure cadence gate."""
    try:
        idx = int(turn_idx)
    except (TypeError, ValueError):
        return False
    return idx > 0 and idx % TICK_CADENCE_TURNS == 0


def dormant_subjects(cid, frame_id=None):
    """The dormant cast as subjects: [{"id", "display", "sheet"}].

    Id-shaped from birth via ``cast_entity_id`` -- the display name rides
    along for prose, it never keys anything.
    """
    from character_schema import cast_entity_id, character_name_from_text
    from db import q

    out = []
    for row in q(
        "SELECT cc.char_id AS char_id, COALESCE(cc.sheet,ch.sheet) AS sheet "
        "FROM chat_chars cc JOIN characters ch ON ch.id=cc.char_id "
        "LEFT JOIN chat_char_frames ccf "
        "  ON ccf.chat_id=cc.chat_id AND ccf.char_id=cc.char_id AND ccf.frame_id IS ? "
        "WHERE cc.chat_id=? AND COALESCE(ccf.status, cc.status)='dormant'",
        (frame_id, cid),
    ):
        try:
            sheet = json.loads(row["sheet"] or "{}")
        except Exception:
            sheet = {}
        out.append({
            "id": cast_entity_id(sheet, row["char_id"]),
            "display": character_name_from_text(row["sheet"] or "{}"),
            "sheet": sheet,
            "char_id": row["char_id"],
        })
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


def schedule_profile_ticks(ctx):
    """Queue this turn's out-of-band profile ticks. Returns the Job or None.

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
    if not tick_due(turn_idx):
        return None
    cfg = dialogue_config(cid) or {}
    cap = int(cfg.get("max_offscreen_actors", 3) or 0)
    if not offscreen_life_allows(cfg.get("offscreen_life"), "stochastic") or cap <= 0:
        return None

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
        return None
    intents = wget(cid, "standing_intentions", []) or []
    candidates = profile_candidates(
        cid, scene, player_room, intents, frame_id=frame_id, cap=cap)
    if not candidates:
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
            since_by_subject[cand["id"]] = max(0, turn_idx - TICK_CADENCE_TURNS)

    def _produce(job):
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
            summary = record.get("summary") or ""
            if record.get("basis") == "unavailable" or not summary:
                continue
            events.append({**record, "actor": cand["id"],
                           "actor_display": cand.get("display", ""),
                           "tick": summary})
        return land_profile_ticks(cid, turn_idx, events)

    return jobs.submit(cid, f"offscreen_profile:{turn_idx}", _produce,
                       base_turn=turn_idx)


def land_profile_ticks(cid, base_turn, events):
    """Write produced ticks, unless the world rolled back underneath them.

    The rollback guard (section 1.0.2 hazard 2): a tick computed against
    turn N describes a future that no longer happens once the player rolls
    back past N. ``base_turn`` makes that decidable; this is the landing
    check that acts on it — discard, loudly, never commit. The engine's own
    precedent is the checkpoint restore that silently undid a completed
    embedding rebuild.
    """
    from db import q

    if not events:
        return {"written": 0}
    row = q("SELECT MAX(idx) AS idx FROM turns WHERE chat_id=?", (cid,),
            one=True)
    current = row["idx"] if row and row["idx"] is not None else None
    if current is not None and int(current) < int(base_turn):
        logger.info(
            "profile ticks discarded: chat=%s base_turn=%s current=%s "
            "(rolled back)", cid, base_turn, current)
        return {"written": 0, "discarded": len(events)}
    written = append_offscreen_log(
        cid, base_turn, f"tick:{cid}:{base_turn}", events, rung="profile")
    return {"written": len(written)}
