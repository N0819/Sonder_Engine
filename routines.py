"""Approach A of the living world: routine and residue.

``docs/DESIGN_LIVING_WORLD.md`` §1, floor only. A routine is a pure
function from the simulation clock and a room's own name-tags to expected
posture; seeded jitter keeps regularity from reading as clockwork; entropy
is what elapsed time does to fires, food and dust. The residue is the diff
between the room as last seen (``gaps.LAST_SEEN_KEY`` anchors when) and
the room as the routine says it now stands — delivered at re-entry, capped,
as present-tense facts for the Director to stage.

WHO MAY LEARN WHAT, AND BY WHAT ROUTE (enforced structurally):

  * TICKS PRODUCE STATE, NEVER PROSE, and this module never ticks at all:
    posture is recomputed from the clock at the moment of contact, so a
    hundred quiet turns cost nothing and write nothing. Nothing here calls
    a model, and nothing here WRITES — no ``wset``, no INSERT — which a
    test pins by reading this source. A residue that is never stored
    cannot be delivered to the wrong mind later.
  * The one consumer is the Director's staging payload for the room the
    party is entering THIS beat (``destination_residue``). No character
    payload receives residue: what a character knows about a room they
    were in is their own gap record's business (``gaps.interim_for``), on
    their own sightings, not the player's.
  * Facts are relative or entropic — "quieter than when last seen", "the
    hearth stands cold" — never absolute clock claims. The engine's clock
    has no day anchor (``display`` is prose the Director owns), so a fact
    like "it is midday" would assert something no ledger holds. A relative
    diff asserts only the passage the clock actually measured, which is
    why it cannot contradict the story's own sense of time.
  * Fired consequence fuses at the entered room outrank texture: they are
    layer-1 fact (see ``living_world``), the texture is plausible motion.
    Both arrive as state; the Director stages, the narrator renders — the
    changelog failure (a return reading as a diff report) is guarded by
    the cap here and the texture clause in the prompt, shipped together.
"""

from __future__ import annotations

import hashlib

#: One in-story day, for cycles and entropy thresholds. The clock is
#: elapsed seconds with no absolute anchor; a DAY here is a period, not a
#: date.
DAY_SECONDS = 86400.0

#: Below this gap a return is a round trip, not an absence; the room owes
#: no difference worth a payload's tokens.
MIN_RESIDUE_GAP_SECONDS = 1800.0

#: BACKGROUND_LIFE §5's texture-not-beats clause, as a number: at most this
#: many facts per re-entry, however much changed. The rest is simply how
#: the room now reads when looked at.
RESIDUE_CAP = 3

#: Occupancy bands, ordered. Band names are state labels, not prose.
OCCUPANCY_BANDS = ("shut", "quiet", "steady", "busy")

#: Eight watches per day-cycle: coarse enough that a band holds for hours,
#: fine enough that a long absence usually crosses one.
_WATCHES = 8

#: The default public-room curve over the eight watches: two low watches,
#: a swell, a peak, an ebb. Which watch is "first" is place-seeded jitter,
#: so no two taverns keep the same hours and none keeps them exactly.
_CURVE = (0, 0, 1, 2, 3, 3, 2, 1)

#: Affordances (from ``place_purpose.assumed_affords`` over the room name)
#: whose rooms have a social routine worth an occupancy claim. A store
#: room has no crowd to thin.
_SOCIAL_AFFORDANCES = frozenset({"food", "drink", "rest"})


def _roll(seed, step, salt):
    """A stable pseudo-random integer for (seed, step, salt).

    The ``weather._roll`` discipline: hashing rather than seeding an RNG,
    because the value must be identical in a fresh process, after a
    restart, and on a replayed turn.
    """
    blob = "%s|%s|%s" % (seed, step, salt)
    return int(hashlib.sha256(blob.encode("utf-8")).hexdigest()[:8], 16)


def routine_band(place_key, elapsed_seconds):
    """Occupancy band index (0–3) for one place at one clock reading. Pure.

    Phase-jittered per place, amplitude-jittered per day: the same place at
    the same clock always answers the same, two places never quite agree,
    and yesterday's peak is not exactly today's — a rhythm, not a schedule.
    """
    try:
        elapsed = max(0.0, float(elapsed_seconds))
    except (TypeError, ValueError):
        elapsed = 0.0
    key = str(place_key or "")
    watch = int(elapsed % DAY_SECONDS // (DAY_SECONDS / _WATCHES))
    phase = _roll(key, 0, "phase") % _WATCHES
    band = _CURVE[(watch + phase) % _WATCHES]
    day = int(elapsed // DAY_SECONDS)
    nudge = _roll(key, day, "nudge") % 4
    if nudge == 0 and band > 0:
        band -= 1
    elif nudge == 3 and band < len(OCCUPANCY_BANDS) - 1:
        band += 1
    return band


def occupancy_fact(room_name, place_key, then_seconds, now_seconds):
    """One relative occupancy fact, or None when the band did not move.

    Relative on purpose — "quieter than when the party last saw it" — see
    the module header for why an absolute clock claim is not this module's
    to make. Only rooms whose own name affords a social routine get one.
    """
    from place_purpose import assumed_affords

    if not _SOCIAL_AFFORDANCES & set(assumed_affords(room_name)):
        return None
    before = routine_band(place_key, then_seconds)
    after = routine_band(place_key, now_seconds)
    if before == after:
        return None
    word = "busier" if after > before else "quieter"
    return (f"The room is {word} than when the party last saw it — "
            f"{OCCUPANCY_BANDS[after]} now.")


def entropy_facts(room_name, gap_seconds):
    """What elapsed time alone did to the room. Pure; tag-gated.

    Each fact is asserted only when the room's own name affords the thing
    it decays — a hearth claim in a room that never afforded warmth would
    be minting a fixture in a reader, the 'quiet office' defect one door
    down. The no-affordance fallback (dust) needs the gap to be long and
    the room unsocial, because a busy room does not gather a week of dust.
    """
    from place_purpose import assumed_affords

    try:
        gap = max(0.0, float(gap_seconds))
    except (TypeError, ValueError):
        return []
    affords = set(assumed_affords(room_name))
    facts = []
    if "warmth" in affords and gap > 4 * 3600.0:
        facts.append("Any fire has long burned down; the hearth stands "
                     "cold.")
    if affords & {"food", "drink"} and gap > DAY_SECONDS:
        facts.append("Whatever food or drink stood out has been cleared "
                     "away or gone stale.")
    if not (affords & _SOCIAL_AFFORDANCES) and gap > 7 * DAY_SECONDS:
        facts.append("Dust and disuse show plainly on every surface.")
    return facts


def residue_for(cid, scene, room_id, frame_id=None, now_seconds=None):
    """The capped diff for one room at re-entry, or None.

    Reads the last-seen ledger for WHEN the room was last before the
    player's eyes, the fired-fuse ledger for what factually landed there
    since (ranked first), and the routine/entropy functions for plausible
    motion. A room never seen returns None — a first arrival owes nothing
    to a diff, and unvisited PLACES are approach D's ledger, not this one.
    """
    from db import wget, wget_for_frame
    from gaps import LAST_SEEN_KEY
    from living_world import fired_consequences_at

    if not room_id:
        return None
    ledger = (wget_for_frame(cid, LAST_SEEN_KEY, frame_id, {})
              if frame_id is not None else wget(cid, LAST_SEEN_KEY, {})) or {}
    rec = ledger.get(str(room_id)) or {}
    try:
        then_seconds = float(rec.get("elapsed_seconds"))
    except (TypeError, ValueError):
        return None
    try:
        now = float(now_seconds)
    except (TypeError, ValueError):
        return None
    gap = now - then_seconds
    if gap < MIN_RESIDUE_GAP_SECONDS:
        return None

    room = ((scene or {}).get("rooms") or {}).get(str(room_id))
    room_name = (room or {}).get("name") if isinstance(room, dict) else None
    room_name = room_name or str(room_id)

    facts = list(fired_consequences_at(cid, str(room_id), then_seconds, now))
    facts.extend(entropy_facts(room_name, gap))
    shift = occupancy_fact(room_name, f"room:{cid}:{room_id}",
                           then_seconds, now)
    if shift:
        facts.append(shift)
    if not facts:
        return None
    return {"room": str(room_id),
            "since_turn": rec.get("turn"),
            "facts": facts[:RESIDUE_CAP]}
