"""Scent on the room graph: a ledger with memory, not a field with a path.

WHY THIS IS NOT THE SOUND FIELD WITH DIFFERENT CONSTANTS. Three differences
decide the whole shape, and each one was checked against how the prior art
actually does it (`docs/CREDITS.md`, `docs/guides/RESEARCH.md`).

  * **Sound's path is the shortest path; scent's path is the air's.** Sound
    diffracts round a corner and arrives in its own beat. A gas goes where
    the air goes, and it goes SLOWLY. So there is no Dijkstra here and no
    cells: scent bleeds one room per beat along declared edges, which is
    Dwarf Fortress's miasma rule -- orthogonal steps only, through bars and
    grates and open doors, stopped by shut ones.
  * **Scent has memory and sound has none.** A sound exists in its beat; a
    smell accumulates while a body stands there and LINGERS after it leaves.
    That is the whole mechanic: a hunter follows where you WERE. Miasma
    keeps spreading after its source is gone, and this does too.
  * **Scent is a gradient, not a bearing.** You cannot localise a smell the
    way you localise a clang. A body is told how strong it is and never
    which way; a creature reads the difference across the rooms it can
    reach and walks uphill, which is Brogue's Dijkstra-map read.

WHAT A ROOM HOLDS is one number per SOURCE KIND, so a hunter tracking breath
is not drawn by a dead thing three rooms off. The kinds are the story's own
words, not a table here.

THE LEDGER IS THE SCENE'S. `scene["scents"] = {room: {kind: strength}}`,
rewritten every beat by `advance_scents`. Strength is on `SCENT_SCALE`, a
plain 0..1 with no decibels in it: a smell is not a wave and borrowing the
sound model's arithmetic would be the same mistake in the other direction.
"""

from __future__ import annotations

from typing import Optional

from world.spatial_barriers import (SCENT_PASS, effective_adjacent,
                                    normalize_barrier)

#: Where the ledger lives on the scene.
SCENTS_KEY = "scents"

#: The strongest a room can smell of one thing. A plain ceiling, so a body
#: standing somewhere for a hundred beats does not make a number that swamps
#: every comparison downstream.
SCENT_MAX = 1.0

#: Under this a room does not smell of the thing at all, and the entry is
#: dropped rather than kept at a millionth. It is what makes a trail END,
#: and it is why the ledger stays small.
SCENT_FLOOR = 0.02

#: What one beat of a source standing in a room adds, by its own strength
#: word. THE LADDER IS SCENT'S OWN and is deliberately not `SOUND_LEVELS`:
#: exhaled breath is faint-and-constant, a dead thing is strong-and-lingering,
#: and neither is measured against a voice. Dwarf Fortress keeps `odor level`
#: on the creature for the same reason.
SCENT_STRENGTH = {"trace": 0.05, "faint": 0.12, "clear": 0.3, "strong": 0.6,
                  "overpowering": 1.0}
SCENT_LEVELS = tuple(SCENT_STRENGTH)

#: What a room keeps from one beat to the next, before anything is added.
#: A sealed place holds its air; an open one loses it. `exposure` is the word
#: the engine already has for how much sky reaches a room, so it is the word
#: that decides ventilation too.
#:
#: Chosen so a trail in a sealed sub-level is followable for roughly a dozen
#: beats and one in the open for two or three -- the roguelike scent map's
#: "one number encodes both distance and staleness", with the decay rate
#: choosing how much staleness is forgiven.
SCENT_KEEP = {"enclosed": 0.86, "sheltered": 0.7, "open": 0.45}

#: A doorway whose barrier the table does not name -- `unknown` and
#: `separated`, and anything that normalizes to `wall`. Nothing crosses. The
#: fail-open direction is wrong for a ledger that ACCUMULATES: guessing a way
#: through ventilates a building nobody has walked, and a trail that leaked
#: everywhere would be worse than no trail. An edge with no barrier written
#: on it is not this case -- the schema says omitting one means an open way
#: through, and `normalize_barrier` answers `open` for it.
SCENT_PASS_NONE = 0.0


def normalize_scent_level(value) -> Optional[str]:
    word = str(value or "").strip().casefold()
    return word if word in SCENT_STRENGTH else None


def normalize_scents(stored) -> dict:
    """The ledger as read: `{room: {kind: strength}}`, clamped and floored.

    Anything unreadable is absent rather than guessed, and a strength at or
    under `SCENT_FLOOR` is dropped -- a trail that has faded is gone, not
    kept as a number nobody can act on.
    """
    if not isinstance(stored, dict):
        return {}
    out = {}
    for room, kinds in stored.items():
        if not isinstance(kinds, dict):
            continue
        held = {}
        for kind, strength in kinds.items():
            kind = " ".join(str(kind or "").split())[:60]
            if not kind:
                continue
            try:
                value = float(strength)
            except (TypeError, ValueError):
                continue
            value = min(SCENT_MAX, value)
            if value > SCENT_FLOOR:
                held[kind] = value
        if held:
            out[str(room)] = held
    return out


def _keep(scene, room_id) -> float:
    from world import weather as _weather

    return SCENT_KEEP.get(_weather.room_exposure(scene, room_id),
                          SCENT_KEEP["enclosed"])


def scent_edges(scene, room_id) -> dict:
    """`{neighbour: what crosses in one beat}` for one room's declared ways
    out. Undirected, like every other reading of the graph, and the LARGER
    pass wins where two sides disagree -- air finds the gap, and the side
    whose author was more careful should not seal it."""
    out = {}
    for edge in effective_adjacent(scene, room_id):
        if not isinstance(edge, dict) or not edge.get("to"):
            continue
        other = str(edge["to"])
        if other == str(room_id):
            continue
        passes = SCENT_PASS.get(normalize_barrier(edge.get("barrier")),
                                SCENT_PASS_NONE)
        if passes > out.get(other, 0.0):
            out[other] = passes
    return out


def advance_scents(scene: dict, deposits=None) -> dict:
    """One beat of the ledger: DECAY, then BLEED, then DEPOSIT.

    In that order deliberately. A body standing still must not have its own
    fresh breath decayed before anything smells it, and what bleeds next
    door is what was in the air at the START of the beat rather than what
    arrived during it -- otherwise a smell crosses a whole building in one
    beat, which is the failure that makes a diffusion look like a flood.

    `deposits` is `[{room, kind, level}]` -- what stood somewhere and gave
    off something this beat. Returns the new ledger and does not write it;
    the caller owns the scene.
    """
    rooms = (scene or {}).get("rooms") or {}
    if not isinstance(rooms, dict) or not rooms:
        return {}
    held = normalize_scents((scene or {}).get(SCENTS_KEY))

    faded = {}
    for room, kinds in held.items():
        if room not in rooms:
            continue                    # a room the scene no longer holds
        keep = _keep(scene, room)
        for kind, strength in kinds.items():
            value = strength * keep
            if value > SCENT_FLOOR:
                faded.setdefault(room, {})[kind] = value

    moved = {room: dict(kinds) for room, kinds in faded.items()}
    for room, kinds in faded.items():
        for other, passes in scent_edges(scene, room).items():
            if other not in rooms:
                continue
            for kind, strength in kinds.items():
                crossed = strength * passes
                if crossed <= SCENT_FLOOR:
                    continue
                there = moved.setdefault(other, {})
                there[kind] = min(SCENT_MAX,
                                  max(there.get(kind, 0.0), crossed))

    for deposit in deposits or ():
        if not isinstance(deposit, dict):
            continue
        room = str(deposit.get("room") or "")
        kind = " ".join(str(deposit.get("kind") or "").split())[:60]
        level = normalize_scent_level(deposit.get("level"))
        if not room or room not in rooms or not kind or not level:
            continue
        there = moved.setdefault(room, {})
        there[kind] = min(SCENT_MAX,
                          there.get(kind, 0.0) + SCENT_STRENGTH[level])
    return normalize_scents(moved)


def scent_at(scene: dict, room_id) -> dict:
    """`{kind: strength}` in one room. What a nose in that room meets."""
    return dict(normalize_scents(
        (scene or {}).get(SCENTS_KEY)).get(str(room_id)) or {})


def scent_word(strength: float) -> Optional[str]:
    """The strongest `SCENT_LEVELS` word at or under this strength, or None
    below the floor. What a body is told: a WORD and never a number, and
    never a direction -- a nose does not give you a bearing."""
    best = None
    for word, at in SCENT_STRENGTH.items():
        if strength >= at and (best is None or at >= SCENT_STRENGTH[best]):
            best = word
    return best if strength > SCENT_FLOOR else None


def scent_gradient(scene: dict, room_id, kind) -> dict:
    """`{room: strength}` for this room and every room reachable from it,
    for one kind -- what a hunter reads before it decides where to step.

    THE ENGINE'S READ, NOT A MIND'S. `scent_at` is what a body is told and
    carries no direction; this names rooms, because it answers where a thing
    WALKS, and nothing here is delivered to anybody.
    """
    ledger = normalize_scents((scene or {}).get(SCENTS_KEY))
    kind = " ".join(str(kind or "").split())[:60]
    out = {}
    here = (ledger.get(str(room_id)) or {}).get(kind)
    if here:
        out[str(room_id)] = here
    for other in scent_edges(scene, room_id):
        strength = (ledger.get(other) or {}).get(kind)
        if strength:
            out[other] = strength
    return out
