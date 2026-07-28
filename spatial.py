# spatial.py
"""Spatial reasoning with entity-aware scene merging and containment validation."""

import copy
import re
from typing import Optional

from schemas import is_derived_entity_name
from spatial_orientation import (
    _LEFT_SECTORS,
    _REL_SECTORS,
    _RIGHT_SECTORS,
    lateral_of,
    normalize_bearing,
    normalize_scene_bearings,
    opposite_bearing,
    relative_bearing,
    travel_bearing,
)

_BARRIER_ALIASES = {
    "": "wall",
    "none": "open",
    "no_barrier": "open",
    "no barrier": "open",
    "open_space": "open",
    "open space": "open",
    "archway": "open",
    "threshold": "open",
    "doorway": "open",
    "open_doorway": "open",
    "open doorway": "open",
    "open_doorframe": "open",
    "open doorframe": "open",
    "counter": "open",
    "open_counter": "open",
    "open counter": "open",
    "door": "open_door",
    "open door": "open_door",
    "shoji_open": "open_door",
    "shoji open": "open_door",
    "shoji_door": "closed_door",
    "shoji door": "closed_door",
    "closed door": "closed_door",
    "locked_door": "closed_door",
    "locked door": "closed_door",
    "locked": "closed_door",
    "padlocked_door": "closed_door",
    "padlocked door": "closed_door",
    "padlocked": "closed_door",
    "sealed_door": "wall",
    "sealed door": "wall",
    "sealed": "wall",
    "bolted": "wall",
    "bolted_door": "wall",
    "bolted door": "wall",
    "solid_wall": "wall",
    "solid wall": "wall",
    # See-through but not passable. Genuinely missing until now: every glassy
    # thing had to degrade to `wall` (opaque, the normalizer's fallback for
    # anything unrecognized) or be lied about as `open`. A room with a window
    # onto the street, an observation port, a sealed glass container -- none of
    # them could be expressed.
    "window": "window",
    "glass": "window",
    "glass_door": "window",
    "glass door": "window",
    "glass_wall": "window",
    "glass wall": "window",
    "pane": "window",
    "windowpane": "window",
    "porthole": "window",
    "viewport": "window",
    "view_port": "window",
    "observation_window": "window",
    "one_way_mirror": "window",
    "transparent": "window",
    "sealed_glass": "window",
    # See-through AND sound-through: a cage, a grille, a barred door. Distinct
    # from glass, which stops sound as well as bodies.
    "bars": "bars",
    "barred": "bars",
    "barred_door": "bars",
    "barred door": "bars",
    "cage": "bars",
    "cage_door": "bars",
    "grate": "bars",
    "grating": "bars",
    "grille": "bars",
    "grill": "bars",
    "mesh": "bars",
    "lattice": "bars",
    "portcullis": "bars",
    "railing": "bars",
    # Passable but opaque -- the inverse of `window`, and just as unauthorable
    # before now: any of these had to be lied about as `open_door` (which sees
    # straight through) or degrade to `wall` (which nothing passes).
    "membrane": "membrane",
    "curtain": "membrane",
    "curtained": "membrane",
    "curtained_doorway": "membrane",
    "curtained doorway": "membrane",
    "drape": "membrane",
    "drapes": "membrane",
    "flap": "membrane",
    "tent_flap": "membrane",
    "tent flap": "membrane",
    "beads": "membrane",
    "bead_curtain": "membrane",
    "bead curtain": "membrane",
    "veil": "membrane",
    "opaque_opening": "membrane",
}

_VALID_BARRIERS = {
    "open",
    "open_door",
    "closed_door",
    # Sight passes, bodies do not. `window` also stops sound; `bars` does not.
    "window",
    "bars",
    # Bodies pass, sight does not -- the exact inverse of `window`, and the
    # rung this ladder was missing. A curtained doorway, a bead screen, a tent
    # flap, a gasketed hatch, the soft wall of an enclosure you climb into:
    # every one of them is walked through and none of them is seen through.
    # Without it, the only way to author a doorway a body can use was
    # `open_door`, which also hands everyone outside a clear line of sight in
    # -- so entering such a space made its occupant MORE exposed than standing
    # in the open, which is precisely backwards.
    "membrane",
    "wall",
    "separated",
    "unknown",
}

# The three questions a barrier answers, kept apart because they genuinely
# differ. Conflating them is what left the engine with no way to say "you can
# see it but you cannot reach it" -- or, in `membrane`'s case, the reverse.
_SIGHT_BARRIERS = {"open", "open_door", "window", "bars"}

# Which barriers carry scent at all. Scent passes freely through open air and
# doorways; bars and grilles let it through almost as well. A membrane (a
# curtain, a tent flap, a body's soft wall) strongly attenuates it -- the
# material is thin enough for some diffusion but not free passage. Glass
# (window) stops air, and with it scent, entirely: a sealed container's
# contents are not smelled from outside. A closed door muffles scent
# significantly but does not fully stop it (gaps, undercuts). A wall blocks
# completely.
#
# The graded answer is `scent_level` (none | muffled | full), mirroring
# `sight_level` (none | shapes | full) and `hear_level` (none | fragment | full).
_SCENT_BARRIERS = {"open", "open_door", "bars", "membrane", "closed_door"}

def scent_level(rel: dict) -> str:
    """How much scent from a source reaches the perceiver: none | muffled | full.

    Barriers gate scent the same way they gate sight and sound. Containment
    concealment (a body sealed inside another) blocks scent as completely as
    it blocks sight: the enclosing body's soft wall is a membrane, and a
    membrane between the perceiver and the source means scent is muffled at
    best -- not leaked through unattenuated.

    Same-room scent is full unless containment conceals the source from the
    perceiver, in which case the membrane rule applies (muffled). This is the
    exact bug this function exists to close: without it, a character sealed
    inside another's body had their scent arriving at the enclosing character
    at full strength, as though the barrier that hid them from sight did
    nothing to what they smelled like.
    """
    if rel.get("concealed"):
        return "muffled"
    if rel.get("same_room"):
        return "full"
    barrier = normalize_barrier(rel.get("barrier"))
    if barrier in ("open", "open_door", "bars"):
        return "full"
    if barrier in ("membrane", "closed_door"):
        return "muffled"
    # window, wall, separated, unknown -- glass stops air; wall stops
    # everything; unknown is safe-closed.
    return "none"

def normalize_barrier(value: str | None) -> str:
    """Normalize model-generated barrier names into engine vocabulary."""
    barrier = str(value or "").strip().casefold()
    barrier = _BARRIER_ALIASES.get(barrier, barrier)

    if barrier not in _VALID_BARRIERS:
        return "wall"

    return barrier

def normalize_scene_barriers(scene: dict) -> dict:
    """Normalize every adjacency barrier in a scene in place."""
    if not isinstance(scene, dict):
        return scene

    for room in (scene.get("rooms") or {}).values():
        if not isinstance(room, dict):
            continue

        adjacency = room.get("adjacent")
        if not isinstance(adjacency, list):
            room["adjacent"] = []
            continue

        for edge in adjacency:
            if not isinstance(edge, dict):
                continue
            edge["barrier"] = normalize_barrier(
                edge.get("barrier")
            )

    return scene

def room_of(scene: dict, name: str) -> Optional[str]:
    positions = scene.get("positions") or {}
    if name in positions:
        return positions[name]
    lname = (name or "").lower().strip()
    for k, v in positions.items():
        if k.lower().strip() == lname:
            return v
    norm = re.sub(r"[^a-z0-9]", "", lname)
    if norm:
        for k, v in positions.items():
            if re.sub(r"[^a-z0-9]", "", k.lower().strip()) == norm:
                return v
    return None

# ---------------------------------------------------------------------------
# LIGHT -- the other half of sight.
#
# Sight was decided entirely by barriers: whether something stood between two
# rooms, and whether you could see through it. Whether there was any light to
# see BY did not exist. A pitch-black cellar and a sunlit hall were identical
# to the engine, which for a system whose whole purpose is to stop a mind
# knowing what it did not perceive is the largest hole in that promise --
# darkness is the most ordinary perception gate there is.
#
# Absent means lit, so every existing scene behaves exactly as before. This is
# the same fail-open the awareness gate and scale use.
LIGHT_LEVELS = ("dark", "dim", "lit", "bright")
_LIGHT_ALIASES = {
    "": "lit", "none": "dark", "pitch_dark": "dark", "pitch black": "dark",
    "pitch_black": "dark", "black": "dark", "unlit": "dark", "blackout": "dark",
    "lightless": "dark", "gloom": "dim", "dusk": "dim", "twilight": "dim",
    "shadowed": "dim", "shadowy": "dim", "murky": "dim", "faint": "dim",
    "candlelit": "dim", "moonlit": "dim", "half_light": "dim", "low": "dim",
    "normal": "lit", "daylight": "lit", "well_lit": "lit", "well lit": "lit",
    "bright": "bright", "glaring": "bright", "blinding": "bright",
    "floodlit": "bright", "sunlit": "lit", "harsh": "bright",
}


def normalize_light(value) -> str:
    level = str(value or "").strip().casefold().replace(" ", "_")
    level = _LIGHT_ALIASES.get(level, level)
    return level if level in LIGHT_LEVELS else "lit"


def room_light(scene: dict, room_id: str) -> str:
    """The light a room has of its own, before anything spills into it."""
    room = ((scene or {}).get("rooms") or {}).get(room_id)
    if not isinstance(room, dict):
        return "lit"
    return normalize_light(room.get("light"))


_LIGHT_ORDER = {"dark": 0, "dim": 1, "lit": 2, "bright": 3}


def _brighter(a, b):
    return a if _LIGHT_ORDER.get(a, 2) >= _LIGHT_ORDER.get(b, 2) else b


def source_light(scene: dict, room_id: str, *, filling_only=False) -> str:
    """The brightest ACTIVE light source in this room.

    A room's own `light` is what the place provides -- a window, a fixture, the
    sun. This is what someone brought with them: a torch, a lantern, a
    phone-screen, a burning brand. Without it, a character standing in a
    lightless cellar holding a lit lamp still saw nothing, which is the obvious
    way for a room-level model to be wrong.

    A carried source travels for free: an entity being carried already has its
    holder's position derived onto it (derive_contained_positions), so the lamp
    is wherever its bearer is without anything here needing to know who is
    holding what.

    Nothing here is specific to carrying. Any entity with `light_source` lights
    the room it is in, so every way a story makes light works the same way and
    none of them needed their own case: a campfire built this beat, a brazier,
    a hearth, a lamp switched on, a glowing rune, a burning wreck. Building one
    is creating an entity with `light_source` and a position -- which is what
    creating a campfire already was.

    Declared as `light_source` on the entity -- the level it EMITS -- and
    switched off with state.lit false, so a doused torch stops lighting the
    room without ceasing to be a torch.

    `filling_only` counts just the sources that light a whole room. A hand
    torch does not: it makes a pool of light around whoever holds it and leaves
    the rest of the room dark, which is `light_at`'s business, not this one's.
    """
    entities = (scene or {}).get("entities") or {}
    if not isinstance(entities, dict) or not room_id:
        return "dark"
    positions = (scene or {}).get("positions") or {}

    best = "dark"
    for eid, entity in entities.items():
        if not isinstance(entity, dict) or not entity.get("light_source"):
            continue
        state = entity.get("state") if isinstance(entity.get("state"), dict) else {}
        lit = state.get("lit", True)
        if lit in (False, 0, "off", "false", "no", "doused", "out"):
            continue
        where = _ci_get(positions, eid)
        if where is None:
            where = _ci_get(positions, str(entity.get("name") or ""))
        if where != room_id:
            continue
        if filling_only and _light_radius(entity) != "room":
            continue
        best = _brighter(best, normalize_light(entity.get("light_source")))
    return best


# How far a source throws. A hand light makes a pool; a hearth or a ceiling
# fixture fills the space. Portable things default to a pool, because that is
# what carrying a light is actually like -- and the difference is the whole
# reason a torch in a cellar is tense rather than a solved problem.
def _light_radius(entity):
    declared = str((entity or {}).get("light_radius") or "").strip().casefold()
    if declared in ("room", "spot"):
        return declared
    return "spot" if (entity or {}).get("portable") else "room"


def light_at(scene: dict, name: str) -> str:
    """The light actually falling on one body.

    A room's ambient light, plus any source close enough to reach them. This is
    what makes a torch a torch: standing next to the person holding it you are
    lit, across the room you are a shape in the dark, and the room itself never
    became "lit" for everyone at once.
    """
    room_id = room_of(scene, name)
    if not room_id:
        return "lit"

    # Ambient: the room's own light, plus sources that fill a whole room.
    level = _brighter(room_light(scene, room_id),
                      source_light(scene, room_id, filling_only=True))

    entities = (scene or {}).get("entities") or {}
    positions = (scene or {}).get("positions") or {}
    for eid, entity in entities.items():
        if not isinstance(entity, dict) or not entity.get("light_source"):
            continue
        if _light_radius(entity) == "room":
            continue                      # already counted as ambient
        state = entity.get("state") if isinstance(entity.get("state"), dict) else {}
        if state.get("lit", True) in (False, 0, "off", "false", "no", "doused", "out"):
            continue
        label = str(entity.get("name") or eid)
        where = _ci_get(positions, eid)
        if where is None:
            where = _ci_get(positions, label)
        if where != room_id:
            continue

        emitted = normalize_light(entity.get("light_source"))
        # Held by this body, or standing in its pool: fully lit. Elsewhere in
        # the room: you can see the light without being in it.
        if str(label).strip().casefold() == str(name).strip().casefold() \
                or proximity_rel(scene, name, label) in ("within_reach", "near"):
            level = _brighter(level, emitted)
        else:
            level = _brighter(level, "dim" if emitted != "dark" else "dark")
    return level


def effective_light(scene: dict, room_id: str) -> str:
    """A room's light including what spills in from next door.

    A dark room with an open doorway onto a lit one is not pitch black -- there
    is enough to make out shapes, which is the difference between a cellar with
    the door open and a cellar with the door shut. Spill lifts dark to dim and
    never further: borrowed light does not let you read by it.
    """
    # Anything burning in here counts as much as anything built in -- but only
    # what actually fills the room. A hand torch is handled per body, in
    # light_at, so it never silently illuminates the far corner.
    own = _brighter(room_light(scene, room_id),
                    source_light(scene, room_id, filling_only=True))
    if own != "dark":
        return own

    rooms = (scene or {}).get("rooms") or {}
    room = rooms.get(room_id)
    if not isinstance(room, dict):
        return own

    for edge in room.get("adjacent") or []:
        if not isinstance(edge, dict):
            continue
        if normalize_barrier(edge.get("barrier")) not in _SIGHT_BARRIERS:
            continue
        if room_light(scene, edge.get("to")) in ("lit", "bright"):
            return "dim"
    return "dark"


def light_blocks_sight(level) -> bool:
    """Is there too little light here to see anything at all."""
    return normalize_light(level) == "dark"


# What light lets you make out, mirroring hear_level's none/fragment/full. A
# binary "can you see" cannot express the state most scenes actually want: a
# shape moving in the gloom that you cannot identify.
SIGHT_LEVELS = ("none", "shapes", "full")
_LIGHT_SIGHT = {
    "dark": "none",       # nothing, including the person beside you
    "dim": "shapes",      # movement, outline, bulk -- not faces, not detail
    "lit": "full",
    "bright": "full",
}


def sight_level(rel: dict) -> str:
    """How well these two can see each other: none | shapes | full.

    Barriers answer whether there is a line at all; light answers what that
    line carries. A lit room through an open door is full sight; the same room
    unlit is nothing; and dim is the interesting middle -- enough to know
    someone is there and not enough to know who.

    `crossing` is the third input, and it is about a BODY rather than a place:
    someone who has just gone through an opaque boundary is not instantly
    gone. Passing through a curtained doorway is watched from the room behind
    for as long as it takes -- so a crossing floors sight at `shapes` even
    where the barrier or the dark would otherwise answer `none`. It never
    RAISES sight above what the light allows; it only refuses to let a body
    vanish mid-step. See spatial_frames.infer_threshold_crossings for how long
    it lasts.
    """
    crossing = bool(rel.get("crossing"))
    # `concealed` is about a BODY being inside something rather than about the
    # rooms, and it outranks both barrier and light: a body in a closed bag is
    # not seen because the bag is shut, however bright the room and however
    # open the doorway. Only a crossing survives it -- being put in or climbing
    # out is watched.
    if rel.get("concealed"):
        return "shapes" if crossing else "none"
    if not _sight_line(rel):
        return "shapes" if crossing else "none"
    level = _LIGHT_SIGHT.get(normalize_light(rel.get("light")), "full")
    if crossing and level == "none":
        return "shapes"
    return level


def _sight_line(rel: dict) -> bool:
    """Is there a line of sight at all, ignoring light."""
    if rel.get("same_room"):
        return True
    return normalize_barrier(rel.get("barrier")) in _SIGHT_BARRIERS


def has_visual(rel: dict) -> bool:
    """Can these two see each other at all.

    The one place sight is decided, which is why see-through barriers land
    here: a body sealed in a glass container is visible to the room, and sees
    the room back. Passage and audibility are answered elsewhere and stay
    unchanged -- being seen through glass is not being reachable through it.

    Kept as the boolean every existing caller expects; `sight_level` is the
    graded answer underneath it.
    """
    return sight_level(rel) != "none"


# How many beats a body stays visibly mid-crossing after stepping through a
# boundary sight does not pass. Going through a doorway is an act with duration
# -- the room behind watches it happen -- and collapsing it into the instant
# the position field changes made bodies blink out of the world. Two beats: the
# one they step through on, and one more still half in it.
THRESHOLD_CROSSING_BEATS = 2


def crossing_of(scene: dict, name: str) -> Optional[dict]:
    """This body's live crossing record, or None.

    {from: room left, to: room entered, beats: how many remain}. Written at
    commit by spatial_frames.infer_threshold_crossings; read here so every
    sight decision sees it through the one function that decides sight.
    """
    rec = (scene.get("crossings") or {}).get(str(name or ""))
    if not isinstance(rec, dict):
        return None
    try:
        beats = int(rec.get("beats") or 0)
    except (TypeError, ValueError):
        return None
    return rec if beats > 0 else None


def crossing_visible_from(scene: dict, observer_room, name: str) -> bool:
    """Is `name` still visibly going through, watched from `observer_room`.

    Only from the room they LEFT. The room they are entering has them
    arriving, which is ordinary presence and needs no special case; the room
    behind is the one that would otherwise lose them the instant they crossed.

    The grace does NOT apply to a body-parented interior. It exists because
    going through a doorway takes time a position field cannot express, so a
    body would otherwise blink out mid-step -- but entry into the inside of a
    BODY is not a threshold anyone stands part-way through, and there is no
    shape to watch once it is done. Left as a doorway, this kept a body fully
    inside another rendering as `shapes` to the very body containing them for
    two more beats, which is the concealment failing at exactly the moment it
    matters most. What the surrounding body has instead is the touch channel,
    which containment already grants and which tells them far more than a
    silhouette would.
    """
    rec = crossing_of(scene, name)
    if not rec or not observer_room or rec.get("from") != observer_room:
        return False
    return _body_interior_holder(scene, name) is None


def spatial_rel_between(scene: dict, observer: str, target: str) -> dict:
    """`spatial_rel` for two BODIES rather than two rooms.

    Identical to the room-level form except that it carries whatever is true
    of these two specifically -- currently, whether the target is still
    part-way through a boundary the observer is standing behind.
    """
    rel = dict(spatial_rel(scene, room_of(scene, observer),
                           room_of(scene, target)))
    if crossing_visible_from(scene, room_of(scene, observer), target):
        rel["crossing"] = True
    holder = _body_interior_holder(scene, observer)
    if holder and holder.casefold() == str(target or "").strip().casefold():
        rel["inside_source"] = True
    # A carried body's position derives to its carrier's, so a body enclosed in
    # something standing right here reads as `same_room` -- which answers sight
    # before barriers or light are consulted at all.
    if containment_conceals(scene, observer, target):
        rel["concealed"] = True
    return rel


def visual_level_between(scene: dict, observer: str, target: str) -> str:
    """Graded sight from one BODY to another, accounting for local light.

    The room-level form cannot know that the target is standing in a torch's
    pool while the observer is not -- and that difference is exactly what a
    carried light is for.
    """
    rel = spatial_rel(scene, room_of(scene, observer), room_of(scene, target))
    crossing = crossing_visible_from(scene, room_of(scene, observer), target)
    if containment_conceals(scene, observer, target):
        return "shapes" if crossing else "none"
    if not _sight_line(rel):
        # Still going through: a shape in the doorway, not yet gone.
        return "shapes" if crossing else "none"
    # You see what is LIT, so the light that matters is the light on the thing
    # being looked at.
    level = _LIGHT_SIGHT.get(light_at(scene, target), "full")
    if crossing and level == "none":
        return "shapes"
    return level


def spatial_rel(
    scene: dict,
    a_room: Optional[str],
    b_room: Optional[str],
) -> dict:
    if not a_room or not b_room:
        return {
            "same_room": False,
            "barrier": "unknown",
            "distance": "remote",
            "note": "no known spatial channel between these entities",
        }

    if a_room == b_room:
        return {
            "same_room": True,
            "barrier": "open",
            "distance": "same",
            # Whether there is light to see by here. A dark room hides the
            # person standing next to you, which is why this is carried even
            # for the same-room case.
            "light": effective_light(scene, b_room),
        }

    rooms = scene.get("rooms") or {}

    for source, target in (
        (a_room, b_room),
        (b_room, a_room),
    ):
        room = rooms.get(source) or {}

        for edge in room.get("adjacent") or []:
            if not isinstance(edge, dict):
                continue

            if edge.get("to") != target:
                continue

            return {
                "same_room": False,
                "barrier": normalize_barrier(
                    edge.get("barrier")
                ),
                # What the barrier is made of, carried through so hearing can
                # account for it. Absent means "ordinary", which is the
                # behaviour every existing scene already had.
                "material": edge.get("material") or "",
                "distance": edge.get("distance", "near"),
                # The light in the room being LOOKED AT: seeing into a dark
                # room from a lit one is still seeing nothing.
                "light": effective_light(scene, b_room),
            }

    return {
        "same_room": False,
        "barrier": "separated",
        "distance": "far",
    }

_PASSABLE_BARRIERS = {"open", "open_door", "membrane"}

def passable_route_exists(
    scene: dict,
    from_room: Optional[str],
    to_room: Optional[str],
) -> bool:
    """True when to_room is reachable from from_room by walking only
    through passable doorways (barrier open / open_door), across any
    number of intermediate rooms.

    spatial_rel answers the DIRECT-adjacency question; this answers the
    traversal question the director_resolve movement backstop needs for a
    legitimate multi-room walk ("cross the corridor into the far office").
    Adjacency is treated as traversable in BOTH directions -- an open
    doorway declared from either side can be walked through either way
    (the nearby_rooms undirected-reachability precedent).

    A route requiring a still-closed door, wall, or unknown barrier does
    NOT count: only edges already passable this beat make a path. Callers
    that want a door opened this beat to count must pass a scene that
    already carries the beat's diff.
    """
    if not from_room or not to_room:
        return False
    if from_room == to_room:
        return True

    rooms = scene.get("rooms") or {}
    neighbors: dict[str, set] = {}
    for room_id, room in rooms.items():
        if not isinstance(room, dict):
            continue
        for edge in room.get("adjacent") or []:
            if not isinstance(edge, dict):
                continue
            target = edge.get("to")
            if not target:
                continue
            if normalize_barrier(edge.get("barrier")) not in _PASSABLE_BARRIERS:
                continue
            neighbors.setdefault(room_id, set()).add(target)
            neighbors.setdefault(target, set()).add(room_id)

    seen = {from_room}
    frontier = [from_room]
    while frontier:
        room_id = frontier.pop()
        for nxt in neighbors.get(room_id, ()):
            if nxt == to_room:
                return True
            if nxt not in seen:
                seen.add(nxt)
                frontier.append(nxt)
    return False

# What a barrier is MADE of, independent of what kind of barrier it is. A
# paper shoji screen and an oak door are both `closed_door` -- they stop a body
# and block sight identically -- and are nothing alike to listen through. The
# barrier type answers "can it be passed / seen through"; the material answers
# "what does it do to a voice", and conflating them made every closed door in
# every setting sound like the same door.
#
# A step of +1 means sound behaves as though the barrier were one grade more
# open; -1, one grade more solid. Deliberately coarse: fiction needs the
# difference between a paper screen and a stone wall, not an absorption
# coefficient.
_MATERIAL_SOUND_STEPS = {
    # Barely there acoustically -- a voice carries almost as if nothing stood
    # between, which is exactly the point of a screen you can be overheard
    # through.
    "paper": 1, "shoji": 1, "rice_paper": 1, "screen": 1, "curtain": 1,
    "cloth": 1, "fabric": 1, "canvas": 1, "tarp": 1, "beads": 1,
    "foliage": 1, "leaves": 1,
    # The default: an ordinary door or partition.
    "wood": 0, "timber": 0, "plank": 0, "plaster": 0, "drywall": 0,
    "panel": 0, "composite": 0,
    # Dense or sealed: sound loses another grade.
    "metal": -1, "steel": -1, "iron": -1, "glass": -1, "stone": -1,
    "brick": -1, "concrete": -1, "rock": -1, "earth": -1, "armor": -1,
    "armour": -1, "bulkhead": -1, "vault": -1, "lead": -1,
    "soundproof": -2, "insulated": -2, "sealed": -1, "airlock": -1,
}

# Ordered most open -> most solid. A material step moves the barrier along
# this ladder before the volume table is consulted.
# `membrane` is deliberately absent. The ladder is walked by relative steps, so
# inserting a rung anywhere silently changes what its NEIGHBOURS shift onto --
# putting it between `bars` and `closed_door` moved a paper screen (closed_door,
# one grade more open) off `bars` and onto it. A membrane's material is the
# membrane, so there is nothing for a material to modulate: _material_shifted_
# barrier leaves any barrier not on this ladder exactly as it found it.
_SOUND_LADDER = ("open", "open_door", "bars", "closed_door", "window", "wall")


def _material_shifted_barrier(barrier, material):
    """The barrier to LISTEN through, after accounting for what it is made of.

    Only the acoustic question is shifted. Sight and passage still read the
    real barrier, so a paper screen you cannot see through and cannot walk
    through is still exactly that -- it is only easy to hear through.
    """
    step = _MATERIAL_SOUND_STEPS.get(
        str(material or "").strip().casefold().replace(" ", "_"))
    if not step or barrier not in _SOUND_LADDER:
        return barrier
    index = _SOUND_LADDER.index(barrier)
    return _SOUND_LADDER[max(0, min(index - step, len(_SOUND_LADDER) - 1))]


def hear_level(
    rel: dict,
    volume: str,
    vouched: bool = False,
    proximity: str | None = None,
) -> str:
    volume = str(volume or "normal").strip().casefold()
    barrier = _material_shifted_barrier(
        normalize_barrier(rel.get("barrier")), rel.get("material"))
    distance = rel.get("distance")

    # Sound CONDUCTED rather than transmitted. A body inside another body's
    # interior is not listening through a wall: the enclosing body is the
    # medium, and its voice arrives through the mass around them -- close and
    # low rather than faint. Treating that as an ordinary opaque barrier left
    # an occupant unable to make out the one voice they are physically closest
    # to in the world.
    #
    # Strictly one-way. `inside_source` says the LISTENER is inside the
    # speaker; the reverse direction is a voice trying to get OUT through that
    # same mass, which is the muffling the barrier already models correctly.
    if rel.get("inside_source"):
        if volume in ("mutter", "whisper"):
            return "fragment"
        return "full"

    if rel.get("same_room"):
        # A whisper (mutter) only fully reaches someone WITHIN REACH; it carries
        # as a fragment to others merely near, and is lost across a large room.
        # proximity None (unknown) preserves the pre-Phase-2 behavior: same room
        # -> full. Only an explicit 'near'/'across' tier downgrades a whisper.
        if volume == "mutter":
            if proximity == "across":
                return "none"
            if proximity == "near":
                return "fragment"
        return "full"

    if barrier == "unknown" or distance == "remote":
        if not vouched:
            return "none"

        if volume in ("loud", "shout"):
            return "fragment"

        return "none"

    if barrier in ("open", "open_door"):
        if volume in ("normal", "loud", "shout"):
            return "full"

        if volume == "mutter":
            return "fragment"

        return "none"

    if barrier == "bars":
        # A grate is an acoustic hole. Sound passes as it would through an
        # open door -- which is the whole difference between a cage and a cell.
        if volume in ("normal", "loud", "shout"):
            return "full"

        if volume == "mutter":
            return "fragment"

        return "none"

    if barrier == "membrane":
        # Soft and opaque: nothing is seen through it and a good deal is heard.
        # It muffles rather than stops -- a raised voice carries, an ordinary
        # one arrives as a fragment, and something said under the breath does
        # not survive the crossing at all.
        if volume in ("loud", "shout"):
            return "full"

        if volume == "normal":
            return "fragment"

        return "none"

    if barrier == "window":
        # Glass is the opposite of bars: you are seen and not heard. Sealed
        # panes carry only real force, and never speech at conversational
        # volume -- which is why a shout through glass is a fragment, and a
        # normal sentence is nothing at all.
        return "fragment" if volume == "shout" else "none"

    if barrier == "closed_door":
        if volume in ("loud", "shout"):
            return "full"

        if volume == "normal":
            return "fragment"

        return "none"

    if barrier in ("wall", "separated"):
        return "fragment" if volume == "shout" else "none"

    return "none"

def can_perceive(rel: dict, volume: str = "normal") -> bool:
    return hear_level(rel, volume) != "none"

def nearby_rooms(
    scene: dict,
    center_room_ids,
    hops: int = 1,
) -> dict:
    """Rooms within `hops` adjacency steps of any of center_room_ids.

    Stage payloads currently serialize the entire scene.rooms dict into
    every LLM call regardless of relevance, so a large, mostly-explored
    building bloats every turn's context even though only the handful of
    rooms near where characters actually are matters for that turn's
    reasoning. This only trims what gets sent to a model -- deterministic
    checks (spatial_rel, hear_level, the passable-route validation in
    director_resolve) operate on the full, unfiltered scene in-process
    and must keep doing so; callers must filter only the payload copy,
    never the scene used for those checks.

    Adjacency is treated as undirected for this purpose (an edge declared
    from either side counts), since asymmetric declarations do happen and
    the question here is reachability for context purposes, not the
    perception-specific forward/reverse distinction visible_adjacent_rooms
    makes for what's visible through an open doorway.
    """
    rooms = scene.get("rooms") or {}

    neighbors: dict[str, set] = {}
    for room_id, room in rooms.items():
        if not isinstance(room, dict):
            continue
        for edge in room.get("adjacent") or []:
            if not isinstance(edge, dict):
                continue
            target = edge.get("to")
            if not target:
                continue
            neighbors.setdefault(room_id, set()).add(target)
            neighbors.setdefault(target, set()).add(room_id)

    included = {r for r in (center_room_ids or []) if r}
    frontier = set(included)

    for _ in range(max(0, hops)):
        next_frontier = set()
        for room_id in frontier:
            next_frontier |= neighbors.get(room_id, set()) - included
        if not next_frontier:
            break
        included |= next_frontier
        frontier = next_frontier

    return {rid: rooms[rid] for rid in included if rid in rooms}

def rooms_adjacent(scene, room_a, room_b):
    """Undirected: is room_b a declared neighbor of room_a (edge from either
    side)? Used to tell a real step (A->adjacent B) from a teleport/gap-cross."""
    if not room_a or not room_b:
        return False
    rooms = scene.get("rooms") or {}
    for a, b in ((room_a, room_b), (room_b, room_a)):
        room = rooms.get(a) or {}
        for edge in room.get("adjacent") or []:
            if isinstance(edge, dict) and edge.get("to") == b:
                return True
    return False


def egocentric_frame(scene, observer):
    """Classify the observer's current room's exits into egocentric buckets
    from their movement-derived orientation. Deterministic and authored-data
    free (see spatial_frames.infer_came_from for how orientation is set).

    Returns {behind, ahead, aside, left, right, unclassified, above, below} --
    each a list of adjacency edges -- plus 'ahead_entity' (an entity id) when
    focus is on an entity.

    Two reference frames, facing taking precedence when available:
      * FACING KNOWN + edge has a `dir` bearing: the edge is placed by
        relative_bearing(facing, dir) -- ahead / behind / left / right (diagonal
        sectors collapse to the lateral side). This is authoritative: it stays
        coherent even when the observer TURNS in place (facing a doorway they
        came through makes it 'ahead', not stale 'behind').
      * Otherwise: the movement fallback -- the room the observer came from ->
        BEHIND, the focused edge -> AHEAD, an edge with no usable facing/bearing
        -> ASIDE (topological only; a side is NEVER guessed).
    Vertical up/down always -> above/below first. With NO movement history AND
    no facing (scene open, fresh teleport) every exit is UNCLASSIFIED and
    callers must assert no egocentric direction.

    Pass-through inference: with a came_from but no facing, entering a room with
    a single non-vertical, non-behind, un-sided exit makes that exit AHEAD
    ('onward') -- the corridor case that otherwise reads as an unplaceable
    'aside'."""
    rooms = scene.get("rooms") or {}
    orientation = _ci_get(scene.get("orientation") or {}, observer) or {}
    room = rooms.get(room_of(scene, observer)) or {}
    edges = [e for e in (room.get("adjacent") or [])
             if isinstance(e, dict) and e.get("to")]

    came_from = orientation.get("came_from")
    facing = orientation.get("facing")
    focus = orientation.get("focus") or {}
    focus_edge = focus.get("ref") if focus.get("kind") == "edge" else None
    has_history = came_from is not None or facing is not None

    b = {"behind": [], "ahead": [], "aside": [], "left": [], "right": [],
         "unclassified": [], "above": [], "below": []}
    for e in edges:
        vert = str(e.get("vertical") or "").lower()
        if vert == "up":
            b["above"].append(e)
            continue
        if vert == "down":
            b["below"].append(e)
            continue
        if not has_history:
            b["unclassified"].append(e)
            continue
        rel = relative_bearing(facing, normalize_bearing(e.get("dir"))) \
            if facing else None
        if rel == "ahead":
            b["ahead"].append(e)
        elif rel == "behind":
            b["behind"].append(e)
        elif rel in _LEFT_SECTORS:
            b["left"].append(e)
        elif rel in _RIGHT_SECTORS:
            b["right"].append(e)
        elif focus_edge and e["to"] == focus_edge:
            b["ahead"].append(e)
        elif came_from is not None and e["to"] == came_from:
            b["behind"].append(e)
        else:
            b["aside"].append(e)

    # Pass-through: one behind + exactly one UN-SIDED lateral exit -> onward.
    # Only WITHOUT a facing: with a facing known, an un-beared exit's direction
    # is genuinely unknown (it stays 'aside'/topological) -- we do not guess it
    # 'ahead'. Also suppressed once a bearing placed any exit left/right.
    if facing is None and came_from is not None and not b["ahead"] \
            and len(b["aside"]) == 1 and not b["left"] and not b["right"]:
        b["ahead"] = b["aside"]
        b["aside"] = []

    if focus.get("kind") in ("entity", "target") and focus.get("ref"):
        b["ahead_entity"] = focus["ref"]
    return b


def spatial_digest(scene, observer):
    """Human-readable egocentric exits for the narrator: the observer's
    egocentric_frame with each edge rendered as {room, barrier}, grouped by
    bucket. The narrator binds egocentric direction words strictly to these
    buckets (see the narrator prompt's SPATIAL FRAME license). A digest with
    only 'unclassified' (or empty) means the observer has no movement history,
    so the narrator must assert no direction -- topological phrasing only."""
    rooms = scene.get("rooms") or {}
    frame = egocentric_frame(scene, observer)

    def ref(edge):
        rid = edge.get("to")
        return {"room": (rooms.get(rid) or {}).get("name") or rid,
                "barrier": edge.get("barrier")}

    out = {}
    for bucket in ("behind", "ahead", "left", "right", "aside",
                   "above", "below", "unclassified"):
        refs = [ref(e) for e in frame.get(bucket) or []]
        if refs:
            out[bucket] = refs
    if frame.get("ahead_entity"):
        # ref is an entity id (look up its name) or already a character name.
        ent = (scene.get("entities") or {}).get(frame["ahead_entity"]) or {}
        out["ahead_entity"] = ent.get("name") or frame["ahead_entity"]
    return out


# ---------------------------------------------------------------------------
# Within-room position (Phase 2): named anchors + entity stations.
#
# Rooms may carry an OPTIONAL `anchors` map {anchor_id: {desc, dir?}} naming the
# features prose already references (the bar, the hearth, a corner table); a
# doorway is implicitly an anchor via its edge. Entities may carry an OPTIONAL
# station in scene['stations'] {name: {at: anchor|None, near: [names]}}. From
# these we DERIVE proximity (within_reach / near / across) and a co-located
# entity's LEFT/RIGHT -- both read-only, never stored egocentric. Absent
# stations/anchors, everything degrades to "same room, unspecified" (near) with
# no side, i.e. exactly the pre-Phase-2 behavior.
# ---------------------------------------------------------------------------

def _station(scene: dict, name: str) -> dict:
    """The station record for `name`, tolerating case/alias keys the way
    room_of does. {} when none."""
    stations = scene.get("stations") or {}
    if name in stations and isinstance(stations[name], dict):
        return stations[name]
    ln = (name or "").lower().strip()
    for k, v in stations.items():
        if isinstance(v, dict) and str(k).lower().strip() == ln:
            return v
    return {}


def _anchor_dir(scene: dict, room_id: str, anchor_id) -> Optional[str]:
    """Compass bearing of an anchor within its room, or None."""
    if not anchor_id:
        return None
    anchors = ((scene.get("rooms") or {}).get(room_id) or {}).get("anchors") or {}
    a = anchors.get(anchor_id)
    return normalize_bearing(a.get("dir")) if isinstance(a, dict) else None


def proximity_rel(scene: dict, observer: str, target: str) -> Optional[str]:
    """Within-room proximity tier between two entities: 'within_reach' | 'near'
    | 'across', or None when they are not co-located. within_reach: same anchor,
    or a mutual 'near' station link. across: distinct anchors in a room flagged
    size 'large' (a great hall, a warehouse). Otherwise 'near' -- the safe
    default for an ordinary same-room pair, including when no stations exist."""
    o_room = room_of(scene, observer)
    t_room = room_of(scene, target)
    if not o_room or o_room != t_room:
        return None
    o_st, t_st = _station(scene, observer), _station(scene, target)
    o_at, t_at = o_st.get("at"), t_st.get("at")
    if (o_at and t_at and o_at == t_at) \
            or target in (o_st.get("near") or []) \
            or observer in (t_st.get("near") or []):
        return "within_reach"
    size = str(((scene.get("rooms") or {}).get(o_room) or {}).get("size") or "").lower()
    if o_at and t_at and o_at != t_at and size == "large":
        return "across"
    return "near"


def _ci_get(mapping, name):
    """Case/whitespace-tolerant dict lookup, matching room_of's key tolerance,
    so an orientation/station keyed 'Hinami' still resolves for a caller passing
    'hinami'. Returns None on miss."""
    if not isinstance(mapping, dict) or not name:
        return None
    if name in mapping:
        return mapping[name]
    ln = str(name).lower().strip()
    for k, v in mapping.items():
        if str(k).lower().strip() == ln:
            return v
    return None


def _relative_sector(scene: dict, observer: str, target: str) -> Optional[str]:
    """The egocentric sector (one of _REL_SECTORS) of a CO-LOCATED target
    relative to the observer's facing, from the target's anchor bearing. None
    without a facing and a beared target anchor -- never guessed. Also None when
    observer and target share the SAME anchor: the observer stands AT it, so the
    anchor's room bearing is not the target's direction from them (they are side
    by side). Approximation: the target anchor's absolute room bearing is taken
    as its direction from an observer near room centre."""
    o_room = room_of(scene, observer)
    if not o_room or o_room != room_of(scene, target):
        return None
    facing = (_ci_get(scene.get("orientation") or {}, observer) or {}).get("facing")
    if not facing:
        return None
    o_at = _station(scene, observer).get("at")
    t_at = _station(scene, target).get("at")
    if o_at and t_at and o_at == t_at:
        return None
    return relative_bearing(facing, _anchor_dir(scene, o_room, t_at))


def entity_side(scene: dict, observer: str, target: str) -> Optional[str]:
    """'left'/'right' for a CO-LOCATED target relative to the observer's facing.
    None without a facing and a beared anchor. Stays consistent when the
    observer turns (facing flips the sides)."""
    rel = _relative_sector(scene, observer, target)
    if rel in _LEFT_SECTORS:
        return "left"
    if rel in _RIGHT_SECTORS:
        return "right"
    return None


# Sectors that fall in an observer's rear arc -- the within-room blind spot.
_REAR_SECTORS = {"behind", "behind_left", "behind_right"}


def entity_arc(scene: dict, observer: str, target: str) -> Optional[str]:
    """'front' or 'rear' for a CO-LOCATED target relative to the observer's
    facing -- the within-room analogue of behind_rooms. A target in the REAR arc
    (behind / behind-left / behind-right of where the observer faces) is in the
    blind spot: the observer gets NO NEW VISUAL detail from them (a silent
    approach or gesture is unseen) though sound still carries. Someone WITHIN
    REACH is never a blind spot (they are at arm's length beside you) -> 'front'.
    None when facing or the target's anchor bearing is unknown -- with no basis,
    nothing is gated (the fail-open default for FOV)."""
    if proximity_rel(scene, observer, target) == "within_reach":
        return "front"
    rel = _relative_sector(scene, observer, target)
    if rel is None:
        return None
    return "rear" if rel in _REAR_SECTORS else "front"


def _sector_label(sector: Optional[str]) -> Optional[str]:
    """Collapse an 8-way sector to a coarse egocentric label for prose:
    ahead / behind / left / right (diagonals fold to their lateral side)."""
    if sector == "ahead":
        return "ahead"
    if sector == "behind":
        return "behind"
    if sector in _LEFT_SECTORS:
        return "left"
    if sector in _RIGHT_SECTORS:
        return "right"
    return None


def room_layout(scene: dict, observer: str) -> dict:
    """An egocentric map of the observer's CURRENT room, for a deliberate
    look-around/survey: {anchors:[{desc, side}], exits:{bucket:[{room,barrier}]},
    facing_known:bool}. Each anchor's `side` (ahead/behind/left/right, or None
    when facing/bearing is unknown -> describe it topologically) comes from the
    observer's facing vs the anchor's compass dir; exits reuse the egocentric
    digest. This is the DATA a convincing 'you look around' renders from -- the
    features, which way they lie, and where the ways out are."""
    o_room = room_of(scene, observer)
    room = (scene.get("rooms") or {}).get(o_room) or {}
    facing = ((scene.get("orientation") or {}).get(observer) or {}).get("facing")
    anchors = []
    for aid, a in (room.get("anchors") or {}).items():
        if not isinstance(a, dict):
            continue
        side = _sector_label(relative_bearing(facing, normalize_bearing(a.get("dir")))) \
            if facing else None
        anchors.append({"desc": a.get("desc") or aid, "side": side})
    return {"anchors": anchors, "exits": spatial_digest(scene, observer),
            "facing_known": bool(facing)}


def anchor_bearing_of(scene: dict, name: str) -> Optional[str]:
    """Compass bearing of the anchor the entity is currently stationed at,
    within its room; None if it has no station anchor or that anchor has no
    dir. Lets a character deterministically turn to FACE a co-located person by
    that person's anchor direction (see spatial_frames.infer_facing)."""
    room = room_of(scene, name)
    if not room:
        return None
    return _anchor_dir(scene, room, _station(scene, name).get("at"))


def normalize_scene_stations(scene: dict) -> dict:
    """Station hygiene, run at merge. Drops a station whose entity has no
    position; blanks an `at` naming an anchor absent from the entity's CURRENT
    room (so a room change auto-clears a stale anchor); drops `near` entries not
    co-located in the same room; then symmetrizes surviving `near` links. This
    makes a room move self-heal a character's within-room position with no
    separate commit inferer -- the old anchor and old near-links simply fail
    their membership tests once the position changes."""
    stations = scene.get("stations")
    if not isinstance(stations, dict):
        return scene
    positions = scene.get("positions") or {}
    rooms = scene.get("rooms") or {}

    for name in list(stations.keys()):
        st = stations.get(name)
        my_room = _ci_get(positions, name)
        if not isinstance(st, dict) or my_room is None:
            stations.pop(name, None)   # tolerant: a case-variant of a positioned name survives
            continue
        anchors = (rooms.get(my_room) or {}).get("anchors") or {}
        if st.get("at") and st["at"] not in anchors:
            st["at"] = None
        st["near"] = [n for n in (st.get("near") or [])
                      if _ci_get(positions, n) is not None and _ci_get(positions, n) == my_room]

    for name, st in list(stations.items()):
        for other in list(st.get("near") or []):
            o = stations.setdefault(other, {"at": None, "near": []})
            if isinstance(o, dict) and name not in (o.setdefault("near", [])):
                o["near"].append(name)
    return scene


# ---------------------------------------------------------------------------
# SCALE -- how big each body currently is, relative to its own baseline.
#
# A shrink or a growth is live physical state, so it lives in the scene blob
# with positions, stations and contacts rather than in a condition row: the
# things that must react to it (what can be reached, lifted, held, or gripped
# at all) are scene-level questions, and keeping them in one place is what
# stops the two accounts drifting.
#
# Absent means 1.0, so a scene that never mentions size behaves exactly as
# before -- the same fail-open the awareness gate uses.
_MIN_SCALE = 0.001            # a body reduced past this is a speck, not a body
_MAX_SCALE = 1000.0
# A change smaller than this is a growth spurt, not a reconfiguration: it does
# not break holds. Beyond it, the geometry that made a contact true is gone.
_SCALE_CONTACT_BREAK = 1.25
_MAX_SCALES = 40

# Ordered small -> large. The boundary is the RATIO to baseline, and the label
# is what a prompt and a narrator can actually use.
_SIZE_TIERS = (
    # 'tiny' shares its boundary with fits_in_other_hand below, so the label
    # and the capability agree: tiny IS "small enough to be held in a hand".
    (0.15, "tiny"),
    (0.5, "small"),
    (2.0, "comparable"),
    (20.0, "large"),
    (float("inf"), "huge"),
)


def clamp_scale(value):
    """A usable scale factor, or None when the value says nothing.

    Junk degrades to None (treated as baseline) rather than to a number, so a
    malformed declaration can never silently shrink someone.
    """
    try:
        factor = float(value)
    except (TypeError, ValueError):
        return None
    if factor != factor or factor in (float("inf"), float("-inf")):
        return None
    if factor <= 0:
        return None
    return max(_MIN_SCALE, min(factor, _MAX_SCALE))


def scale_of(scene: dict, name: str) -> float:
    """`name`'s current size relative to its own baseline. 1.0 when unstated."""
    scales = (scene or {}).get("scales") or {}
    if not isinstance(scales, dict):
        return 1.0
    return clamp_scale(_ci_get(scales, name)) or 1.0


def size_tier(factor) -> str:
    factor = clamp_scale(factor) or 1.0
    for bound, label in _SIZE_TIERS:
        if factor < bound:
            return label
    return "huge"


def normalize_scene_scales(scene: dict) -> dict:
    """Scale hygiene, run at merge.

    Clamps what is there and removes anything back at baseline, so "restored to
    normal" is expressed by setting 1.0 and leaves no residue behind.

    Deliberately NOT pruned by position, unlike contacts. A contact genuinely
    requires two bodies in one room; a size does not. Someone shrunk who steps
    offscreen for a scene is still shrunk when they return, and dropping the
    entry would silently restore them.
    """
    scales = scene.get("scales")
    if not isinstance(scales, dict):
        if scales is not None:
            scene["scales"] = {}
        return scene

    cleaned = {}
    for name, raw in scales.items():
        label = str(name or "").strip()
        if not label:
            continue
        factor = clamp_scale(raw)
        if factor is None or factor == 1.0:
            continue
        cleaned[label] = factor

    # Bounded so a runaway model cannot grow this without limit; a scene with
    # more than this many transformed bodies at once has other problems.
    if len(cleaned) > _MAX_SCALES:
        cleaned = dict(list(cleaned.items())[-_MAX_SCALES:])

    scene["scales"] = cleaned
    return scene


def scale_ratio(scene: dict, a: str, b: str) -> float:
    """How many times bigger `a` currently is than `b`."""
    other = scale_of(scene, b)
    return scale_of(scene, a) / other if other else 1.0


def size_relation(scene: dict, a: str, b: str) -> dict:
    """What `a`'s size permits against `b`, as deterministic ground truth.

    The Director owns whether an act succeeds; this only reports the geometry
    it should reason from, so "she is too small to reach the latch now" comes
    from a number rather than from vibes. Thresholds are deliberately coarse --
    fiction does not need a physics engine, it needs the difference between
    'comparable', 'can be picked up', and 'cannot be reached at all'.
    """
    ratio = scale_ratio(scene, a, b)
    return {
        "actor": a,
        "other": b,
        "ratio": round(ratio, 4),
        "actor_tier": size_tier(scale_of(scene, a)),
        "other_tier": size_tier(scale_of(scene, b)),
        # Lifting something roughly your own size is a feat; twice your size is
        # not happening without leverage the fiction has to supply.
        "can_lift_other": ratio >= 2.0,
        "can_be_lifted_by_other": ratio <= 0.5,
        # Small enough to be carried in one hand rather than hoisted.
        "fits_in_other_hand": ratio <= 0.15,
        # A body this much smaller cannot reach past the other's feet unaided,
        # nor act on anything at their head height.
        "can_reach_other_upper_body": ratio > 0.25,
        "can_be_stepped_over_by_other": ratio <= 0.34,
        # Fine work needs a hand roughly proportionate to what it works on. Too
        # large and a fingertip is broader than the thing being reached for, so
        # the act is not clumsy but impossible; too small and there is no
        # purchase. Precision is the first capability a size gap takes away,
        # well before reach or lifting.
        "can_do_fine_work_on_other": 0.25 <= ratio <= 4.0,
    }


def size_facts(scene: dict, observer: str, source_names) -> list:
    """Plain statements about relative size, for the observer's frame.

    Only emitted when someone is actually off-baseline: a scene of ordinary
    people generates nothing, exactly as before.
    """
    scales = scene.get("scales") or {}
    if not isinstance(scales, dict) or not scales:
        return []

    facts = []
    own = scale_of(scene, observer)
    if own != 1.0:
        facts.append(
            f"You are {size_tier(own)} right now — about "
            f"{_scale_phrase(own)} your normal size."
        )
    for name in source_names or []:
        if not name or name == observer:
            continue
        factor = scale_of(scene, name)
        if factor == 1.0 and own == 1.0:
            continue
        rel = size_relation(scene, observer, name)
        if 0.75 <= rel["ratio"] <= 1.34:
            continue  # near enough the same size to need no saying
        if rel["ratio"] < 1:
            clause = f"{name} towers over you"
            if rel["fits_in_other_hand"]:
                clause = f"{name} could close a hand around you"
            elif rel["can_be_lifted_by_other"]:
                clause = f"{name} could pick you up"
        else:
            clause = f"you tower over {name}"
            if rel["ratio"] >= 6.7:
                clause = f"{name} could fit in your hand"
            elif rel["can_lift_other"]:
                clause = f"you could pick {name} up"
        facts.append(clause + ".")
    return facts


def _scale_phrase(factor):
    if factor >= 1:
        return f"{factor:g}x"
    return f"1/{round(1 / factor):g} of"


# ---------------------------------------------------------------------------
# CONTAINMENT -- being carried, pocketed, jarred, or ridden along.
#
# The sibling of scale, and the reason it exists: a body shrunk to a tenth and
# picked up is not merely "in contact with" the hand holding it. It has stopped
# being an independently positioned thing. Contact alone left the tiny person
# free to walk out of the room while sitting in someone's pocket, because
# nothing tied their position to their container's.
#
# So a contained body's position is DERIVED, every merge, from whatever holds
# it -- transitively, so a person in a jar in a satchel goes where the satchel
# goes. Getting out is an explicit act the Director declares by releasing the
# containment, exactly like letting go of a hold; it is never a side effect of
# writing a position, because "they walked away" and "the Director forgot they
# were in a pocket" produce the identical diff and only one of them is meant.
#
# Interior rooms remain the mechanism for large containers you stand INSIDE (a
# ship, a building). This is for the other direction: a container that carries
# you as cargo.
_MAX_CONTAINED = 40
CONTAINMENT_MODES = (
    "held", "carried", "pocket", "container", "riding", "mounted", "worn",
)


def _clean_containment(raw, subject):
    if isinstance(raw, str):
        raw = {"in": raw}
    if not isinstance(raw, dict):
        return None
    holder = str(raw.get("in") or raw.get("container") or "").strip()
    if not holder or holder.casefold() == str(subject or "").strip().casefold():
        return None
    mode = str(raw.get("mode") or "").strip().casefold() or "carried"
    return {"in": holder, "mode": mode}


def container_of(scene: dict, name: str):
    """What is carrying `name`, or None."""
    contained = (scene or {}).get("contained") or {}
    if not isinstance(contained, dict):
        return None
    record = _ci_get(contained, name)
    if not isinstance(record, dict):
        return None
    return record.get("in") or None


def carrier_chain(scene: dict, name: str) -> list:
    """Every container above `name`, outermost last. Cycle-safe."""
    chain = []
    seen = {str(name or "").strip().casefold()}
    current = container_of(scene, name)
    while current:
        key = str(current).strip().casefold()
        if key in seen:
            break
        seen.add(key)
        chain.append(current)
        current = container_of(scene, current)
    return chain


def contents_of(scene: dict, container: str) -> list:
    """Everything `container` is directly carrying."""
    target = str(container or "").strip().casefold()
    if not target:
        return []
    contained = (scene or {}).get("contained") or {}
    if not isinstance(contained, dict):
        return []
    out = []
    for name, record in contained.items():
        if isinstance(record, dict) and \
                str(record.get("in") or "").strip().casefold() == target:
            out.append(name)
    return sorted(out)


# Being carried in the open and being carried INSIDE something are not the same
# fact, and nothing in the containment record distinguished them: a body in a
# pocket and a body in an open palm were equally visible to the room, because a
# carried body's position derives to its carrier's room and `same_room` answers
# sight before anything else gets a say. Interior rooms have had `enclosure` to
# settle this for a while; the carry path had no equivalent at all.
#
# These five are the documented ways a body is carried IN VIEW. Everything else
# -- the enclosed half of the vocabulary, or a mode the Director reached outside
# it to name -- puts the body inside something. Unknown reads as enclosed on
# purpose: the open cases are exactly this list, so a mode the engine cannot
# vouch for must not be the one that grants sight. Under-sharing is the safe
# failure for an engine whose whole promise is that nothing is known unless it
# was legitimately perceived. An ABSENT mode still defaults to "carried" in
# _clean_containment, so the ordinary carry keeps behaving exactly as before.
_OPEN_CONTAINMENT_MODES = frozenset({
    "held", "carried", "riding", "mounted", "worn",
})


def containment_hides(mode) -> bool:
    """Does being carried this way put a body out of the room's sight."""
    return str(mode or "").strip().casefold() not in _OPEN_CONTAINMENT_MODES


def _body_interior_holder(scene: dict, name: str):
    """The body whose INSIDE `name` is currently standing in, if any.

    A scene can express one body being inside another two ways. The
    `contained` ledger is one: an explicit record that a body is held in
    something. The other is a room -- an interior space parented to a body,
    which the occupant simply has as their position, exactly like any other
    room.

    Only the ledger was ever consulted, so the room form concealed nothing.
    A body fully inside another read as an ordinary occupant of an ordinary
    adjacent room: `containment_conceals` returned False in both directions,
    which left the observer outside with a sight channel to them and left the
    body inside with no touch channel to the body around it -- seen when they
    should not be, and not felt when they should be.

    A parent that holds a POSITION is a body; a parent that does not is a bag,
    a ship, a jar -- already handled by `_is_carried_interior` for a different
    question (whether you take its inside in as ambience).
    """
    rooms = (scene or {}).get("rooms") or {}
    positions = (scene or {}).get("positions") or {}
    room_id = _ci_get(positions, name)
    room = rooms.get(room_id) if room_id else None
    if not isinstance(room, dict):
        return None
    parent = str(room.get("parent_entity") or "").strip()
    if not parent:
        return None
    if _ci_get(positions, parent) is None:
        return None
    if parent.casefold() == str(name or "").strip().casefold():
        return None
    return parent


def _hiding_holders(scene: dict, name: str) -> list:
    """Holders that conceal `name`, innermost first. Cycle-safe."""
    contained = (scene or {}).get("contained") or {}
    if not isinstance(contained, dict):
        contained = {}
    out = []
    current = name
    seen = {str(name or "").strip().casefold()}
    while True:
        holder = None
        record = _ci_get(contained, current)
        if isinstance(record, dict) and record.get("in"):
            if not containment_hides(record.get("mode")):
                # Carried in the open: not a hiding holder, but keep walking
                # the chain -- its own holder may still be one.
                holder = record.get("in")
                key = str(holder).strip().casefold()
                if key in seen:
                    break
                seen.add(key)
                current = holder
                continue
            holder = record.get("in")
        else:
            holder = _body_interior_holder(scene, current)
        if not holder:
            break
        key = str(holder).strip().casefold()
        if key in seen:
            break
        seen.add(key)
        out.append(holder)
        current = holder
    return out


def hiding_holders_of(scene: dict, name: str) -> list:
    """Public form of `_hiding_holders` -- the enclosures around one body,
    innermost first, whether expressed as a `contained` record or as a
    body-parented interior room. Read it rather than `scene['contained']`
    directly, or the room form is invisible to the caller."""
    return list(_hiding_holders(scene, name))


def _innermost_hiding_holder(scene: dict, name: str):
    """The nearest enclosure `name` is shut inside, or None if in the open."""
    holders = _hiding_holders(scene, name)
    return str(holders[0]).strip().casefold() if holders else None


def containment_conceals(scene: dict, observer: str, target: str) -> bool:
    """Is sight between these two blocked by an enclosure around either.

    Sight needs both parties on the SAME side of every closed thing, so the
    test is that their nearest enclosure matches. Being shut inside something
    blocks the view out exactly as it blocks the view in -- a body in a closed
    bag can no more watch the room than the room can watch it, and that
    direction is the easier one to forget.

    The holder itself is not exempt. Something carried inside a body is not
    seen BY that body either: the holder is not inside its own enclosure, so
    the two do not match, and what it has instead of sight is touch. Two
    bodies inside the same enclosure do match, and see each other normally.
    """
    return (_innermost_hiding_holder(scene, observer)
            != _innermost_hiding_holder(scene, target))


def normalize_scene_containment(scene: dict) -> dict:
    """Containment hygiene, run at merge.

    Drops a record whose container has left the scene, and any record that
    would make a body contain itself directly or through a chain -- a cycle
    would otherwise make position derivation unresolvable.
    """
    contained = scene.get("contained")
    if not isinstance(contained, dict):
        if contained is not None:
            scene["contained"] = {}
        return scene

    positions = scene.get("positions") or {}
    entities = scene.get("entities") or {}

    cleaned = {}
    for name, raw in contained.items():
        subject = str(name or "").strip()
        if not subject:
            continue
        record = _clean_containment(raw, subject)
        if record is None:
            continue
        holder = record["in"]
        # The container must be something the scene actually knows about.
        if _ci_get(positions, holder) is None and holder not in entities \
                and not _ci_get({k: 1 for k in entities}, holder):
            continue
        cleaned[subject] = record

    scene["contained"] = dict(list(cleaned.items())[-_MAX_CONTAINED:])

    # Break cycles: walk each chain and drop the record that closes a loop.
    for subject in list(scene["contained"]):
        seen = {subject.strip().casefold()}
        current = scene["contained"][subject]["in"]
        while current:
            key = str(current).strip().casefold()
            if key in seen:
                scene["contained"].pop(subject, None)
                break
            seen.add(key)
            record = _ci_get(scene["contained"], current)
            current = record.get("in") if isinstance(record, dict) else None

    return scene


def derive_contained_positions(scene: dict) -> dict:
    """Put every contained body where its container is.

    This is what makes containment mean something: the position is not the
    contained body's to set. A tiny person in a pocket goes where the pocket
    goes and cannot be somewhere else, which is precisely what contact alone
    could not express.
    """
    contained = scene.get("contained")
    if not isinstance(contained, dict) or not contained:
        return scene
    positions = scene.get("positions")
    if not isinstance(positions, dict):
        return scene

    for subject in contained:
        room = None
        # Resolve against the OUTERMOST carrier, not the nearest one. An
        # intermediate container's own position is derived too, and may not
        # have been updated yet this pass -- reading it would hand the innermost
        # body a stale room while the satchel it is in has already moved.
        for holder in reversed(carrier_chain(scene, subject)):
            room = _ci_get(positions, holder)
            if room is not None:
                break
        if room is None:
            continue
        # Write under the key already in use, so this never mints a second
        # spelling of a name that positions already carries.
        for key in list(positions):
            if str(key).strip().casefold() == subject.strip().casefold():
                positions[key] = room
                break
        else:
            positions[subject] = room
    return scene


def containment_broken_by_scale_change(scene: dict, previous_scales) -> list:
    """Release anyone whose size change makes their container absurd.

    The counterpart of the contact rule, and the reason it matters: someone
    restored to full height while sitting in a coat pocket is not still in the
    coat pocket. The engine releases rather than guesses, and the Director
    re-declares the containment if it still holds.
    """
    contained = scene.get("contained")
    if not isinstance(contained, dict) or not contained:
        return []

    before = previous_scales if isinstance(previous_scales, dict) else {}
    now = scene.get("scales") or {}

    changed = set()
    for name in set(before) | set(now):
        was = clamp_scale(_ci_get(before, name)) or 1.0
        current = clamp_scale(_ci_get(now, name)) or 1.0
        if min(was, current) <= 0:
            continue
        if max(was, current) / min(was, current) >= _SCALE_CONTACT_BREAK:
            changed.add(str(name).strip().casefold())

    if not changed:
        return []

    released = []
    for subject in list(contained):
        record = contained.get(subject)
        holder = record.get("in") if isinstance(record, dict) else None
        if subject.strip().casefold() in changed or \
                str(holder or "").strip().casefold() in changed:
            contained.pop(subject, None)
            released.append(subject)
    return sorted(released)


def containment_facts(scene: dict, observer: str, source_names) -> list:
    """What the observer knows about being carried, or carrying."""
    facts = []
    holder = container_of(scene, observer)
    if holder:
        record = _ci_get(scene.get("contained") or {}, observer) or {}
        mode = record.get("mode") or "carried"
        facts.append(
            f"You are {mode} by {holder} — you go where {holder} goes, and "
            "cannot leave on your own until you are out."
        )
    visible = {str(n) for n in (source_names or []) if n} | {observer}
    for name in contents_of(scene, observer):
        record = _ci_get(scene.get("contained") or {}, name) or {}
        facts.append(f"{name} is {record.get('mode') or 'carried'} by you.")
    for name in visible:
        if name == observer:
            continue
        inner = [c for c in contents_of(scene, name) if c in visible]
        for c in inner:
            record = _ci_get(scene.get("contained") or {}, c) or {}
            facts.append(f"{c} is {record.get('mode') or 'carried'} by {name}.")
    return facts


# ---------------------------------------------------------------------------
# BODY POSITION TRACKING -- who is in contact with whom, and where.
#
# Contact used to live as prose inside an entity's own `state`: a single
# whole-body `target`, a `proximity` word, and a `description` paragraph
# ("mouth on throat ..., hips ..., tail coiled around the leg"). Model-written
# and model-read, with nothing structural in between, which cost four things:
#
#   * it could not say WHERE -- one whole-body target, so a hand on a shoulder
#     and a grip on a wrist were the same fact, and a hold on two different
#     people at once was unsayable;
#   * it was stored per entity, so one contact became two records (one on each
#     body) free to drift apart, and each was overwritten wholesale each beat;
#   * nothing ever cleared it -- it persisted verbatim until the model happened
#     to rewrite the paragraph, so a grip survived the person walking away; and
#   * no reader could query it, so the narrator had only prose to re-read and
#     was free to contradict it.
#
# A contact is a RELATION, so it is stored once, at scene level, in the same
# grain as `stations` (the within-room sibling of `positions`): a plain list
# that deterministic hygiene prunes at every merge. Movement clearing contact
# falls out of that hygiene rather than needing the model to remember -- exactly
# how a room change already self-heals a stale station anchor.
_MAX_CONTACTS = 40
_MAX_CONTACT_PART = 48

# Small controlled vocabulary. Unknown manners are kept (the fiction is wider
# than any list) but normalized to lowercase so equality holds.
CONTACT_MANNERS = (
    "touch", "hold", "grip", "press", "rest", "lean", "wrap", "coil",
    "straddle", "pin", "carry", "support", "kiss", "bite", "strike",
)


def _contact_text(value, limit=_MAX_CONTACT_PART):
    return str(value or "").strip()[:limit]


def _contact_key(contact):
    """Identity of a contact for dedup/removal: who, by what, on whom, where.
    `manner` is deliberately excluded -- a grip that becomes a caress is the
    same contact changing, not a second one."""
    return (
        _contact_text(contact.get("actor")).casefold(),
        _contact_text(contact.get("actor_part")).casefold(),
        _contact_text(contact.get("target")).casefold(),
        _contact_text(contact.get("target_part")).casefold(),
    )


def _mirror_key(key):
    """The same contact stated from the other side: pair and parts swapped."""
    actor, actor_part, target, target_part = key
    return (target, target_part, actor, actor_part)


def _clean_contact(raw):
    """A contact record, or None if it names nobody on one side."""
    if not isinstance(raw, dict):
        return None
    actor = _contact_text(raw.get("actor"), 120)
    target = _contact_text(raw.get("target"), 120)
    if not actor or not target:
        return None
    if actor.casefold() == target.casefold():
        return None  # a body is always in contact with itself; not a fact
    manner = _contact_text(raw.get("manner")).casefold() or "touch"
    return {
        "actor": actor,
        "actor_part": _contact_text(raw.get("actor_part")),
        "target": target,
        "target_part": _contact_text(raw.get("target_part")),
        "manner": manner,
    }


# ---- migrating contact out of entity state --------------------------------
# Before contacts existed, the Director recorded contact inside an entity's own
# `state`: `target` + `proximity` in the documented shape, and in practice a
# drift of invented keys naming the other body -- `leaning_against: "tamamo"`,
# `tails_wrapped_around: "Tamamo"`, `squished_against: "tamamo_side"`. Those
# assertions are real physical facts written in the wrong place, where nothing
# prunes them when the two walk apart.
#
# They are converted to contacts and REMOVED from the state, so exactly one
# record of a contact exists. Conversion is deliberately conservative: only a
# key whose NAME carries a contact verb, whose VALUE names a co-located person,
# converts. Adjacency words ("beside", "alongside") are not contact and are left
# untouched -- inventing a hold is worse than missing one, because a contact
# becomes ground truth the narrator is told.
#
# The free-text `description` paragraph is NOT parsed. Regex over prose would
# manufacture body parts and holds that were never asserted; it stays as the
# descriptive text it is, and the Director is told to stop putting contact in it.

# Never touched: the engine reads these structurally (movement, portals,
# perception's own deterministic backstop).
_PROTECTED_STATE_KEYS = frozenset({
    "transit", "link", "phase", "hatch", "destination_room", "route_room",
    "eta_seconds", "posture", "activity", "held_items", "zone", "description",
    "proximity", "target", "targets", "kind", "name",
})

# key-name fragment -> manner. Ordered: the first match wins, so "wrapped"
# beats a bare "on".
_CONTACT_KEY_MANNERS = (
    ("coil", "coil"), ("wrap", "wrap"), ("entwin", "wrap"),
    ("straddl", "straddle"), ("astride", "straddle"), ("mount", "straddle"),
    ("pin", "pin"), ("carry", "carry"), ("carried", "carry"),
    ("support", "support"), ("kiss", "kiss"), ("bit", "bite"),
    ("grip", "grip"), ("grasp", "grip"), ("clutch", "grip"),
    ("clench", "grip"), ("hold", "hold"), ("held", "hold"),
    ("embrac", "hold"), ("hug", "hold"), ("cling", "hold"),
    ("squish", "press"), ("press", "press"), ("flush", "press"),
    ("lean", "lean"), ("rest", "rest"), ("touch", "touch"),
    ("contact", "touch"), ("against", "press"), ("_on", "touch"),
)

# `proximity` values that assert actual contact rather than mere nearness.
_CONTACT_PROXIMITIES = (
    "press", "contact", "touch", "flush", "against", "entwin", "on_top",
    "straddl", "atop",
)


def _manner_from_fragment(text):
    low = str(text or "").casefold()
    for fragment, manner in _CONTACT_KEY_MANNERS:
        if fragment in low:
            return manner
    return None


def _part_from_key(key, manner_fragment):
    """The body part a legacy key names, if any: `tails_wrapped_around` -> the
    part is 'tails'. Only the segment BEFORE the contact verb counts."""
    low = str(key or "").casefold()
    index = low.find(manner_fragment)
    if index <= 0:
        return ""
    return low[:index].strip("_ ").replace("_", " ").strip()


def contacts_from_entity_state(scene: dict) -> dict:
    """Lift contact asserted inside entity `state` into scene.contacts.

    Converted keys are removed from the state, so one contact has exactly one
    record. Runs at merge, which also backfills a save written before contacts
    existed: the assertions become real contacts and then obey the same
    positional hygiene as everything else.
    """
    entities = scene.get("entities")
    if not isinstance(entities, dict):
        return scene
    positions = scene.get("positions") or {}
    if not positions:
        return scene

    # Who can be a contact partner: anyone (or anything) with a position,
    # matched loosely -- these values are model-written, so "tamamo" must find
    # "Tamamo". A value may also carry the part it touches: "tamamo_side" is
    # Tamamo's side, an observed shape. Returns (partner, target_part).
    normalized_positions = [
        (name, re.sub(r"[^a-z0-9]", "", str(name).casefold()))
        for name in positions
    ]

    def _resolve(value):
        text = re.sub(r"[^a-z0-9]", "", str(value or "").casefold())
        if not text:
            return None, ""
        for name, slug in normalized_positions:
            if slug and slug == text:
                return name, ""
        # `<person><part>` -- longest name first so "tamamo" cannot win over a
        # longer name that also starts with it.
        for name, slug in sorted(normalized_positions,
                                 key=lambda item: -len(item[1])):
            if slug and text.startswith(slug) and len(text) > len(slug):
                remainder = str(value or "").casefold()
                remainder = re.sub(r"[^a-z0-9]+", " ", remainder).strip()
                # Drop the name's own words, keep what is left as the part.
                for word in re.split(r"[^a-z0-9]+", str(name).casefold()):
                    if word:
                        remainder = remainder.replace(word, " ", 1)
                part = " ".join(remainder.split())[:_MAX_CONTACT_PART]
                if part.startswith("s "):     # "tamamo's side"
                    part = part[2:].strip()
                return name, part
        return None, ""

    derived = []
    for eid, entity in entities.items():
        if not isinstance(entity, dict):
            continue
        state = entity.get("state")
        if not isinstance(state, dict) or not state:
            continue
        actor = str(entity.get("name") or eid).strip()
        if not actor or _ci_get(positions, actor) is None:
            continue

        # The documented old shape: one whole-body target plus a proximity
        # word. Only a proximity that means CONTACT converts -- "close_on_bed"
        # is nearness, and stations already model that.
        proximity = str(state.get("proximity") or "").casefold()
        target_name, target_part = _resolve(state.get("target"))
        if target_name and any(p in proximity for p in _CONTACT_PROXIMITIES):
            derived.append({
                "actor": actor, "actor_part": "", "target": target_name,
                "target_part": target_part,
                "manner": _manner_from_fragment(proximity) or "press",
            })
            # This legacy pair asserted one contact jointly. Once lifted, remove
            # both halves just as the invented-key path below removes its source:
            # leaving them behind would re-create a pruned/removed contact on a
            # later merge as soon as the two bodies shared a room again.
            state.pop("target", None)
            state.pop("proximity", None)

        # The invented keys: a contact verb in the NAME, a person in the VALUE.
        for key in list(state.keys()):
            if key in _PROTECTED_STATE_KEYS:
                continue
            value = state.get(key)
            if not isinstance(value, str):
                continue
            partner, partner_part = _resolve(value)
            if partner is None or partner == actor:
                continue
            manner = None
            fragment = ""
            for frag, mapped in _CONTACT_KEY_MANNERS:
                if frag in str(key).casefold():
                    manner, fragment = mapped, frag
                    break
            if manner is None:
                continue  # not a contact assertion: leave it exactly as it is
            derived.append({
                "actor": actor,
                "actor_part": _part_from_key(key, fragment),
                "target": partner, "target_part": partner_part,
                "manner": manner,
            })
            state.pop(key, None)

    if derived:
        scene["contacts"] = list(scene.get("contacts") or []) + derived
    return scene


def contacts_broken_by_scale_change(scene: dict, previous_scales) -> list:
    """Drop every contact involving a body that just changed size.

    A hold is a fact about two bodies at the sizes they were. Shrink the held
    person to a tenth and "his hand grips her wrist" is not a smaller version
    of itself -- the wrist is no longer where the hand is, and whether anything
    equivalent is still possible is a question only the Director can answer.
    So the engine cancels rather than rescales: the grip is released, and the
    Director re-establishes whatever the new geometry actually permits.

    This is the same discipline movement already follows -- a contact that the
    physical situation no longer supports does not survive on inertia -- and it
    is why a size change cannot leave a phantom grip behind.

    Returns the names whose contacts were cancelled, for the caller to report.
    """
    contacts = scene.get("contacts")
    if not isinstance(contacts, list) or not contacts:
        return []

    before = previous_scales if isinstance(previous_scales, dict) else {}
    now = scene.get("scales") or {}

    changed = set()
    for name in set(before) | set(now):
        was = clamp_scale(_ci_get(before, name)) or 1.0
        current = clamp_scale(_ci_get(now, name)) or 1.0
        if was <= 0 or current <= 0:
            continue
        shift = max(was, current) / min(was, current)
        if shift >= _SCALE_CONTACT_BREAK:
            changed.add(str(name).strip().casefold())

    if not changed:
        return []

    kept = []
    for contact in contacts:
        if not isinstance(contact, dict):
            continue
        pair = {
            str(contact.get("actor") or "").strip().casefold(),
            str(contact.get("target") or "").strip().casefold(),
        }
        if pair & changed:
            continue
        kept.append(contact)

    scene["contacts"] = kept
    return sorted(changed)


def normalize_scene_contacts(scene: dict) -> dict:
    """Contact hygiene, run at merge -- the sibling of normalize_scene_stations.

    Drops a contact naming someone with no position (they are not in the
    scene), and any contact between two people who are not in the SAME room:
    you cannot hold someone you are not standing next to. That single rule is
    what makes walking away clear contact deterministically, with no separate
    inferer and nothing for the Director to remember -- the stale record simply
    fails its membership test the moment a position changes.

    Deduped on (actor, actor_part, target, target_part) keeping the LAST
    occurrence, so re-asserting a contact updates its manner rather than
    stacking a second copy.

    A MIRROR -- the same pair with the parts swapped -- is one physical contact
    stated from the other side, and only one record survives it. Both bodies
    describing the same hold is precisely how the old per-entity shape produced
    two records that drifted, and legacy extraction can surface it too when
    each entity's state named the other.
    """
    contacts = scene.get("contacts")
    if not isinstance(contacts, list):
        if contacts is not None:
            scene["contacts"] = []
        return scene

    positions = scene.get("positions") or {}
    kept = {}
    for raw in contacts:
        contact = _clean_contact(raw)
        if contact is None:
            continue
        actor_room = _ci_get(positions, contact["actor"])
        target_room = _ci_get(positions, contact["target"])
        if actor_room is None or target_room is None:
            continue
        if actor_room != target_room:
            continue
        key = _contact_key(contact)
        if _mirror_key(key) in kept:
            continue  # already recorded from the other side
        kept[key] = contact

    scene["contacts"] = list(kept.values())[-_MAX_CONTACTS:]
    return scene


def apply_contact_ops(scene: dict, ops) -> dict:
    """Apply state_diff.contact_ops to scene.contacts.

    add     -- upsert by (actor, actor_part, target, target_part)
    remove  -- drop matching contacts; parts omitted means "any contact
               between these two", so ending a hold does not require the
               Director to recall exactly which parts it recorded
    clear   -- with `actor`, every contact that person is part of (on either
               side); bare, the whole list

    Hygiene still runs afterwards, so an op naming someone in another room
    cannot smuggle in an impossible contact.
    """
    if not isinstance(ops, list) or not ops:
        return scene

    contacts = scene.get("contacts")
    if not isinstance(contacts, list):
        contacts = []
    current = {_contact_key(c): c for c in
               (_clean_contact(r) for r in contacts) if c is not None}

    for raw in ops:
        if not isinstance(raw, dict):
            continue
        op = str(raw.get("op") or "add").strip().casefold()

        if op == "clear":
            who = _contact_text(raw.get("actor"), 120).casefold()
            if not who:
                current = {}
                continue
            current = {
                key: c for key, c in current.items()
                if who not in (c["actor"].casefold(), c["target"].casefold())
            }
            continue

        if op == "remove":
            actor = _contact_text(raw.get("actor"), 120).casefold()
            target = _contact_text(raw.get("target"), 120).casefold()
            actor_part = _contact_text(raw.get("actor_part")).casefold()
            target_part = _contact_text(raw.get("target_part")).casefold()
            if not actor or not target:
                continue
            survivors = {}
            for key, c in current.items():
                pair = {c["actor"].casefold(), c["target"].casefold()}
                # Contact is physically symmetric, so a removal naming the two
                # in either order ends it.
                if pair != {actor, target}:
                    survivors[key] = c
                    continue
                if actor_part and c["actor_part"].casefold() != actor_part:
                    survivors[key] = c
                    continue
                if target_part and c["target_part"].casefold() != target_part:
                    survivors[key] = c
                    continue
            current = survivors
            continue

        contact = _clean_contact(raw)
        if contact is not None:
            key = _contact_key(contact)
            mirror = _mirror_key(key)
            # Re-asserting from the other side updates the contact already on
            # record rather than creating its twin.
            if mirror in current and key not in current:
                current[mirror] = {**current[mirror], "manner": contact["manner"]}
            else:
                current[key] = contact

    scene["contacts"] = list(current.values())[-_MAX_CONTACTS:]
    return scene


def contacts_of(scene: dict, name: str) -> list:
    """Every contact `name` is part of, on either side.

    The reader that did not exist before: "what is touching Hinami" was only
    answerable by re-reading a prose paragraph and hoping.
    """
    target = str(name or "").strip().casefold()
    if not target:
        return []
    out = []
    for contact in (scene.get("contacts") or []):
        if not isinstance(contact, dict):
            continue
        if target in (str(contact.get("actor") or "").strip().casefold(),
                      str(contact.get("target") or "").strip().casefold()):
            out.append(contact)
    return out


def contact_phrase(contact: dict, *, subject_first=True) -> str:
    """One contact as a plain clause: 'Bramwell's hand grips Hinami's waist'."""
    if not isinstance(contact, dict):
        return ""
    actor = str(contact.get("actor") or "").strip()
    target = str(contact.get("target") or "").strip()
    if not actor or not target:
        return ""
    manner = str(contact.get("manner") or "touch").strip() or "touch"
    actor_part = str(contact.get("actor_part") or "").strip()
    target_part = str(contact.get("target_part") or "").strip()

    left = f"{actor}'s {actor_part}" if actor_part else actor
    right = f"{target}'s {target_part}" if target_part else target
    if not subject_first:
        return f"{right} is under {left} ({manner})"
    return f"{left} {manner}s {right}" if not manner.endswith("s") \
        else f"{left} {manner} {right}"


def spatial_facts(scene: dict, observer: str, source_names) -> list:
    """Deterministic, authoritative one-line spatial statements for a beat, from
    the observer's frame -- GROUND TRUTH a weak narrator must not contradict
    (it need NOT recite them; restraint still governs how much is said). Covers
    exit directions and co-located people (proximity tier, side, rear blind
    spot). Empty when nothing is derivable. This is scaffolding against weak
    models flipping 'behind' to 'ahead' or swapping who is where."""
    facts = []
    digest = spatial_digest(scene, observer)
    dir_word = {"behind": "behind you", "ahead": "ahead of you",
                "left": "to your left", "right": "to your right",
                "above": "above you", "below": "below you"}
    for bucket, word in dir_word.items():
        for ref in digest.get(bucket) or []:
            facts.append(f"{ref['room']} lies {word}.")
    tier_word = {"within_reach": "within arm's reach beside you",
                 "near": "a few steps away", "across": "across the room"}
    for name in source_names or []:
        if name == observer:
            continue
        tier = proximity_rel(scene, observer, name)
        if tier is None:
            continue
        clause = f"{name} is {tier_word.get(tier, 'nearby')}"
        if entity_arc(scene, observer, name) == "rear":
            clause += ", behind you and out of your sight (you hear, not see, them)"
        else:
            side = entity_side(scene, observer, name)
            if side:
                clause += f", on your {side}"
        facts.append(clause + ".")

    # Body position: contact is objective, and it is the fact a narrator most
    # easily contradicts -- describing hands that let go a beat ago, or a hold
    # that was never recorded.
    #
    # BOTH parties must be nameable to this observer, exactly like the
    # proximity clauses above, which only ever iterate source_names. These
    # lines carry canonical names, so a contact involving someone the observer
    # does not recognize would hand the narrator a name the observer has no way
    # to know -- the leak this engine exists to prevent. Being held by a
    # stranger therefore yields no line here rather than a named one; the
    # perception view still reports the hold in the observer's own terms.
    # Relative size, when anyone is off their baseline. This is the fact that
    # silently invalidates everything else -- reach, lifting, whether a hold is
    # even possible -- so it is stated before the contacts below it.
    # Light before anything else: it decides whether the rest of this list is
    # perceivable at all.
    here = effective_light(scene, room_of(scene, observer))
    if here == "dark":
        facts.append(
            "It is pitch dark here — you cannot see anything, including the "
            "people in this room with you.")
    elif here == "dim":
        facts.append("The light here is dim; shapes and movement, not detail.")
    elif here == "bright":
        facts.append("The light here is harsh and bright.")

    # Bodily condition, when the story tracks it at all. Lazy import: survival
    # reads spatial for sealed-enclosure detection, and this is the only edge
    # back the other way.
    if scene.get("vitals"):
        from survival import vitals_facts
        facts.extend(vitals_facts(scene, observer))

    facts.extend(size_facts(scene, observer, source_names))
    # Being carried is a harder constraint than any of the above: it decides
    # where you are at all, so the narrator is told before it describes anyone
    # walking anywhere.
    facts.extend(containment_facts(scene, observer, source_names))

    visible = {str(n) for n in (source_names or []) if n} | {observer}
    for contact in (scene.get("contacts") or []):
        if not isinstance(contact, dict):
            continue
        actor = str(contact.get("actor") or "").strip()
        target = str(contact.get("target") or "").strip()
        if actor not in visible or target not in visible:
            continue
        phrase = contact_phrase(contact)
        if phrase:
            facts.append(phrase + ".")
    return facts


def _is_carried_interior(scene, room_id):
    """Is `room_id` the inside of something a body is carrying.

    You do not take in the inside of a bag, a case, a jar or a pocket as part
    of taking in the room it is being carried through -- looking in is an act,
    not ambience. Without this, every interior attached to a carried entity was
    permanently in its owner's field of view, so a character stood there
    perpetually perceiving the inside of their own belongings.

    Deliberately keyed on the CARRIER relation (or portability), not on any
    notion of smallness: a ship's hold you are walking through is an interior
    too, and it stays visible because nobody is carrying the ship.
    """
    rooms = (scene or {}).get("rooms") or {}
    room = rooms.get(room_id)
    if not isinstance(room, dict):
        return False
    parent = room.get("parent_entity")
    if not parent:
        return False

    entities = (scene or {}).get("entities") or {}
    entity = entities.get(parent)
    if not isinstance(entity, dict):
        entity = next(
            (e for e in entities.values()
             if isinstance(e, dict)
             and str(e.get("name") or "").strip().casefold()
             == str(parent).strip().casefold()),
            {},
        )
    if entity.get("portable"):
        return True
    # Carried right now, by a hand or inside another container.
    return container_of(scene, parent) is not None or \
        container_of(scene, str(entity.get("name") or "")) is not None


# How far a straight passage can be read, and how the reading coarsens. Sight
# down a corridor is real -- you see that it ends before you walk it -- but it
# degrades with distance into "somewhere along there", which is the form worth
# handing a character.
CORRIDOR_SIGHT_LIMIT = 6
_CORRIDOR_VAGUENESS = ((1, "just ahead"), (2, "a short way"),
                       (4, "some way"), (99, "far"))
# How many rooms down a line are NAMED. Beyond this the passage is reported as
# running on, without contents -- which is both what sight gives you and what
# keeps this from becoming a page per beat.
_CORRIDOR_NAMED = 2


def _reverse_dir(d):
    return {"n": "s", "s": "n", "e": "w", "w": "e"}.get(str(d or "").lower())


def corridor_sightlines(scene, room_id):
    """What can be seen looking STRAIGHT along each passage out of a room.

    A character could previously see one room and no further, so a corridor
    ending three rooms north was indistinguishable from one running on -- he
    had to walk it. But you can see down a straight passage, and that you
    cannot see round the corner is what makes it worth having: sight follows
    the line until the passage turns, a door blocks it, or the dark swallows
    it.

    Deliberately coarse, and coarser with distance. The useful percept is "some
    way north the passage comes to an end", not a room count -- so `distance`
    is carried for ordering and `vagueness` for rendering, and a caller should
    prefer the latter.

    Returns [] when the scene's edges carry no `dir`, since without direction
    there is no line to follow and guessing one would invent a sense.
    """
    rooms = (scene or {}).get("rooms") or {}
    start = rooms.get(room_id)
    if not isinstance(start, dict):
        return []
    out = []
    for edge in start.get("adjacent") or []:
        if not isinstance(edge, dict) or not edge.get("dir"):
            continue
        heading = str(edge["dir"]).lower()
        if normalize_barrier(edge.get("barrier")) not in _SIGHT_BARRIERS:
            continue
        cur, prev, dist, terminus = edge.get("to"), room_id, 1, None
        # What is made out ALONG the line, not merely where it ends. Detail
        # decays the way sight does: the near chamber is read plainly, the next
        # by its one memorable feature, past that only that something is there.
        # Capped at _CORRIDOR_NAMED because a full description per room per
        # direction would be a page of prose every beat -- and because nobody
        # reads the far end of a corridor in that much detail anyway.
        along = []
        while cur and dist <= CORRIDOR_SIGHT_LIMIT:
            room = rooms.get(cur)
            if not isinstance(room, dict):
                terminus = None
                break
            # Anything short of full sight stops the line. Light spills
            # through an open doorway, so a dark room beside a lit one reads
            # `dim` -- and shapes are enough to know something is there, not
            # enough to read whether a passage ends. Reporting a terminus
            # through gloom would be inventing detail.
            if _LIGHT_SIGHT.get(effective_light(scene, cur), "full") != "full":
                terminus = "darkness"
                break
            onward = [
                e for e in (room.get("adjacent") or [])
                if isinstance(e, dict) and str(e.get("to")) != str(prev)
                and normalize_barrier(e.get("barrier")) not in ("wall",)
            ]
            if not onward:
                terminus = "dead_end"
                break
            if len(along) < _CORRIDOR_NAMED:
                along.append({
                    "room": room.get("name") or cur,
                    "detail": "clear" if dist == 1 else "landmark",
                })
            straight = [e for e in onward
                        if str(e.get("dir") or "").lower() == heading
                        and normalize_barrier(e.get("barrier")) in _SIGHT_BARRIERS]
            if len(onward) > 1:
                terminus = "opening"      # a junction: the line stops being one line
                break
            if not straight:
                terminus = "turn"         # the passage bends; sight stops here
                break
            prev, cur, dist = cur, straight[0].get("to"), dist + 1
        if terminus:
            out.append({
                "dir": heading, "distance": dist, "terminus": terminus,
                "vagueness": next(v for lim, v in _CORRIDOR_VAGUENESS
                                  if dist <= lim),
                "along": along,
            })
    return out


def _onward_exits(scene, all_rooms, target_id, from_room):
    """How many ways out of `target_id` lead somewhere other than back here.

    Looking through a doorway into a chamber, you see whether it has another
    way out -- that is ordinary sight, not deduction. Without it a character
    has to physically walk into a dead end to discover it is one, which is
    exactly what was observed: a maze runner entered the same one-exit chamber
    six times, having never been given the one fact that would have told him.

    Omitted entirely when the room is too dark to make out, because then you
    genuinely cannot see its doorways. Absent means "could not tell", never
    "none" -- a caller must not read a missing key as a dead end.
    """
    if _LIGHT_SIGHT.get(effective_light(scene, target_id), "full") == "none":
        return {}
    room = all_rooms.get(target_id) or {}
    onward = 0
    for edge in room.get("adjacent") or []:
        if not isinstance(edge, dict):
            continue
        if normalize_barrier(edge.get("barrier")) == "wall":
            continue
        if str(edge.get("to")) != str(from_room):
            onward += 1
    return {"onward_exits": onward}


def visible_adjacent_rooms(
    scene: dict,
    room_id: str,
    extra_rooms: dict | None = None,
) -> list[dict]:
    if not room_id:
        return []

    all_rooms = dict(
        scene.get("rooms") or {}
    )

    if extra_rooms:
        all_rooms.update(extra_rooms)

    visible = []
    seen = set()

    # Forward adjacency: the current room explicitly points to another.
    current_room = all_rooms.get(room_id) or {}

    for edge in current_room.get("adjacent") or []:
        if not isinstance(edge, dict):
            continue

        barrier = normalize_barrier(
            edge.get("barrier")
        )

        if barrier not in _SIGHT_BARRIERS:
            continue

        adjacent_id = edge.get("to")
        if _is_carried_interior(scene, adjacent_id):
            continue

        if (
            not adjacent_id
            or adjacent_id not in all_rooms
            or adjacent_id in seen
        ):
            continue

        room_data = all_rooms[adjacent_id]
        notes = (
            room_data.get("notes")
            or room_data.get("desc")
            or ""
        )

        if not notes:
            continue

        visible.append({
            "room_id": adjacent_id,
            "room_name": (
                room_data.get("name")
                or adjacent_id
            ),
            "barrier": barrier,
            "description": notes[:800],
            **_onward_exits(scene, all_rooms, adjacent_id, room_id),
        })
        seen.add(adjacent_id)

    # Reverse adjacency: another room explicitly points back to the
    # current room. Do not include unrelated rooms with arbitrary open
    # edges.
    for other_id, room_data in all_rooms.items():
        if (
            other_id == room_id
            or other_id in seen
            or not isinstance(room_data, dict)
        ):
            continue

        for edge in room_data.get("adjacent") or []:
            if not isinstance(edge, dict):
                continue

            barrier = normalize_barrier(
                edge.get("barrier")
            )

            if (
                edge.get("to") != room_id
                or barrier not in _SIGHT_BARRIERS
                or _is_carried_interior(scene, other_id)
            ):
                continue

            notes = (
                room_data.get("notes")
                or room_data.get("desc")
                or ""
            )

            visible.append({
                "room_id": other_id,
                "room_name": (
                    room_data.get("name")
                    or other_id
                ),
                "barrier": barrier,
                "description": notes[:800],
            })
            seen.add(other_id)

            break

    return visible

def is_derived_room_name(room_id, name) -> bool:
    """Is `name` just the room id spelled out -- the placeholder the
    staged-lore materializers in commit.py and agents/director.py use when a
    room has to exist before anyone has named it? Such a name must never
    displace an authored one (see _merge_room)."""
    text = str(name or "").strip()
    return bool(text) and text == str(room_id or "").replace("_", " ").title()


def _merge_room(existing: dict, incoming: dict, room_id=None) -> dict:
    """Merge an incoming room redeclaration into an already-known room.

    A director/mapping model redeclaring a room to add or change one
    adjacency edge has no reliable way to also echo back every other edge
    it didn't touch. Replacing the whole room (the old behavior) silently
    drops every edge the model didn't re-mention -- observed live when
    generating a west wing connection wiped out an existing corridor's
    links to the entrance hall and stairwell. Adjacency is merged by
    upserting on `to`: an incoming edge with the same target updates it
    (so barrier/distance changes still work), edges not mentioned survive.
    Explicit removal goes through `remove_adjacent`, not silence.
    """
    merged_room = dict(existing)

    for field in ("name", "desc", "notes", "parent_entity"):
        if not incoming.get(field):
            continue
        if field == "name" and existing.get("name") \
                and is_derived_room_name(room_id, incoming[field]):
            continue  # an id slug never overwrites a name someone authored
        merged_room[field] = incoming[field]

    existing_edges = {
        edge.get("to"): dict(edge)
        for edge in (existing.get("adjacent") or [])
        if isinstance(edge, dict) and edge.get("to")
    }

    for edge in (incoming.get("adjacent") or []):
        if isinstance(edge, dict) and edge.get("to"):
            existing_edges[edge["to"]] = dict(edge)

    merged_room["adjacent"] = list(existing_edges.values())

    for key, value in incoming.items():
        if key in ("name", "desc", "notes", "parent_entity", "adjacent"):
            continue
        merged_room[key] = value

    return merged_room

# Every SceneEntityDef field whose schema default is indistinguishable from
# "the model did not mention this". A diff carrying one of these cannot be
# read as an erasure -- see _merge_entity.
_ENTITY_DEFAULT_FIELDS = {
    "kind": "object",
    "description": "",
    "aliases": [],
    "portable": False,
    "container": False,
    "interior_rooms": [],
    "ubiquitous": False,
    # Absent from this map, these two could only ever be set at CREATION: the
    # merge below copies listed fields and leaves everything else at whatever
    # the existing record held, so a Director declaring `enclosure` on an
    # entity it had already introduced was silently dropped every time. That
    # made both fields unfixable in flight -- an interior authored see-through
    # stayed see-through for the rest of the story, and a lamp that came back
    # without its emission could never get it back. None is the right default
    # here precisely because it is what "not declared" already looks like, so
    # silence still reads as silence.
    "enclosure": None,
    "light_source": None,
}


def _merge_entity(entity_id, existing: dict, incoming: dict) -> dict:
    """Merge an incoming entity redeclaration into an already-known entity.

    The exact sibling of _merge_room, and for the same reason: a Director
    updating one entity's pose has no way to echo back the description,
    aliases and interior rooms it did not touch. `entities.update(diff)`
    replaced the whole record instead -- and because validation fills every
    absent field with a schema default first, the replacement looked
    complete. Observed live (Elevator Adventure branch 41) on a pose-only
    diff: "Blue Police Box" (kind vehicle, container, interior_rooms
    ["tardis_interior_001"]) became "Tardis 001", kind object, no interior;
    the registered character "The Doctor" became an object named "The
    Doctor 10". Both then read back corrupted on every later turn.

    So a schema DEFAULT is treated as silence, never as an erasure, and a
    name the validator derived from the key cannot displace a real one.
    Deliberate changes still land: any non-default value wins, and
    genuinely clearing a field goes through remove_entities, not silence.
    """
    merged = dict(existing)

    incoming_name = str(incoming.get("name") or "").strip()
    existing_name = str(existing.get("name") or "").strip()
    if incoming_name and not (
        existing_name
        and is_derived_entity_name(entity_id, incoming_name,
                                   incoming.get("kind"))
    ):
        merged["name"] = incoming_name

    for field, default in _ENTITY_DEFAULT_FIELDS.items():
        if field not in incoming:
            continue
        value = incoming[field]
        if value == default and existing.get(field, default) != default:
            continue  # silence, not an erasure
        merged[field] = value

    # `state` is the live, per-beat half of an entity and is the field a
    # partial diff most often carries alone: merge key-wise so a pose
    # update keeps the transit//link state the same entity depends on.
    incoming_state = incoming.get("state")
    if isinstance(incoming_state, dict):
        state = dict(existing.get("state") or {})
        state.update(incoming_state)
        merged["state"] = state
    elif "state" in incoming:
        merged["state"] = incoming_state

    for key, value in incoming.items():
        if key == "name" or key == "state" or key in _ENTITY_DEFAULT_FIELDS:
            continue
        merged[key] = value

    return merged


def _dedupe_adjacent(edges):
    """Collapse adjacency edges that target the same room, keeping the LAST
    occurrence for each target (matching _merge_room's upsert-by-'to').

    _merge_room already dedupes, but ONLY for a room present in the incoming
    diff. A room the model doesn't re-declare this turn is carried through the
    merge verbatim, so a duplicate 'to' edge introduced once -- e.g. when
    rename-remapping rewrites two edges onto the same target -- otherwise
    persists frozen across every subsequent turn. That leaves a room
    simultaneously walled off from AND open-doored to the same neighbor
    (barrier 'wall' and 'open_door' at once), which makes perception's spatial
    cues incoherent. Deduping every room on every merge heals it. First-seen
    'to' order is preserved; malformed edges (no 'to') pass through untouched."""
    seen, order, extras = {}, [], []
    for edge in edges or []:
        if isinstance(edge, dict) and edge.get("to"):
            if edge["to"] not in seen:
                order.append(edge["to"])
            seen[edge["to"]] = edge  # last wins, matching _merge_room
        else:
            extras.append(edge)
    return [seen[t] for t in order] + extras

# ---------------------------------------------------------------------------
# Moving rooms / transit: derived dock edges.
#
# The interior<->exterior doorway of a parent_entity-linked room (an elevator
# car, a ship cabin, a carried container) is NOT a static fact: it is derived
# from where the entity currently IS (its exterior position) and its transit
# state (docked/sealed/in transit, hatch open/closed). Storing it as an
# ordinary adjacency edge -- which the establish/mapping prompts historically
# forced at creation -- meant nothing ever updated the edge when the entity
# moved or sealed, leaving a stale portal to the departure room (live
# instance: an elevator narrated as sealed and descending whose room kept an
# open_door edge onto the smoke-filled hallway it left). These functions
# recompute that doorway deterministically from the entity's own structured
# state, joining the infer_vehicle_zones/infer_companion_carry family of
# mechanical follow-throughs: the model authors WHAT the entity is doing
# (state.transit / state.link, its position); code derives the adjacency.
#
# Pure function of the scene, idempotent, run from merge_scene_with_diff so
# every consumer (commit preparation, mid-turn perception merges) sees the
# same derived edges without any reader changes.
# ---------------------------------------------------------------------------

# Phases during which an entity's interior has NO doorway to the outside
# world (beyond an optional route_room -- the shaft/ocean/sky it moves
# through). "arriving" keeps the hatch shut against the destination until
# the director docks it.
_TRANSIT_CLOSED_PHASES = {"sealed", "in_transit"}

def _transit_state(entity) -> Optional[dict]:
    """entity.state.transit if present and well-formed:
    {phase: docked|sealed|in_transit|arriving, hatch: open|closed|locked,
     destination_room?, eta_seconds?, route_room?}."""
    if not isinstance(entity, dict):
        return None
    state = entity.get("state")
    transit = state.get("transit") if isinstance(state, dict) else None
    return transit if isinstance(transit, dict) else None

# What an entity's enclosure is MADE of, which decides what it still lets
# through. `enclosure` sits beside portable/container as a structural fact: a
# glass case and a strongbox are both closed, and only one of them is opaque.
#
# It used to describe only the CLOSED state, on the assumption that an open way
# in is an open way to look in. That holds for a lid or a door and fails for
# every soft or draped opening, where the way in is opaque in both states --
# `membrane` is that case, and the one enclosure whose OPEN doorway is not
# see-through.
CONTAINER_ENCLOSURES = ("opaque", "transparent", "barred", "membrane")


def _is_body_entity(scene: dict, eid: str, ent: dict) -> bool:
    """Is this entity a body rather than a vehicle, room-sized object or box.

    Asked of the scene alone so the dock-edge derivation stays a pure function.
    Bodies are the things that WEAR something and the things that have a SIZE
    relative to their own baseline; a lift car, a ship and a crate have
    neither. Checked across every scene on disk when this was written, the
    split was exact: every vehicle/structure/container interior scored false
    on both, and every body scored true on `attire`.

    `container: true` is deliberately NOT the test -- it is absent on plenty of
    real vehicles, so it misclassifies them as bodies.
    """
    keys = [eid]
    if isinstance(ent, dict):
        keys.append(ent.get("name"))
        keys.extend(ent.get("aliases") or [])
    for source in ("attire", "scales"):
        table = scene.get(source) or {}
        if not isinstance(table, dict):
            continue
        for key in keys:
            key = str(key or "").strip()
            if key and _ci_get(table, key) is not None:
                return True
    return False


def infer_body_enclosures(scene: dict) -> bool:
    """Default a BODY's interior to an opaque way in. Idempotent; mutates.

    The `membrane` enclosure only helps if something declares it, and the
    Director does not reliably do so -- observed live, on a fresh interior
    authored after the prompt asked for it. Relying on a model to remember a
    safety property every time is the wrong shape for this engine: flesh is
    opaque whether or not anyone remembered to say so.

    So an interior belonging to a body defaults to `membrane` when nothing was
    declared. An explicit `enclosure` always wins -- including `transparent`,
    so a deliberately see-through case stays authorable -- and vehicles,
    cabins and containers are untouched, keeping their see-through open
    doorway.
    """
    entities = scene.get("entities") or {}
    changed = False
    for eid, ent in entities.items():
        if not isinstance(ent, dict) or not ent.get("interior_rooms"):
            continue
        if str(ent.get("enclosure") or "").strip():
            continue                      # authored: never override
        if not _is_body_entity(scene, eid, ent):
            continue
        ent["enclosure"] = "membrane"
        changed = True
    return changed


def _open_enclosure_barrier(ent):
    """The doorway barrier for an OPEN entity interior.

    `open_door` for everything that opens by swinging a lid or a hatch aside,
    which is the historical behaviour and stays the default. A `membrane`
    enclosure is the exception: passable in both states and never see-through,
    so entering one hides its occupant instead of exposing them.
    """
    enclosure = str((ent or {}).get("enclosure") or "").strip().casefold()
    if enclosure == "membrane":
        return "membrane"
    return "open_door"


def _closed_enclosure_barrier(ent):
    """The doorway barrier for a CLOSED entity interior.

    Opaque is the default and the old behaviour. Transparent yields a window --
    a body sealed inside is visible to the room and can see out, without being
    reachable. Barred yields bars, which also carries sound.
    """
    enclosure = str((ent or {}).get("enclosure") or "").strip().casefold()
    if enclosure == "transparent":
        return "window"
    if enclosure == "barred":
        return "bars"
    return "closed_door"


def _link_state(entity) -> Optional[dict]:
    """entity.state.link if present and well-formed: a traversable link
    (portal, gate, wormhole) {rooms: [a, b], phase: open|closed} that, when
    open, derives an edge between two arbitrary rooms."""
    if not isinstance(entity, dict):
        return None
    state = entity.get("state")
    link = state.get("link") if isinstance(state, dict) else None
    if not isinstance(link, dict):
        return None
    rooms = link.get("rooms")
    if not isinstance(rooms, list) or len(rooms) != 2:
        return None
    return link

def _entity_exterior_room(scene: dict, eid: str, entity: dict) -> Optional[str]:
    """The room the entity itself currently occupies -- tolerating positions
    keyed by entity id, display name, or an alias (the same read tolerance
    merge_scene_with_diff's remove_entities path already applies)."""
    positions = scene.get("positions") or {}
    candidates = [eid]
    if isinstance(entity, dict):
        candidates.append(entity.get("name"))
        candidates.extend(entity.get("aliases") or [])
    for cand in candidates:
        cand = str(cand or "").strip()
        if cand and cand in positions:
            return positions[cand]
    return None

def apply_transit_dock_edges(scene: dict) -> bool:
    """Rewrite every parent_entity room's exterior adjacency to match
    f(entity position, entity.state.transit), and every state.link entity's
    derived portal edge to match its phase. Returns True when anything
    changed. Idempotent; mutates `scene` in place.

    Per entity with interior rooms:
    - docked (or no transit state) + hatch open  -> edge to the entity's
      exterior room, barrier open_door -- or membrane, when the entity's
      `enclosure` says the way in is opaque even standing open (an existing
      edge to that room otherwise keeps its authored barrier/distance when no
      hatch state overrides it);
    - docked + hatch closed/locked -> same edge, barrier closed_door;
    - sealed / in_transit -> exterior edges severed (a closed_door edge to
      transit.route_room only, when one is set -- the shaft/ocean/sky);
    - arriving -> closed_door edge to transit.destination_room.

    Which interior room carries the doorway is remembered via a `dock_exit`
    marker stamped on any interior room seen with an exterior edge (rooms
    carry arbitrary extra keys through merges untouched -- the zone-field
    precedent), so sealing and later re-docking restores the door to the
    same room. An entity's sole interior room is always the dock room.

    Only the canonical FORWARD edge (interior -> exterior) is kept; stale
    reverse edges from plain world rooms into the interior are stripped.
    Rooms that are themselves another entity's interior are never stripped
    -- a nested mover (a car on a ferry's vehicle deck) manages its own
    dock edge through its own entity's rewrite, which is what makes the
    model compose for nesting.
    """
    rooms = scene.get("rooms") or {}
    entities = scene.get("entities") or {}
    changed = False

    interiors: dict[str, list] = {}
    for rid, room in rooms.items():
        if isinstance(room, dict) and room.get("parent_entity"):
            interiors.setdefault(room["parent_entity"], []).append(rid)

    for eid, ent in entities.items():
        if not isinstance(ent, dict):
            continue

        # --- traversable links (portals): derived edge between two rooms ---
        link = _link_state(ent)
        if link:
            a, b = (str(link["rooms"][0] or ""), str(link["rooms"][1] or ""))
            is_open = str(link.get("phase") or "open").casefold() == "open"
            for room in rooms.values():
                if not isinstance(room, dict):
                    continue
                adjacency = room.get("adjacent") or []
                kept = [e for e in adjacency
                        if not (isinstance(e, dict) and e.get("via_link") == eid)]
                if len(kept) != len(adjacency):
                    room["adjacent"] = kept
                    changed = True
            if is_open and a in rooms and b in rooms and a != b:
                rooms[a].setdefault("adjacent", []).append({
                    "to": b, "barrier": "open_door",
                    "distance": str(link.get("distance") or "near"),
                    "via_link": eid,
                })
                changed = True

        interior_ids = interiors.get(eid)
        if not interior_ids:
            continue
        same = set(interior_ids)
        transit = _transit_state(ent)
        exterior = _entity_exterior_room(scene, eid, ent)

        # A container is not "in transit" -- a jar with a lid has a hatch and
        # no journey -- so the lid is read from state.hatch as well as from a
        # transit blob. Transit wins when both are present, since a vehicle
        # sealing for a journey is the stronger statement.
        entity_state = ent.get("state") if isinstance(ent.get("state"), dict) else {}
        hatch = str(
            (transit or {}).get("hatch")
            or entity_state.get("hatch")
            or "open"
        ).casefold()
        phase = str((transit or {}).get("phase") or "docked").casefold()
        # (target, barrier); barrier None = preserve whatever was authored.
        if transit is None and not entity_state.get("hatch"):
            # Nothing declared about the way in: keep whatever was authored
            # (barrier None), UNLESS the enclosure itself settles the question.
            # A membrane is opaque by construction, so an authored `open_door`
            # onto one is a description the enclosure contradicts -- and
            # preserving it is what let a body walk into an interior and stay
            # in plain view of the room outside.
            target = exterior
            barrier = (_open_enclosure_barrier(ent)
                       if str(ent.get("enclosure") or "").strip().casefold()
                       == "membrane" else None)
        elif transit is None:
            # A static container: the lid alone decides the doorway.
            target = exterior
            barrier = (_closed_enclosure_barrier(ent)
                       if hatch in ("closed", "locked")
                       else _open_enclosure_barrier(ent))
        elif phase in _TRANSIT_CLOSED_PHASES:
            target = str(transit.get("route_room") or "") or None
            barrier = "closed_door"
        elif phase == "arriving":
            target = str(transit.get("destination_room") or "") or exterior
            barrier = "closed_door"
        else:  # docked, or an unrecognized phase read conservatively as docked
            target = exterior
            barrier = (_closed_enclosure_barrier(ent)
                       if hatch in ("closed", "locked")
                       else _open_enclosure_barrier(ent))

        # No authoritative exterior at all (entity has no recorded position)
        # outside an explicitly closed phase: there is nothing to derive the
        # doorway FROM, and severing on missing data would cut off a cabin
        # whose authored edge is the only truth available. Leave it alone --
        # only an explicit sealed/in_transit state severs without a target.
        if target is None and phase not in _TRANSIT_CLOSED_PHASES:
            continue

        for rid in interior_ids:
            room = rooms[rid]
            adjacency = [e for e in (room.get("adjacent") or [])
                         if isinstance(e, dict)]
            interior_edges = [e for e in adjacency if e.get("to") in same]
            exterior_edges = [e for e in adjacency if e.get("to") not in same]
            if exterior_edges and not room.get("dock_exit"):
                room["dock_exit"] = True
                changed = True
            is_dock = bool(exterior_edges) or bool(room.get("dock_exit")) \
                or len(interior_ids) == 1
            new_adjacency = list(interior_edges)
            if is_dock and target:
                prev = next((e for e in exterior_edges if e.get("to") == target),
                            exterior_edges[0] if exterior_edges else None)
                if barrier is None:
                    resolved_barrier = normalize_barrier(
                        (prev or {}).get("barrier") or "open_door")
                else:
                    resolved_barrier = barrier
                new_adjacency.append({
                    "to": target, "barrier": resolved_barrier,
                    "distance": (prev or {}).get("distance") or "near",
                })
            if new_adjacency != adjacency:
                room["adjacent"] = new_adjacency
                changed = True

        # Strip stale reverse edges from plain world rooms into this
        # entity's interiors (the canonical edge is forward-only; spatial_rel
        # and visible_adjacent_rooms both resolve either direction). Another
        # entity's interior room is exempt -- see docstring (nesting).
        for orid, oroom in rooms.items():
            if orid in same or not isinstance(oroom, dict) \
                    or oroom.get("parent_entity"):
                continue
            adjacency = oroom.get("adjacent") or []
            kept = [e for e in adjacency
                    if not (isinstance(e, dict) and e.get("to") in same)]
            if len(kept) != len(adjacency):
                oroom["adjacent"] = kept
                changed = True

    return changed

# ---------------------------------------------------------------------------
# Nesting-aware ambient scope (movement/space Phase 1, item 5).
#
# Read-only helpers over the SCENE's containment structure (rooms'
# parent_entity + derived dock edges) -- deliberately NOT the lorebook
# graph: a currently_within link is retrieval bookkeeping and must never
# be read as perception authorization. These answer "whose ambience can
# legitimately reach this observer right now?" so location-scoped
# information does not leak into a sealed nested interior (the port must
# not color the inside of a sealed elevator).
# ---------------------------------------------------------------------------

_AMBIENT_BARRIERS = {"open", "open_door", "bars"}

def containment_chain(scene: dict, room_id: str) -> list:
    """Rooms from room_id outward through entity containment: the room
    itself, then -- for each enclosing parent_entity -- that entity's
    exterior room, and so on. [{'room': rid, 'entity': enclosing_eid|None}]
    ordered innermost-first. Cycle-safe."""
    chain = []
    seen = set()
    rooms = scene.get("rooms") or {}
    entities = scene.get("entities") or {}
    current = room_id
    while current and current not in seen:
        seen.add(current)
        room = rooms.get(current)
        eid = room.get("parent_entity") if isinstance(room, dict) else None
        chain.append({"room": current, "entity": eid})
        if not eid:
            break
        current = _entity_exterior_room(scene, eid, entities.get(eid) or {})
    return chain

def ambient_scope(scene: dict, room_id: str):
    """(rooms, open_to_world): the set of rooms whose ambient signal can
    reach room_id -- its connected component through open/open_door
    barriers (either edge direction) in the current derived graph -- and
    whether that component reaches any room that is not an entity
    interior. With dock edges applied, a sealed vehicle's interior scopes
    to just itself (open_to_world False); docked with an open hatch it
    scopes out to the exterior. An unknown room is treated as open (no
    filtering on missing data)."""
    rooms = scene.get("rooms") or {}
    if not room_id or room_id not in rooms:
        return ({room_id} if room_id else set()), True
    graph: dict[str, set] = {}
    for rid, room in rooms.items():
        if not isinstance(room, dict):
            continue
        for edge in room.get("adjacent") or []:
            if not isinstance(edge, dict):
                continue
            to = edge.get("to")
            if to not in rooms:
                continue
            if normalize_barrier(edge.get("barrier")) in _AMBIENT_BARRIERS:
                graph.setdefault(rid, set()).add(to)
                graph.setdefault(to, set()).add(rid)
    seen = {room_id}
    queue = [room_id]
    while queue:
        current = queue.pop()
        for nxt in graph.get(current, ()):
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    open_to_world = any(
        not (isinstance(rooms.get(rid), dict)
             and rooms[rid].get("parent_entity"))
        for rid in seen
    )
    return seen, open_to_world

def _dedup_duplicate_position_keys(positions, entities, incoming_positions=None):
    """Collapse a position keyed under BOTH an entity's id and its display name
    to one key. Only a genuine duplicate is touched; a lone id-keyed position
    (an object with no name twin) is left alone. When both keys are present the
    FRESH write wins -- the one in this diff's incoming positions -- else the
    display-name key (the convention `room_of` and every character use).
    """
    if not isinstance(positions, dict) or not isinstance(entities, dict):
        return positions
    incoming = incoming_positions if isinstance(incoming_positions, dict) else {}
    for eid, ent in list(entities.items()):
        name = (ent.get("name") or "").strip() if isinstance(ent, dict) else ""
        if not name or name == eid:
            continue
        if eid in positions and name in positions:
            # Prefer whichever key this diff just wrote; default to the name.
            if eid in incoming and name not in incoming:
                positions[name] = positions.pop(eid)
            else:
                positions.pop(eid, None)
    return positions


# Durable structural facts about an entity, as opposed to `state`, which is a
# snapshot of right now. When two records for one entity are collapsed these
# survive from whichever record has them; `state` never merges (see below).
_ENTITY_STRUCTURAL_FIELDS = (
    "kind", "subtype", "name", "description", "aliases", "interior_rooms",
    "portable", "container", "ubiquitous", "parent_entity",
    # What the thing is made of and what it gives off are as durable as what
    # it is -- and were being lost whenever two records for one entity
    # collapsed, which is the other half of the same gap.
    "enclosure", "light_source",
)


def _dedup_duplicate_entity_keys(entities, incoming_entities=None):
    """Collapse an entity recorded under BOTH its id and its display name.

    The third instance of one bug. A character legitimately answers to several
    scene keys -- display name, identity.uid, aliases (see
    agents.common.character_scene_keys) -- and the Director keys with whichever
    it reaches for. `positions` survived that because readers try every key and
    duplicates collapse (_dedup_duplicate_position_keys); `attire` was healed
    after a character rendered as wearing nothing while her clothing state still
    described her coat (commit._heal_attire_identity_keys). `entities` had
    neither, and it is the record that says what each body is doing and what it
    is in contact with.

    Observed live: one character held two entity records -- `char_9f13c0a4...`
    frozen at the beat it was created, and `Bramwell` written every beat
    since. Both claimed to describe her, so "who is in contact with whom" had
    two contradictory answers at once, one of them arbitrarily old, and every
    reader that walks entities saw the same person twice.

    Unlike attire, `state` is NOT merged: a wardrobe accumulates, but contact
    and posture describe a single instant, so folding a stale snapshot into a
    fresh one is what manufactures the contradiction. The fresh record's state
    wins whole. Only the structural fields above are rescued from the loser, so
    collapsing can never drop a vehicle's interior_rooms or an entity's aliases.
    """
    if not isinstance(entities, dict):
        return entities
    incoming = incoming_entities if isinstance(incoming_entities, dict) else {}

    for eid, ent in list(entities.items()):
        if not isinstance(ent, dict):
            continue
        name = str(ent.get("name") or "").strip()
        if not name or name == eid or name not in entities:
            continue
        twin = entities.get(name)
        if not isinstance(twin, dict) or twin is ent:
            continue

        # The display name is the surviving KEY either way (the convention every
        # reader uses); which record's content survives depends on which one
        # this diff just wrote.
        if eid in incoming and name not in incoming:
            winner, loser = ent, twin
        else:
            winner, loser = twin, ent

        merged = dict(winner)
        for field in _ENTITY_STRUCTURAL_FIELDS:
            if field not in merged or merged.get(field) in (None, "", [], {}):
                if loser.get(field) not in (None, "", [], {}):
                    merged[field] = loser[field]
        merged["name"] = name

        entities[name] = merged
        entities.pop(eid, None)

    return entities


def merge_scene_with_diff(
    scene: dict,
    diff: dict | None,
) -> dict:
    diff = diff or {}
    # A scene is a nested mutable structure.  A shallow copy allowed
    # downstream normalization and deterministic backstops (zone stamping,
    # adjacency edits, overlays, attire) to mutate the caller's supposedly
    # pre-diff scene through shared child dictionaries/lists.  That made
    # before/after comparisons order-dependent and could contaminate rollback
    # preparation.  Scene merges are correctness boundaries, so pay the small
    # cost of a real copy here.
    merged = copy.deepcopy(scene)

    merged["rooms"] = dict(merged.get("rooms") or {})
    merged["entities"] = dict(merged.get("entities") or {})
    merged["positions"] = dict(merged.get("positions") or {})

    incoming_rooms = diff.get("rooms") or {}
    incoming_entities = diff.get("entities") or {}
    incoming_positions = diff.get("positions") or {}
    incoming_stations = diff.get("stations") or {}

    if isinstance(incoming_rooms, dict):
        for room_id, incoming_room in incoming_rooms.items():
            if not isinstance(incoming_room, dict):
                continue
            existing_room = merged["rooms"].get(room_id)
            merged["rooms"][room_id] = (
                _merge_room(existing_room, incoming_room, room_id)
                if isinstance(existing_room, dict)
                else incoming_room
            )

    if isinstance(incoming_entities, dict):
        for entity_id, incoming_entity in incoming_entities.items():
            existing_entity = merged["entities"].get(entity_id)
            merged["entities"][entity_id] = (
                _merge_entity(entity_id, existing_entity, incoming_entity)
                if isinstance(existing_entity, dict)
                and isinstance(incoming_entity, dict)
                else incoming_entity
            )

    # An entity keyed by its id in one beat and by its display name in the next
    # leaves TWO records for one body -- each with its own posture and contact,
    # one of them frozen at whatever beat it was last written. Collapse before
    # anything reads them (positions dedup below reads entities, and every
    # perception/narration reader walks this dict).
    _dedup_duplicate_entity_keys(merged["entities"], incoming_entities)

    if isinstance(incoming_positions, dict):
        merged["positions"].update(incoming_positions)
    # DW-4: an entity can end up in `positions` under BOTH its id key and its
    # display-name key -- e.g. an auto-created backstory person seeded with an
    # id-keyed position (`karen_marsh`) while director_resolve moves it by name
    # (`Karen Marsh`). The blind update() above then leaves BOTH, so the entity
    # is co-present in two rooms and perception's co-present set is corrupted.
    # Collapse only a genuine id+name DUPLICATE -- a lone id-keyed object
    # position (tardis, a dropped item) has no name-key twin and is untouched.
    _dedup_duplicate_position_keys(
        merged["positions"], merged["entities"], incoming_positions)

    # Stations (within-room position) are a sibling of positions, merged per
    # entity so a diff touching only `at` keeps the entity's `near` list, and
    # vice versa. Hygiene (phantom-anchor blanking, non-colocated pruning,
    # symmetrization) runs below via normalize_scene_stations.
    if isinstance(incoming_stations, dict) and incoming_stations:
        merged["stations"] = dict(merged.get("stations") or {})
        for name, st in incoming_stations.items():
            if isinstance(st, dict):
                cur = dict(merged["stations"].get(name) or {})
                cur.update(st)
                merged["stations"][name] = cur

    for removal in diff.get("remove_adjacent") or []:
        if not isinstance(removal, dict):
            continue
        room = merged["rooms"].get(removal.get("room"))
        target = removal.get("to")
        if not isinstance(room, dict) or not target:
            continue
        room["adjacent"] = [
            edge for edge in (room.get("adjacent") or [])
            if not (isinstance(edge, dict) and edge.get("to") == target)
        ]

    for entity_id in diff.get("remove_entities") or []:
        entity = merged["entities"].pop(entity_id, None)

        if not entity:
            continue

        names = {
            entity_id,
            str(entity.get("name") or ""),
            *(entity.get("aliases") or []),
        }

        for name in names:
            if name:
                merged["positions"].pop(name, None)

    occupied_rooms = set(merged["positions"].values())

    for room_id in diff.get("remove_rooms") or []:
        if room_id in occupied_rooms:
            continue
        merged["rooms"].pop(room_id, None)

    # A body's interior is opaque whether or not anyone declared it so. Runs
    # BEFORE the dock-edge rewrite, which reads `enclosure` to pick the
    # doorway's barrier.
    infer_body_enclosures(merged)

    # Derived dock/portal edges are a function of the merged scene, not an
    # authored fact -- recompute them here so every consumer of a merge
    # (commit preparation, perception's mid-turn merges) sees the same
    # correct doorways. Runs before barrier normalization, which then
    # canonicalizes whatever the rewrite emitted.
    apply_transit_dock_edges(merged)

    # Collapse duplicate same-target adjacency edges across EVERY room, not
    # just the ones re-declared this turn -- otherwise a duplicate frozen into
    # an untouched room (a neighbor that is both walled and open-doored) leaks
    # incoherent spatial cues into perception forever. See _dedupe_adjacent.
    for room in merged["rooms"].values():
        if isinstance(room, dict) and room.get("adjacent"):
            room["adjacent"] = _dedupe_adjacent(room["adjacent"])

    normalize_scene_barriers(merged)
    # Optional compass bearings on edges: canonicalize each `dir` and reconcile
    # reciprocals so either room can derive a consistent left/right. Runs after
    # dedupe (so only surviving edges are reconciled) and barrier normalization.
    normalize_scene_bearings(merged)
    # Within-room station hygiene: prune stale anchors/near-links (auto-heals a
    # room move) and symmetrize proximity. Runs after positions are final.
    if merged.get("stations"):
        normalize_scene_stations(merged)
    # Body position tracking: apply this beat's contact ops, then prune every
    # contact that positions no longer permit. Runs LAST, after positions are
    # final, which is what makes walking away end a hold with nothing for the
    # Director to remember.
    # Lift any contact the Director wrote into an entity's own state (the shape
    # that predates contacts, and the one a model still reaches for) before the
    # ops, so both paths land in one place and one truth survives.
    contacts_from_entity_state(merged)
    # The key always exists after a merge, empty or not: a reader that has to
    # ask whether contact tracking is "on" for this scene is a reader that will
    # eventually forget to.
    merged.setdefault("contacts", [])

    # Scale FIRST, and the contacts it invalidates with it -- before this
    # beat's contact ops, not after. A size change cancels the holds that were
    # standing when it happened; the Director is then expected to re-establish
    # whatever the new geometry allows IN THE SAME BEAT, and those ops must
    # survive. Cancelling after them would wipe exactly the correct behaviour.
    incoming_scales = diff.get("scales")
    previous_scales = dict(merged.get("scales") or {})
    if isinstance(incoming_scales, dict) and incoming_scales:
        scales = dict(previous_scales)
        for name, raw in incoming_scales.items():
            label = str(name or "").strip()
            if not label:
                continue
            factor = clamp_scale(raw)
            # An explicit 1.0 (or an unusable value) means "back to normal";
            # normalize_scene_scales drops it, which is the same thing.
            scales[label] = factor if factor is not None else 1.0
        merged["scales"] = scales
    merged.setdefault("scales", {})
    normalize_scene_scales(merged)
    # The return value is for callers/tests; nothing is stashed in the scene,
    # which is saved verbatim and must not accumulate scratch keys.
    contacts_broken_by_scale_change(merged, previous_scales)

    # Containment. Declared as {subject: {"in": holder, "mode": ...}}, with a
    # null/empty value releasing -- the same shape positions uses, because a
    # body is in exactly one container at a time.
    merged.setdefault("contained", {})
    # A size change releases containment for the same reason it breaks a hold:
    # someone restored to full height is not still in the coat pocket. Runs
    # BEFORE this beat's own containment declarations, so a Director that
    # re-declares the arrangement as the thing it now is keeps it -- the same
    # ordering the contact cancellation needs, and for the same reason.
    containment_broken_by_scale_change(merged, previous_scales)
    incoming_contained = diff.get("containment")
    if isinstance(incoming_contained, dict):
        for subject, raw in incoming_contained.items():
            label = str(subject or "").strip()
            if not label:
                continue
            record = _clean_containment(raw, label) if raw else None
            if record is None:
                # Released: out of the pocket, off the shoulder, out of the jar.
                for key in [k for k in merged["contained"]
                            if str(k).strip().casefold() == label.casefold()]:
                    merged["contained"].pop(key, None)
            else:
                merged["contained"][label] = record
    normalize_scene_containment(merged)
    # Derived LAST among position writes: whatever else this beat did to
    # positions, a carried body ends up where its carrier is.
    derive_contained_positions(merged)

    apply_contact_ops(merged, diff.get("contact_ops"))
    normalize_scene_contacts(merged)

    # Bodily condition, last: air depends on whether the doorway ended the beat
    # sealed, which the dock-edge rewrite above has only just settled. Entirely
    # skipped unless something has written a vitals table -- absence is the
    # off switch, so a story without survival tracking never touches this.
    incoming_vitals = diff.get("vitals")
    if incoming_vitals or merged.get("vitals"):
        from survival import apply_vitals_diff, tick_vitals
        apply_vitals_diff(merged, incoming_vitals)
        elapsed = 0
        time_block = diff.get("time")
        if isinstance(time_block, dict):
            elapsed = time_block.get("duration_seconds") or 0
        tick_vitals(
            merged, elapsed,
            asleep=[n for n, r in (merged.get("contained") or {}).items()
                    if isinstance(r, dict) and r.get("mode") == "asleep"],
        )
    return merged

def normalize_room_id(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")

def would_create_containment_cycle(placements: dict, subject_id: str, destination_id: str) -> bool:
    current = destination_id
    visited = set()
    while current:
        if current == subject_id:
            return True
        if current in visited:
            return True
        visited.add(current)
        placement = placements.get(current) or {}
        current = placement.get("container_id")
    return False

def validate_operations(scene: dict, operations: list) -> list:
    """Validate world mutation operations before atomic commit."""
    known_ids = set((scene.get("entities") or {}).keys())
    known_ids.update((scene.get("rooms") or {}).keys())
    created_ids = set()
    errors = []

    for operation in operations:
        op = operation.get("op")
        if op == "create_entity":
            entity = operation.get("entity") or {}
            entity_id = str(entity.get("entity_id") or "")
            if not entity_id:
                errors.append("Created entity has no entity_id")
            elif entity_id in known_ids or entity_id in created_ids:
                errors.append(f"Duplicate entity ID: {entity_id}")
            else:
                created_ids.add(entity_id)
        elif op == "move_entity":
            entity_id = operation.get("entity_id")
            destination_id = operation.get("destination_id")
            if entity_id not in known_ids | created_ids:
                errors.append(f"Unknown moved entity: {entity_id}")
            if destination_id not in known_ids | created_ids:
                errors.append(f"Unknown movement destination: {destination_id}")
            if entity_id == destination_id:
                errors.append("An entity cannot contain itself")
    return errors
