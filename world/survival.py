# survival.py
"""Bodily condition: breath, stamina, nourishment, injury.

OFF BY DEFAULT, and off means absent -- not zeroed, not defaulted, absent. When
the setting is off nothing is tracked, nothing is ticked, no vitals reach any
prompt, and the scene blob carries no `vitals` key at all. A story that does not
want a hunger clock must not pay for one in tokens, in state, or in the
Director's attention, and inventing bodily needs for fiction that never asked is
how a simulation engine becomes tedious.

When it is on, four numbers per body, each 0..1:

    air           1 breathing freely   -> 0 suffocating
    stamina       1 fresh              -> 0 spent
    nourishment   1 fed                -> 0 starving
    injury        0 unhurt             -> 1 critical      (inverted, on purpose:
                                                           absent means unhurt)

They are live physical state, so they live in the scene blob beside positions,
contacts and scales, and they move with simulation time rather than with turns
-- a beat that covers three seconds and a beat that covers three hours must not
cost the same.

Air is the one with teeth, and it exists because of containment: sealing someone
in an opaque container was previously survivable indefinitely. Air only depletes
for a body in a sealed enclosure, and it depletes fast.
"""

from __future__ import annotations

from core.db import wget, wset

# --- the setting ----------------------------------------------------------
#
# PER STORY, not per install, and stored in the world KV beside the style guide
# it sits with in the interface. One chat can be a survival ordeal and the next
# a conversation in a tavern; a single global switch would make the menu it
# lives in a lie.

SURVIVAL_KEY = "survival_enabled"
# Whether the margin tracker shows anyone but the player. Off by default: the
# player's own body is the one they act with, and a column of NPC meters beside
# the prose is a dashboard rather than a story. The NPC numbers are still
# tracked and still reach the Director -- they are simply read in the Cast
# panel, on purpose, rather than hovering over the page.
SURVIVAL_NPC_KEY = "survival_track_npcs"


def survival_enabled(chat_id) -> bool:
    return bool(wget(chat_id, SURVIVAL_KEY, False))


def set_survival_enabled(chat_id, enabled: bool) -> bool:
    wset(chat_id, SURVIVAL_KEY, bool(enabled))
    return bool(enabled)


def survival_shows_npcs(chat_id) -> bool:
    return bool(wget(chat_id, SURVIVAL_NPC_KEY, False))


def set_survival_shows_npcs(chat_id, enabled: bool) -> bool:
    wset(chat_id, SURVIVAL_NPC_KEY, bool(enabled))
    return bool(enabled)


# --- the vitals -----------------------------------------------------------

# name -> (baseline per HOUR of simulation time, starts_at)
# Negative drains. Injury does not drain; it heals, slowly, and only rest or
# treatment in the fiction should move it much.
VITALS = {
    "air": 1.0,
    "stamina": 1.0,
    "nourishment": 1.0,
    "injury": 0.0,
}

_PER_HOUR = {
    # ~33 hours awake before stamina is spent, halved again by exertion the
    # Director declares. Sleep restores it far faster than waking spends it,
    # which is why a night's rest resets a body and an hour's nap does not.
    "stamina": -0.03,
    # ~2 days to starving. Deliberately slower than stamina: hunger should
    # shape a long journey, not a conversation.
    "nourishment": -0.02,
    # Untreated injury closes on its own, barely.
    "injury": -0.01,
}

# Air is not a per-hour drain, it is a countdown, and only while sealed in.
_AIR_SECONDS = 900.0        # a sealed container is unbreathable in ~15 minutes
_SLEEP_STAMINA_PER_HOUR = 0.14
_REST_STAMINA_PER_HOUR = 0.05

# Where each vital crosses into something the fiction should feel. Ordered
# worst-first; the first threshold a value meets wins.
_LABELS = {
    "air": ((0.0, "suffocating"), (0.15, "starved of air"),
            (0.4, "short of breath"), (0.75, "breathing hard")),
    "stamina": ((0.0, "spent"), (0.15, "exhausted"),
                (0.4, "tiring badly"), (0.7, "tired")),
    "nourishment": ((0.0, "starving"), (0.15, "faint with hunger"),
                    (0.4, "very hungry"), (0.7, "hungry")),
}
_INJURY_LABELS = ((0.85, "critically injured"), (0.6, "badly hurt"),
                  (0.3, "hurt"), (0.1, "bruised"))


def _clamp(value, low=0.0, high=1.0):
    try:
        return max(low, min(float(value), high))
    except (TypeError, ValueError):
        return None


def default_vitals() -> dict:
    return dict(VITALS)


def _stored_vitals(record) -> dict:
    """A body's stored vitals as NUMBERS, defaults where they are not.

    The table is the same JSON blob a checkpoint restore, an archive import,
    an extension and the GM's own scene editor all write, so a value read back
    out of it is untrusted exactly as a value read out of a Director diff is.
    Both readers used to trust it, and a stored `"low"` then reached `-` in
    `tick_vitals` and `round()` in `apply_vitals_diff`: a TypeError out of
    `merge_scene_with_diff`, which fails the whole TURN rather than the vital.
    An unreadable value falls to that vital's default, which is the only
    numeric answer available, and it never takes its healthy neighbours with
    it.
    """
    out = default_vitals()
    for key, value in (record or {}).items():
        if key not in VITALS:
            continue
        clamped = _clamp(value)
        if clamped is not None:
            out[key] = clamped
    return out


def seed_vitals(scene: dict, names) -> dict:
    """Give every named body a baseline record, creating the table if needed.

    Turning the feature ON has to DO something. Absence is the off switch --
    nothing ticks and nothing reaches a prompt without a table -- which meant
    enabling it was inert until the Director happened to write a vitals patch,
    and it had no reason to: nobody was hungry yet. The switch now seeds the
    bodies it knows about, so the first beat after enabling already has
    something to move and the tracker has something to show.

    Existing records are left exactly as they are, so re-enabling after a pause
    resumes rather than restoring everyone to perfect health.
    """
    table = scene.get("vitals")
    if not isinstance(table, dict):
        table = {}
    for name in names or []:
        label = str(name or "").strip()
        if label and not any(str(k).strip().casefold() == label.casefold()
                             for k in table):
            table[label] = default_vitals()
    scene["vitals"] = table
    return scene


def vitals_of(scene: dict, name: str) -> dict:
    """`name`'s vitals, or defaults. Empty when survival is off."""
    table = (scene or {}).get("vitals")
    if not isinstance(table, dict):
        return {}
    target = str(name or "").strip().casefold()
    for key, record in table.items():
        if str(key).strip().casefold() == target and isinstance(record, dict):
            return _stored_vitals(record)
    return {}


def vital_label(vital: str, value) -> str:
    """A word for where this number sits, or "" when it is unremarkable."""
    value = _clamp(value)
    if value is None:
        return ""
    if vital == "injury":
        for bound, label in _INJURY_LABELS:
            if value >= bound:
                return label
        return ""
    for bound, label in _LABELS.get(vital, ()):
        if value <= bound:
            return label
    return ""


def is_sealed_in(scene: dict, name: str) -> bool:
    """Is this body inside a closed enclosure with no way out.

    The direct consequence of containers-as-places: an interior whose doorway
    is shut has whatever air was in it and no more. A transparent or barred
    enclosure is still sealed to AIR -- you can be seen through glass and
    suffocate behind it, which is exactly the horror of the thing.
    """
    from world.spatial import normalize_barrier, room_of

    room_id = room_of(scene, name)
    if not room_id:
        return False
    room = ((scene or {}).get("rooms") or {}).get(room_id)
    if not isinstance(room, dict) or not room.get("parent_entity"):
        return False

    # Any adjacency a body could pass through means it is not sealed.
    for edge in room.get("adjacent") or []:
        if isinstance(edge, dict) and \
                normalize_barrier(edge.get("barrier")) in ("open", "open_door"):
            return False
    return True


def tick_vitals(scene: dict, elapsed_seconds, *, asleep=(), exerting=()) -> dict:
    """Advance every tracked body's vitals by the time this beat took.

    A no-op unless the scene already carries a vitals table, which is what
    keeps this free for stories with the setting off: nothing creates the table
    but an explicit write, so nothing here can start a hunger clock by itself.
    """
    table = (scene or {}).get("vitals")
    if not isinstance(table, dict) or not table:
        return scene

    from world.comfort import rest_affording

    try:
        seconds = max(0.0, float(elapsed_seconds or 0))
    except (TypeError, ValueError):
        seconds = 0.0
    hours = seconds / 3600.0

    resting = {str(n).strip().casefold() for n in (asleep or [])}
    working = {str(n).strip().casefold() for n in (exerting or [])}

    for name in list(table):
        record = table.get(name)
        if not isinstance(record, dict):
            table.pop(name, None)
            continue
        key = str(name).strip().casefold()
        current = _stored_vitals(record)

        # Air: a countdown while sealed in, and a fast recovery once out.
        if is_sealed_in(scene, name):
            current["air"] = _clamp(current["air"] - seconds / _AIR_SECONDS)
        else:
            current["air"] = _clamp(current["air"] + seconds / 60.0)

        if key in resting:
            current["stamina"] = _clamp(
                current["stamina"] + hours * _SLEEP_STAMINA_PER_HOUR)
        elif key not in working and rest_affording(scene, name):
            # Lying on a rest-affording surface recovers, derived -- like air
            # -- from what the scene itself asserts, so rest works without the
            # Director remembering to say the word. Declared exertion wins:
            # you are not resting if the beat says you are straining.
            current["stamina"] = _clamp(
                current["stamina"] + hours * _REST_STAMINA_PER_HOUR)
        else:
            drain = _PER_HOUR["stamina"] * (2.0 if key in working else 1.0)
            current["stamina"] = _clamp(current["stamina"] + hours * drain)

        current["nourishment"] = _clamp(
            current["nourishment"] + hours * _PER_HOUR["nourishment"])
        current["injury"] = _clamp(
            current["injury"] + hours * _PER_HOUR["injury"])

        # Every value is a number by construction now, so no key is ever
        # dropped. A dropped key was not a smaller record: `vitals_of` merges
        # the defaults back, so an omitted `air` read as a full breath.
        table[name] = {k: round(v, 4) for k, v in current.items()}

    return scene


def apply_vitals_diff(scene: dict, incoming) -> dict:
    """Apply a Director-declared {name: {vital: value}} patch.

    Only ever called when survival is on, which is what makes the table's
    existence the switch: no write, no table, nothing to tick.
    """
    if not isinstance(incoming, dict) or not incoming:
        return scene
    table = scene.setdefault("vitals", {})
    if not isinstance(table, dict):
        table = scene["vitals"] = {}

    for name, patch in incoming.items():
        label = str(name or "").strip()
        if not label:
            continue
        if patch is None:
            table.pop(label, None)
            continue
        if not isinstance(patch, dict):
            continue
        current = _stored_vitals(table.get(label))
        for vital, value in patch.items():
            if vital not in VITALS:
                continue
            clamped = _clamp(value)
            if clamped is not None:
                current[vital] = clamped
        table[label] = {k: round(v, 4) for k, v in current.items()}
    return scene


def vitals_facts(scene: dict, name: str) -> list:
    """Plain statements about a body's condition, for its own frame.

    Only what is actually remarkable: a fed, rested, unhurt body generates
    nothing, so the common case costs no tokens even with survival on.
    """
    vitals = vitals_of(scene, name)
    if not vitals:
        return []

    facts = []
    for vital in ("air", "stamina", "nourishment", "injury"):
        label = vital_label(vital, vitals.get(vital))
        if not label:
            continue
        if vital == "air":
            facts.append(f"You are {label}." if vitals["air"] > 0
                         else "You cannot breathe.")
        elif vital == "injury":
            facts.append(f"You are {label}.")
        else:
            facts.append(f"You are {label}.")
    return facts
