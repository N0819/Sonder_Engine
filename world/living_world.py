"""The living world: settings for five approaches and their built floors.

Approach A's pure functions live in ``routines.py``; C's physical witnessed
carrier envelopes live in ``carriers.py``; E's reactive executor lives in
``offscreen.py``. This module owns the shared config, B's fuse mint, and D's
obligation ledger.

``docs/design/DESIGN_LIVING_WORLD.md`` is the argument; §9 there records the
author's constraints verbatim. The floors landed here are deterministic,
seeded where they draw, and free at rest — every model-assisted ceiling is
declared in the ladder below and deliberately unbuilt, exactly as
``scene.OFFSCREEN_LIFE_BUILT`` already does for the offscreen ladder: the
declared/built split is stated by the engine, not by a menu that drifts.

WHO MAY LEARN WHAT, AND BY WHAT ROUTE (the epistemic contract, enforced
structurally — each rule names the structure that holds it):

  * A consequence fuse firing is LAYER-1 FACT: it happened, at a location,
    at a clock time, whether or not anyone was there to see it. The row is
    Director-caused (``state_diff.consequences`` is adjudicated output) and
    deterministically fired, so it carries ``disposition: resolved_fact`` —
    the provenance tier that phase 2's invented gossip will NOT carry.
  * Nobody LEARNS of a fired fuse merely because it is true. The firing
    writes no notice unless the player is standing at its location when it
    fires (walking in on it — §0.2's in-progress surface). Every other
    delivery is at contact: the residue assembler and the gap skeleton read
    fired rows only for the location being entered or the subject being
    asked about. There is no broadcast path to write to — that is the
    structure, not a rule someone must remember.
  * A place's accumulated obligations are real durable state, written as
    fuses fire — BEFORE anyone asks, so a later rumour has a truth to be a
    distortion of — but they are knowledge held by NOBODY. Their single
    consumer is the mapping seam at generation time (``owed_history``),
    where the place itself is made to show its aftermath. Arrival is the
    earning event; no character payload reads this ledger, and a test pins
    that no agent module but mapping names it.
  * Nothing here privileges the player. A fuse's fields are properties of
    the EVENT — what, where, when, who caused it, what was publicly visible
    — never of who it might matter to. There is no priority, importance or
    reputation field, and phase 2's propagation must compute interest from
    the event's own properties (the author's constraint: the player earns
    reputation downstream of propagation, or is correctly nobody).

CARRIER-READY BY SHAPE. Information moves by carriers along routes, never by
timer alone. Every fuse payload and obligation row therefore
already carries {what, where, a time, origin, originator, witnessed,
disposition} — the pickup surface a courier needs — and the payloads are
JSON, so a route-bound {carrier, route} pair extends them without
migration. The built C floor emits only a non-empty witnessed surface to a
registered character physically present when it lands; that envelope follows
the holder's actual scene movement and only their private agent reads it.
Anonymous crowd/message carriers and copy-time degradation remain later layers.
"""

from __future__ import annotations

import json

from core.logging_utils import logger
from world.mechanics import stable_event_key

# ---------------------------------------------------------------------------
# The settings ladder: author-selectable world-generation approaches.
# ---------------------------------------------------------------------------

#: Ordered: a depth permits everything below it. ``ceiling`` is the
#: model-assisted tier of the SAME mechanism, off the critical path — not a
#: second mechanism (design doc, preamble to §1).
LIVING_WORLD_DEPTHS = ("off", "floor", "ceiling")

#: Rumour transport is no longer an optional approach. It is core epistemic
#: physics owned by Charter people and the shared physical carrier rail; a
#: setting that can disable witnessing, speech or letters makes the world
#: incoherent. The remaining keys are author-selectable generation policies.
LIVING_WORLD_APPROACHES = (
    "routine_residue",        # A: the world's default motion
    "scheduled_consequence",  # B: the world as a delay line
    "place_obligations",      # D: the lorebook edge owes a history
    "antagonist_ladder",      # E: plans that advance unwatched
)

#: Which depths actually DO something today. Kept beside the ladder, like
#: ``scene.OFFSCREEN_LIFE_BUILT``, so an unbuilt tier cannot quietly start
#: reading as built when it ships and nobody updates a menu. Physical carrier
#: behavior is core and therefore absent from this table. E's floor
#: advances only Director-adjudicated stages authored from a character's own
#: on-screen declaration; its adaptive ceiling is built on the core carrier
#: network
#: (``offscreen.schedule_agent_ticks``): an opted-in dormant mind with a
#: private reason gets one reduced turn — fail-closed private context, one
#: character call, one Director adjudication, one atomic landing.
LIVING_WORLD_BUILT = {
    "routine_residue": frozenset({"floor"}),
    "scheduled_consequence": frozenset({"floor"}),
    "place_obligations": frozenset({"floor"}),
    "antagonist_ladder": frozenset({"floor", "ceiling"}),
}

#: What each approach and depth buys, and what it costs — served to the UI
#: with the config so the menu renders the engine's own ladder rather than
#: a copy that drifts (the ``offscreen_life_levels`` convention).
LIVING_WORLD_DESCRIPTIONS = {
    "routine_residue": {
        "label": "Routine and residue",
        "floor": "Rooms drift on the clock while unwatched — fires burn "
                 "down, crowds thin and swell — and re-entering delivers "
                 "the difference as present state, never a report.",
        "ceiling": "Familiar places also advance their social life between "
                   "visits (who is feuding, what the barkeep is short of).",
        "cost": "floor: free — no model calls; ceiling: ~1 call per "
                "familiar place per scene boundary, off the turn path",
    },
    "scheduled_consequence": {
        "label": "Scheduled consequence",
        "floor": "This beat's causes set offscreen effects on the clock — "
                 "the patrol doubles in three days, the river gate closes "
                 "in a week — and they genuinely happen, seen or "
                 "not.",
        "ceiling": "A significant consequence can mint a second-order one "
                   "when it lands (fire, then prices, then the bread "
                   "queue).",
        "cost": "floor: free — rows on the existing event clock; ceiling: "
                "~1 call per significant fired consequence, off the turn "
                "path",
    },
    "place_obligations": {
        "label": "Places that owe a history",
        "floor": "Somewhere you have never been still accrues what "
                 "happened there; first arrival finds the aftermath "
                 "already in place, in the present tense.",
        "ceiling": "A place you are clearly heading toward is generated "
                   "early, off the path, so first arrival is instant and "
                   "owes its history better.",
        "cost": "floor: free while unvisited — arrival costs what arrival "
                "already cost; ceiling: the same generation call, paid "
                "early",
    },
    "antagonist_ladder": {
        "label": "Antagonist ladder",
        "floor": "A named few advance authored plans on schedule, acting "
                 "only on what has actually reached them — a race you can "
                 "genuinely lose.",
        "ceiling": "Those few think between visits: declaration, "
                   "adjudication, and a remembered week at re-contact.",
        "cost": "floor: ~2 calls per dramatic event; ceiling: ~2–4 calls "
                "per turn amortized at 2–3 tracked actors, all off the "
                "turn path",
    },
}

#: The offscreen-life rung each depth spends at. The two settings are two
#: axes of ONE question — ``scene.OFFSCREEN_LIFE_LADDER`` answers how much
#: authority off-screen work may have, this module answers which machinery
#: does it — and before this table nothing said which governed: B's floor
#: minted fuses that genuinely fired while the ladder said ``inert``
#: ("nothing happens off screen"). The assignments are the ladder's own
#: descriptions, not new policy: the floors are clock-work, and the
#: ``deterministic`` rung's text names them verbatim ("scheduled effects
#: only — arrivals, expiry, news latency"); the ceilings are model-assisted
#: invention without plans, the ``stochastic`` tier's authority; and E is
#: the ``character_agent`` rung wearing this module's vocabulary — the
#: design doc §5 names E's rungs 2 and 3 ``reactive`` and
#: ``character_agent`` outright, so gating E anywhere lower would be the
#: two-vocabularies drift the ladder comment in ``scene.py`` warns against.
LIVING_WORLD_REQUIRES = {
    "routine_residue": {"floor": "deterministic", "ceiling": "stochastic"},
    "scheduled_consequence": {"floor": "deterministic",
                              "ceiling": "stochastic"},
    "place_obligations": {"floor": "deterministic", "ceiling": "stochastic"},
    "antagonist_ladder": {"floor": "reactive",
                          "ceiling": "character_agent"},
}

#: All off. The engine never did any of this before the setting existed, and
#: a merge must not silently change a running story — the same reasoning
#: that made ``stochastic`` the offscreen default (what the engine already
#: did) makes ``off`` the default here (it did nothing).
LIVING_WORLD_DEFAULT = "off"

#: World-KV key for the per-chat config.
LIVING_WORLD_KEY = "living_world"

#: The key the off-screen ceiling rides on INSIDE a config dict handed
#: around this module. It is never stored under ``LIVING_WORLD_KEY`` —
#: ``normalize_living_world`` strips it from anything written back, so the
#: ceiling has exactly one durable spelling (``dialogue_config``'s) and
#: can never shadow it from a second row. Absent, it reads as the ladder
#: default, exactly as ``scene.normalize_offscreen_life`` treats an
#: unreadable level.
OFFSCREEN_CEILING_KEY = "offscreen_life"


def normalize_living_world(stored):
    """Coerce a stored or submitted config to {approach: depth}, total.

    Unknown approaches are dropped; an unreadable depth falls to the
    DEFAULT. Here — unlike ``scene.normalize_offscreen_life``, whose
    default is the live middle of its ladder — the default IS off, so a
    typo does silence a feature; the PUT route returns the normalized
    config so what stuck is visible immediately rather than fifty turns
    later. Dropping unknown keys is also what keeps the STORED config
    pure: ``OFFSCREEN_CEILING_KEY`` (folded in by ``living_world_config``
    at read time) never survives a write, so the ceiling cannot acquire a
    second durable spelling that shadows ``dialogue_config``'s.
    """
    out = {}
    stored = stored if isinstance(stored, dict) else {}
    for approach in LIVING_WORLD_APPROACHES:
        depth = str(stored.get(approach) or "").strip().casefold()
        out[approach] = depth if depth in LIVING_WORLD_DEPTHS \
            else LIVING_WORLD_DEFAULT
    return out


def living_world_config(cid):
    """The chat's mechanism config with the off-screen authority ceiling
    folded in ON THE WAY IN (the ``canonical_url`` rule): every gate that
    fetches a config composes both axes without remembering to call a
    second helper — ``commit_transit_sweep``'s mint gate, the Director's
    residue gate and the mapping seam all compose because the dict they
    already hold carries the ceiling. The ceiling's durable home stays
    ``dialogue_config``; it rides here only between read and use.
    """
    from core.db import wget
    from story.scene import dialogue_config

    config = normalize_living_world(wget(cid, LIVING_WORLD_KEY, None) or {})
    config[OFFSCREEN_CEILING_KEY] = dialogue_config(cid)["offscreen_life"]
    return config


def effective_depth(config, approach):
    """The depth that actually RUNS: the requested depth, lowered to the
    highest depth at or below it that is both BUILT and within the story's
    off-screen authority ceiling (``LIVING_WORLD_REQUIRES``). Two clamps,
    one convention: setting an unbuilt ceiling behaves as the floor and
    MARKS the story as wanting the ceiling — the ``character_agent``
    convention, so landing a ceiling later is opt-in on a chat that
    already asked rather than a surprise in every story — and a depth the
    ladder does not permit is capped the same visible way, never silently
    run: the ladder is the single answer to how much off-screen work MAY
    do, and these mechanisms answer only which machinery does it.
    """
    from story.scene import normalize_offscreen_life, offscreen_life_allows

    raw = config if isinstance(config, dict) else {}
    ceiling = normalize_offscreen_life(raw.get(OFFSCREEN_CEILING_KEY))
    requested = normalize_living_world(raw).get(approach,
                                                LIVING_WORLD_DEFAULT)
    built = LIVING_WORLD_BUILT.get(approach, frozenset())
    for depth in reversed(
            LIVING_WORLD_DEPTHS[:LIVING_WORLD_DEPTHS.index(requested) + 1]):
        if depth == "off":
            return depth
        if depth in built and offscreen_life_allows(
                ceiling, LIVING_WORLD_REQUIRES[approach][depth]):
            return depth
    return "off"


def living_world_allows(config, approach, depth="floor"):
    """Does the config's EFFECTIVE depth for ``approach`` permit ``depth``.

    Ordered comparison, like ``scene.offscreen_life_allows``. Unknown
    approaches and depths permit nothing — a spend gate must fail toward
    not spending.
    """
    if approach not in LIVING_WORLD_APPROACHES \
            or depth not in LIVING_WORLD_DEPTHS:
        return False
    have = LIVING_WORLD_DEPTHS.index(effective_depth(config, approach))
    return have >= LIVING_WORLD_DEPTHS.index(depth)


def living_world_levels(config=None):
    """The ladder as the UI renders it: what is on, what it costs, what is
    merely declared, and what the off-screen ceiling caps — per approach,
    from the engine's own tables. ``requires``/``permitted`` ride along so
    a mechanism set above the ceiling displays as clamped rather than
    silently ignored: the clamp the menu shows is the clamp
    ``effective_depth`` will apply, never a copy that drifts."""
    from story.scene import normalize_offscreen_life, offscreen_life_allows

    raw = config if isinstance(config, dict) else {}
    ceiling = normalize_offscreen_life(raw.get(OFFSCREEN_CEILING_KEY))
    values = normalize_living_world(raw)
    composed = {**values, OFFSCREEN_CEILING_KEY: ceiling}
    out = []
    for approach in LIVING_WORLD_APPROACHES:
        desc = LIVING_WORLD_DESCRIPTIONS[approach]
        out.append({
            "approach": approach,
            "label": desc["label"],
            "value": values[approach],
            "effective": effective_depth(composed, approach),
            "cost": desc["cost"],
            "depths": [
                {"value": depth,
                 "description": desc.get(depth, ""),
                 "built": depth in LIVING_WORLD_BUILT[approach],
                 "requires": LIVING_WORLD_REQUIRES[approach][depth],
                 "permitted": offscreen_life_allows(
                     ceiling, LIVING_WORLD_REQUIRES[approach][depth])}
                for depth in LIVING_WORLD_DEPTHS if depth != "off"
            ],
        })
    return out


# ---------------------------------------------------------------------------
# Approach B floor: the fuse mint. Deterministic validation of an
# adjudicated declaration; firing lives in mechanics._fire_due_events.
# ---------------------------------------------------------------------------

CONSEQUENCE_KIND = "consequence"

#: At most this many fuses land per turn, however many were declared. Every
#: beat minting fuses turns a quiet story into a ratchet; most beats must
#: mint nothing (the ``pick_background_reactor`` shape).
MINT_CAP_PER_TURN = 2

#: Due bounds, clamped rather than refused (a legitimate intent badly
#: quantified should land at an honest distance, not vanish). Below one
#: in-story hour a consequence is this beat's own business and belongs in
#: the state_diff proper; past thirty in-story days it is a plot, and plots
#: belong to standing intentions and authored events. The declared value is
#: kept on the payload so the clamp is visible after the fact.
DUE_MIN_SECONDS = 3600.0
DUE_MAX_SECONDS = 30 * 86400.0

_WHAT_MAX = 140
_WITNESSED_MAX = 200


def _squeeze(text, cap):
    return " ".join(str(text or "").split())[:cap]


def mint_consequences(cid, scene, frame_id, turn_id, turn_idx,
                      elapsed_seconds, declarations, player_room=None):
    """Validate declared consequences into scheduled_events rows.

    Deterministic; no model, no I/O beyond subject resolution. Returns
    ``(rows, warnings)`` — rows in the shape the sweep's schedule op
    inserts, warnings for every declaration refused and why (a dropped
    fuse must be sayable, or minting failures look like a quiet world).

    The location gate is ``subjects.resolve_subject``: ``where`` must
    resolve to a generated room (kind ``room``, id ``room_uid``/scene id)
    or an ungenerated lorebook place (kind ``place``, id ``entry_uid``) —
    the 'quiet office' rule, applied at the write path. ``origin`` is
    where the CAUSE happened (this beat's stage), an event property; it is
    never read to decide anything about the player.
    """
    from world.subjects import resolve_subject

    rows, warnings = [], []
    if not isinstance(declarations, (list, tuple)) or not declarations:
        return rows, warnings
    now = float(elapsed_seconds or 0.0)
    for i, decl in enumerate(declarations):
        if len(rows) >= MINT_CAP_PER_TURN:
            warnings.append(
                f"consequence cap: {MINT_CAP_PER_TURN} per turn; "
                f"{len(declarations) - i} more dropped")
            break
        if not isinstance(decl, dict):
            warnings.append(f"consequences[{i}] is not an object; dropped")
            continue
        what = _squeeze(decl.get("what"), _WHAT_MAX)
        if not what:
            warnings.append(f"consequences[{i}] has no 'what'; dropped")
            continue
        where_raw = str(decl.get("where") or "").strip()
        res = resolve_subject(cid, scene, "place", where_raw, frame_id)
        if not res:
            warnings.append(
                f"consequences[{i}] 'where' {where_raw!r} resolves to no "
                f"room or lore place ({res.reason}); dropped — a fuse at a "
                "location the world does not contain is the 'quiet office' "
                "row")
            continue
        where_id = res.subject.id
        where_kind = res.subject.kind
        try:
            declared_due = float(decl.get("due_seconds"))
        except (TypeError, ValueError):
            warnings.append(
                f"consequences[{i}] due_seconds "
                f"{decl.get('due_seconds')!r} is not a number; dropped")
            continue
        due = min(max(declared_due, DUE_MIN_SECONDS), DUE_MAX_SECONDS)

        originator_raw = str(decl.get("originator") or "").strip()
        originator, originator_display = "", ""
        if originator_raw:
            who = resolve_subject(cid, scene, "character", originator_raw,
                                  frame_id)
            if who:
                originator = who.subject.id
            else:
                originator_display = originator_raw[:80]

        payload = {
            "frame_id": frame_id,
            "what": what,
            "where": where_id,
            "where_kind": where_kind,
            # The publicly visible surface at cause time — what phase 2's
            # carriers may pick up. Empty means the cause was not publicly
            # witnessed, and an unwitnessed event emits nothing.
            "witnessed": _squeeze(decl.get("witnessed"), _WITNESSED_MAX),
            "origin": {"room": str(player_room or ""),
                       "turn": int(turn_idx),
                       "elapsed_seconds": now},
            "originator": originator,
            **({"originator_display": originator_display}
               if originator_display else {}),
            "declared_due_seconds": declared_due,
            "base_turn": int(turn_idx),
            # Layer-1 provenance: Director-adjudicated cause, deterministic
            # firing. Phase 2's invented gossip rides the same rail with
            # ``provisional`` instead, and the field is what keeps the two
            # from ever being confused.
            "disposition": "resolved_fact",
        }
        rows.append({
            "event_id": stable_event_key(
                CONSEQUENCE_KIND, cid, frame_id, where_id, turn_id, i),
            "chat_id": cid,
            "due_at": now + due,
            "kind": CONSEQUENCE_KIND,
            "location_id": where_id,
            "payload": json.dumps(payload, ensure_ascii=False),
            "seed": f"{CONSEQUENCE_KIND}:{cid}:{turn_idx}",
            "status": "pending",
        })
    return rows, warnings


def fired_consequences_at(cid, room_id, since_seconds, until_seconds,
                          cap=2):
    """Fired fuses at one location inside a clock window, oldest first.

    The contact-time reader: the residue assembler calls this for the room
    being entered. It reads ``what`` only — the payload's origin and
    originator stay in the row for phase 2's carriers, not for narration.
    """
    from core.db import q

    out = []
    for row in q(
        "SELECT payload FROM scheduled_events WHERE chat_id=? AND "
        "status='fired' AND kind=? AND location_id=? AND due_at>? AND "
        "due_at<=? ORDER BY due_at",
        (cid, CONSEQUENCE_KIND, str(room_id), float(since_seconds),
         float(until_seconds)),
    ):
        try:
            payload = json.loads(row["payload"] or "{}")
        except Exception:
            continue
        what = str(payload.get("what") or "").strip()
        if what:
            out.append(what)
        if len(out) >= max(0, int(cap)):
            break
    return out


# ---------------------------------------------------------------------------
# Approach D floor: the obligation ledger. Real state, accumulated as it
# happens, surfaced only where the place itself is generated.
# ---------------------------------------------------------------------------

OBLIGATION_KEY = "place_obligations"

#: Stored per place; the oldest fall off. Enough that ranking at honour
#: time has something to rank, small enough that the ledger cannot become
#: a shadow event log.
OBLIGATION_STORE_CAP = 12

#: Handed to generation per place. A room reciting fourteen obligations is
#: an arrival paragraph that reads like a briefing; the rest silently
#: expire as things that turned out not to matter (design doc §4).
OBLIGATION_HONOR_CAP = 4


def record_obligations(cid, fired_rows):
    """Fold fired consequence rows at ungenerated places into the ledger.

    Called from the commit sweep with this beat's fired fuses. Recorded
    WHENEVER a fuse fires at a place — not gated by the D setting — because
    this is layer-1 truth accumulating, and settings gate surfaces, never
    truth: switching D on mid-story must find the history already there.
    Deliberately no turn-counted TTL: an unvisited place's clock is exactly
    the countdown amendment 7 warns must pause while nobody is near
    (``CLAIM_TTL_TURNS`` eating truth about subjects the player never met);
    the store cap is the only forgetting.
    """
    from core.db import transaction, wget, wset

    entries = []
    for row in fired_rows or []:
        payload = row.get("payload") if isinstance(row, dict) else None
        if isinstance(payload, str):
            try:
                payload = json.loads(payload or "{}")
            except Exception:
                payload = {}
        if not isinstance(payload, dict):
            continue
        if payload.get("where_kind") != "place":
            continue
        uid = str(payload.get("where") or "")
        what = str(payload.get("what") or "").strip()
        if not uid or not what:
            continue
        entries.append((uid, {
            "what": what,
            "event_id": str(row.get("event_id") or ""),
            "elapsed_seconds": float(row.get("due_at") or 0.0),
            "origin": payload.get("origin") or {},
            "originator": str(payload.get("originator") or ""),
            "witnessed": str(payload.get("witnessed") or ""),
            "frame_id": payload.get("frame_id"),
            "disposition": str(payload.get("disposition") or ""),
        }))
    if not entries:
        return 0
    with transaction():
        ledger = wget(cid, OBLIGATION_KEY, {}) or {}
        for uid, entry in entries:
            rows = ledger.setdefault(uid, [])
            if any(r.get("event_id") == entry["event_id"] for r in rows
                   if entry["event_id"]):
                continue  # a rerun fires the same stable id; fold, not stack
            rows.append(entry)
            del rows[:-OBLIGATION_STORE_CAP]
        wset(cid, OBLIGATION_KEY, ledger)
    return len(entries)


def owed_history(cid, entry_uid, cap=OBLIGATION_HONOR_CAP):
    """What one place owes, most recent first, capped for the honour seam.

    THE ONLY LEGITIMATE CONSUMER IS GENERATION of the place itself — the
    mapping payload, at the moment the place becomes rooms. Handing this to
    a character payload would be knowledge held without a route that
    delivered it: the accumulated history is true, and truth is not a
    channel (the Kadoman rule).
    """
    from core.db import wget

    ledger = wget(cid, OBLIGATION_KEY, {}) or {}
    rows = ledger.get(str(entry_uid)) or []
    out = []
    for row in reversed(rows[-max(0, int(cap)):]):
        if not isinstance(row, dict):
            continue
        out.append({
            "what": row.get("what") or "",
            "elapsed_seconds": row.get("elapsed_seconds"),
            **({"witnessed": row["witnessed"]} if row.get("witnessed")
               else {}),
        })
    return out


def attach_owed_history(cid, lore_hits, config=None):
    """Annotate location lore hits with what the place owes, for mapping.

    Returns copies; never mutates the input. Gated by the D setting HERE —
    this is the surface, and surfaces are what settings gate. Attached to
    location entries with an ``entry_uid``. Accrual stops by construction
    once a place is generated (``resolve_subject`` then answers ``room``,
    so new fuses land on the room id) — but old obligations stay attached
    until the ledger row is superseded; the mapping prompt scopes them to
    the generation moment.
    """
    config = config if config is not None else living_world_config(cid)
    if not living_world_allows(config, "place_obligations", "floor"):
        return [dict(h) for h in (lore_hits or [])]
    out = []
    for hit in lore_hits or []:
        hit = dict(hit)
        uid = str(hit.get("entry_uid") or "")
        if uid and str(hit.get("category") or "") == "location":
            owed = owed_history(cid, uid)
            if owed:
                hit["owed_history"] = owed
        out.append(hit)
    return out
