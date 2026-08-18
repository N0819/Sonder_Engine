# spatial.py
"""Spatial reasoning with entity-aware scene merging and containment validation."""

import copy
import hashlib
import re
from collections import defaultdict
from typing import Optional

from schemas import NON_ENTITY_FIELD_KEYS, is_derived_entity_name
from spatial_orientation import (
    _LEFT_SECTORS,
    _REL_SECTORS,
    _RIGHT_SECTORS,
    lateral_of,
    normalize_bearing,
    normalize_scene_bearings,
    normalize_vertical,
    opposite_bearing,
    opposite_vertical,
    relative_bearing,
    travel_bearing,
)


from spatial_identity import (
    _ci_get, _entity_named, _live_subject_spellings, _position_of,
    _SUBJECT_KEYED, canonical_subject, canonical_subject_map,
    is_derived_room_name, normalize_room_id, normalize_scene_subjects,
    room_of, same_subject,
)


from spatial_barriers import (
    _AMBIENT_BARRIERS, _barrier_against_its_own_name, _BARRIER_ALIASES,
    _BARRIER_CLOSED_FORM, _BARRIER_CLOSED_QUALIFIERS, _barrier_exact,
    _BARRIER_OPEN_FORM, _BARRIER_OPEN_QUALIFIERS, _BARRIER_SEAL_QUALIFIERS,
    _BARRIER_SEALED_FORM, _OPENING_WORDS, _PASSABLE_BARRIERS, _SCENT_BARRIERS,
    _SIGHT_BARRIERS, _VALID_BARRIERS, normalize_barrier,
    normalize_scene_barriers, unresolved_barrier_words,
)


from spatial_transit import (
    _closed_enclosure_barrier, _entity_exterior_room, _is_body_entity,
    _link_state, _open_enclosure_barrier, _TRANSIT_CLOSED_PHASES,
    _transit_state, ambient_scope, apply_transit_dock_edges,
    CONTAINER_ENCLOSURES, containment_chain, infer_body_enclosures,
)


from spatial_containment import (
    _body_interior_holder, _clean_containment, _hiding_holders,
    _innermost_hiding_holder, _MAX_CONTAINED, _MAX_SCALE, _MAX_SCALES,
    _MIN_SCALE, _NEVER_STATIONED_KINDS, _OPEN_CONTAINMENT_MODES,
    _SCALE_CONTACT_BREAK, _scale_phrase, _shares_enclosure, _SIZE_TIERS,
    carrier_chain, clamp_scale, container_of,
    containment_broken_by_scale_change, containment_conceals,
    containment_facts, containment_hides, CONTAINMENT_MODES, contents_of,
    derive_contained_positions, hiding_holders_of,
    normalize_scene_containment, normalize_scene_scales, scale_of,
    scale_ratio, size_facts, size_relation, size_tier,
    would_create_containment_cycle,
)


from spatial_contacts import (
    _CAVITY_GRIP_MANNERS, _clean_contact, _contact_key,
    _CONTACT_MOMENTARY_STALE_BEATS, _contact_motion_from_text,
    _contact_ops_are_evidence, _CONTACT_RESIDUE_VERB, _CONTACT_STALE_BEATS,
    _CONTACT_STATE_VERBS, _contact_text, _contained_inversion, _displaces,
    _ENCLOSING_PART_CAVITY, _ENVELOPMENT_MANNERS, _flip,
    _INTERIOR_MOVING_MANNERS, _is_anatomical_part, _LATERAL_QUALIFIERS,
    _MAX_CONTACT_DETAIL, _MAX_CONTACT_PART, _MAX_CONTACTS, _mirror_key,
    _MOMENTARY_SET, _NON_ANATOMICAL_PART_WORDS, _normalize_contact_motion,
    _normalize_contact_relation, _part_identity, _part_is_plural,
    _same_appendage, _same_region, _SENSATION_FORMS, _SINGULAR_S_PARTS,
    _STRICT_CAVITY_KINDS, apply_contact_ops, canonical_region,
    CONTACT_INTERIOR_MANNERS, contact_is_momentary, contact_manner_kind,
    CONTACT_MANNERS, CONTACT_MOMENTARY_MANNERS, contact_motion,
    CONTACT_MOVING_MANNERS, contact_relation, contacts_broken_by_scale_change,
    contacts_of, normalize_scene_contacts, owned_region, same_owned_region,
)


from spatial_contact_migration import (
    _CONTACT_KEY_MANNERS, _CONTACT_PROXIMITIES, _DIRECTION_AFTER_VERB,
    _drop_contradicted_state, _lift_valued_contact, _manner_from_fragment,
    _part_from_key, _PROTECTED_STATE_KEYS, _RELATIONAL_STATE_SUFFIXES,
    contacts_from_entity_state,
)


from spatial_substance import (
    _absorb_into_pool, _interior_destination_for_release, _record_region,
    _resolved_substance_add, _same_pool, _SPEECH_CAVITY_INTERIORS,
    _SPEECH_MOUTH_KINDS, _stock_consumed_by, _substance_id,
    _substance_placement, _SUBSTANCE_PLACEMENTS, _substance_target_exists,
    _substance_text, apply_substance_ops, ARTICULATION_SLURRED,
    ARTICULATION_STIFLED, resolve_substance_ops,
    speech_articulation_impediment, substance_event_clause, substances_for,
)


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

    THAT RULE HAD ONE FLAG FOR TWO OPPOSITE SITUATIONS. `concealed` is
    symmetric -- it is true when either body is enclosed and the other is not
    -- so it was answering both "the source is shut inside something" (muffled,
    correct) and "the PERCEIVER is shut inside something" with the same word.
    The second is not a muffling at all. A body sealed inside another is not
    downwind of the thing around them; they are inside it, breathing nothing
    else, and the room beyond that wall does not reach them at all.

    Measured live: a character fully enclosed in another read `muffled` for the
    body around her AND `muffled` for a window across the room -- the enclosure
    and a draught from outside scoring identically. The reported symptom was
    that the scent went faint exactly when it should have drowned out
    everything else, which is precisely what one symmetric flag produces.

    So the direction is now carried explicitly:

      * `inside_source` -- the perceiver is inside this source. Maximal. There
        is no barrier between you and a thing you are within.
      * `enclosed_from_source` -- the perceiver is inside something else, and
        this source is beyond that wall. Nothing arrives.

    Ordered before `concealed`, because both are the more specific claim.
    """
    if rel.get("inside_source"):
        return "full"
    if rel.get("enclosed_from_source"):
        return "none"
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


# ---------------------------------------------------------------- comms
#
# A CHANNEL between places or people, as distinct from a doorway between rooms.
#
# The engine already had a per-LINE rescue: a dialogue entry tagged
# `medium: "comm"` reaches the observer it explicitly names, whatever wall is
# in the way (`composer.line_hear_level`). That covers a phone call to one
# person and nothing else. It cannot express a PA that a whole room hears, a
# channel switched off mid-scene, a ship's intercom reaching four
# compartments, a radio that travels in its owner's pocket, or a broadcast
# that goes one way -- because it is a property of one sentence rather than a
# standing fact about the world.
#
# So channels are world state, in the scene blob beside rooms and positions:
#
#     scene["comms"] = {
#       "cell_pa":  {"name": "Interview cell PA",
#                    "rooms": ["observation", "cell"],
#                    "mode": "broadcast", "source": "observation",
#                    "live": true},
#       "squad_net": {"name": "squad radio",
#                     "carriers": ["Sarah Moon", "Vela"], "live": true},
#       "her_phone": {"name": "phone call",
#                     "carriers": ["Sarah Moon", "Ito"],
#                     "private": true, "live": true},
#     }
#
# ENDPOINTS ARE ROOMS **OR** BODIES, which is the difference between an
# intercom and a walkie-talkie. A fixed installation names `rooms`; a handset,
# radio or phone names `carriers`, and its endpoint is wherever that body is
# standing NOW -- resolved at question time from `positions`, so the channel
# travels in the pocket it is actually in.
#
# Four properties, each earned:
#
# * **It carries VOICE and nothing else.** Not sight, not scent, not the room's
#   own noise. A speaker in the ceiling is not a window. Hearing someone over a
#   channel must never imply they are present, which is why the percept records
#   which channel carried it -- a mind that cannot tell a voice on a radio from
#   a voice at its shoulder has been handed a fact it has no channel for.
# * **`live` is the switch, and it is a fact about the world.** A radio nobody
#   keyed carries nothing; closing a channel mid-scene is an act with
#   consequences, which is the whole reason this is state and not a per-line
#   flag.
# * **`broadcast` is genuinely one-way.** The observation room talks to the
#   cell; the cell does not answer. This is the asymmetry `_VALID_BARRIERS`
#   refuses for doorways -- a barrier belongs to the doorway, not to the side
#   you stand on -- and it is right HERE, because a transmitter and a receiver
#   are different equipment.
# * **`private` decides who in the room hears it.** A handset held to an ear
#   reaches its carrier alone; the same handset on speaker fills the room. Both
#   are ordinary, and the difference is the entire question of whether the man
#   beside you learns what you were just told.

COMMS_MODES = ("duplex", "broadcast")


def _comms_carrier_room(scene, name):
    """Where a carrier is standing now, or None."""
    positions = (scene or {}).get("positions") or {}
    return _ci_get(positions, str(name or "")) if name else None


def _clean_comms_channel(raw, rooms=None):
    """One channel, or None when it names nothing usable.

    A channel needs two endpoints to be a channel; `rooms` and `carriers` are
    counted together toward that, because a base station talking to one field
    radio is the ordinary shape and neither half alone is two.

    `rooms=None` means "do not check the room ids yet", and that is what the
    APPLIER passes. Checking them there would make this channel's result
    depend on whether the beat's room changes had already been merged -- an
    ordering coupling between two delegated channels, which
    `test_diff_application_is_order_independent_by_construction` exists to
    forbid. So the applier only records what the beat said, and
    `normalize_scene_comms` -- which runs once rooms have settled -- does
    every prune. Same end state, no order to get wrong.
    """
    if not isinstance(raw, dict):
        return None
    served = []
    for room_id in raw.get("rooms") or []:
        room_id = str(room_id or "").strip()
        # A channel to a room that no longer exists is not a channel: pruned
        # rather than kept, so a retired compartment cannot keep carrying
        # voices somewhere nobody can stand.
        if not room_id or room_id in served:
            continue
        if rooms is None or room_id in rooms:
            served.append(room_id)
    carriers = []
    for name in raw.get("carriers") or []:
        name = " ".join(str(name or "").split())[:80]
        if name and name not in carriers:
            carriers.append(name)
    if len(served) + len(carriers) < 2:
        return None
    mode = str(raw.get("mode") or "duplex").strip().lower()
    if mode not in COMMS_MODES:
        mode = "duplex"
    source = " ".join(str(raw.get("source") or "").split())[:80]
    if mode == "broadcast" and source not in served and source not in carriers:
        # A broadcast with no transmitter among its own endpoints cannot say
        # which way it points, and guessing the direction of a one-way channel
        # is exactly what would put a voice somewhere it never went.
        mode, source = "duplex", ""
    return {
        "name": " ".join(str(raw.get("name") or "").split())[:120],
        "rooms": served,
        "carriers": carriers,
        "mode": mode,
        "source": source if mode == "broadcast" else "",
        "private": bool(raw.get("private", False)),
        "live": bool(raw.get("live", True)),
    }


def normalize_scene_comms(scene: dict) -> dict:
    """Drop channels that no longer join two endpoints."""
    channels = scene.get("comms")
    if not isinstance(channels, dict):
        scene["comms"] = {}
        return scene
    rooms = scene.get("rooms") or {}
    cleaned = {}
    for channel_id, raw in channels.items():
        channel = _clean_comms_channel(raw, rooms)
        if channel is not None:
            cleaned[str(channel_id)] = channel
    scene["comms"] = cleaned
    return scene


def apply_comms_ops(scene: dict, ops) -> dict:
    """Create, open, close or remove channels.

    `op` is one of set | open | close | remove. `set` is a COMPLETE
    replacement snapshot of one channel, the rule poses already follow: a
    partial update to a thing whose whole point is which endpoints it joins
    would let a channel keep serving somebody the beat just cut off.
    """
    if not isinstance(ops, list):
        return scene
    channels = scene.get("comms")
    if not isinstance(channels, dict):
        channels = {}
        scene["comms"] = channels
    for raw in ops:
        if not isinstance(raw, dict):
            continue
        channel_id = str(raw.get("id") or raw.get("channel") or "").strip()
        if not channel_id:
            continue
        op = str(raw.get("op") or "set").strip().lower()
        if op == "remove":
            channels.pop(channel_id, None)
            continue
        if op in ("open", "close"):
            existing = channels.get(channel_id)
            if isinstance(existing, dict):
                existing["live"] = (op == "open")
            continue
        channel = _clean_comms_channel(raw)
        if channel is not None:
            channels[channel_id] = channel
    return scene


def _comms_transmits(scene, channel, room, name):
    """May this speaker put a voice ONTO the channel."""
    carriers = channel.get("carriers") or []
    on_it = (room and room in (channel.get("rooms") or [])) or (
        name and any(str(name).casefold() == c.casefold() for c in carriers))
    if not on_it:
        return False
    if channel.get("mode") != "broadcast":
        return True
    source = str(channel.get("source") or "")
    return (source == room) or bool(
        name and source.casefold() == str(name).casefold())


def _comms_delivers(scene, channel, room, name):
    """Does this observer hear what comes OFF the channel.

    A private channel reaches its carriers and nobody else -- an earpiece, a
    handset at an ear. A channel that is not private plays out loud, so anyone
    in the carrier's room hears it too, which is the difference between a phone
    call and the same call on speaker.
    """
    carriers = channel.get("carriers") or []
    if name and any(str(name).casefold() == c.casefold() for c in carriers):
        return True
    if channel.get("private"):
        return False
    if room and room in (channel.get("rooms") or []):
        return True
    return bool(room) and any(
        _comms_carrier_room(scene, carrier) == room for carrier in carriers)


def comms_link(scene, speaker_room, observer_room, *,
               speaker_name=None, observer_name=None):
    """The live channel carrying a voice from speaker to observer, or None.

    Directional: a broadcast reaches its receivers and hears nothing back, so
    the same question asked the other way round answers no.
    """
    channels = (scene or {}).get("comms")
    if not isinstance(channels, dict):
        return None
    speaker_room = str(speaker_room) if speaker_room else None
    observer_room = str(observer_room) if observer_room else None
    if speaker_room and observer_room and speaker_room == observer_room \
            and not speaker_name:
        return None
    for channel_id, channel in channels.items():
        if not isinstance(channel, dict) or not channel.get("live"):
            continue
        if not _comms_transmits(scene, channel, speaker_room, speaker_name):
            continue
        if not _comms_delivers(scene, channel, observer_room, observer_name):
            continue
        # A channel exists to reach somewhere a voice does not already go. Two
        # people in one room hear each other directly, and saying they heard it
        # "over the radio" would put a device between them that the beat does
        # not need -- and would tell a mind its neighbour was elsewhere.
        if speaker_room and observer_room and speaker_room == observer_room:
            continue
        return {"id": str(channel_id), **channel}
    return None


def comms_between(scene: dict, from_room, to_room):
    """Room-to-room convenience: is any voice route open at all."""
    return comms_link(scene, from_room, to_room)


def comms_reach(scene: dict, from_room, speaker_name=None):
    """Every room a voice raised in `from_room` reaches over a live channel."""
    reached = {}
    if not isinstance((scene or {}).get("comms"), dict):
        return reached
    for room_id in (scene.get("rooms") or {}):
        channel = comms_link(scene, from_room, room_id,
                             speaker_name=speaker_name)
        if channel is not None:
            reached[str(room_id)] = channel
    return reached


def can_perceive_onset(scene: dict, from_room, to_room) -> bool:
    """Could anything of a beat in `from_room` reach someone in `to_room`.

    DERIVED from the channels, never a list of barrier names. The list it
    replaces was written once and then drifted from the vocabulary it was
    quoting: it admitted `wall` -- through which nothing whatever is perceived
    -- and excluded `bars`, through which sight AND full speech cross, and
    `window`, through which sight crosses. So a character behind glass could
    not react to what they were plainly watching, while one behind a solid
    wall could react to what they could not possibly know about. Measured
    against the real tables the day it was found: 4 of 9 barriers classified
    wrong, in both directions.

    Probed at ORDINARY speaking volume, not at a shout. A shout carries a
    fragment through absolutely everything the table has -- a solid wall, and
    `separated`, which is what two rooms with no edge between them report. So
    a shout probe answers True for every pair of rooms in the scene, which
    turns this gate into "everyone" and plans a character step per cast member
    per beat. Sight is checked outright because sight does not have volumes.

    What remains is genuinely fail-open for the case that matters: anything a
    body could see, or hear said at a normal voice, or be told over a live
    channel. A gate too tight here is invisible -- the character simply says
    nothing and reads as incurious -- so the tie goes to letting them answer.
    """
    if not from_room or not to_room:
        return False
    if str(from_room) == str(to_room):
        return True
    rel = spatial_rel(scene, from_room, to_room)
    if rel.get("same_room"):
        return True
    if sight_level(rel) != "none":
        return True
    if hear_level(rel, "normal") != "none":
        return True
    # A live channel is a channel: someone on the other end of an open
    # intercom can hear the beat, whatever the wall between the rooms is.
    return comms_between(scene, from_room, to_room) is not None


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


def spatial_rel_between(
    scene: dict,
    observer: str,
    target: str,
    observer_room: Optional[str] = None,
    target_room: Optional[str] = None,
) -> dict:
    """`spatial_rel` for two BODIES rather than two rooms.

    Identical to the room-level form except that it carries whatever is true
    of these two specifically: whether the target is still part-way through a
    boundary the observer is standing behind, and the three enclosure
    directions (`inside_source` / `enclosed_from_source` / `source_enclosed`)
    that `hear_level` and `scent_level` grade by. This is THE relation builder
    for any body-to-body channel question -- for a long time it had no
    production caller at all, so every enclosure guard downstream was a guard
    that could not fire: a voice sealed inside a body reached the whole room
    at full clarity, and an enclosed perceiver heard the room it was sealed
    away from.

    `observer_room` / `target_room` let a caller that has already resolved a
    position uid/alias-tolerantly (or that carries a declared source room)
    keep that resolution; absent, `room_of` answers.
    """
    o_room = observer_room if observer_room else room_of(scene, observer)
    t_room = target_room if target_room else room_of(scene, target)
    rel = dict(spatial_rel(scene, o_room, t_room))
    if crossing_visible_from(scene, o_room, target):
        rel["crossing"] = True
    holder = _body_interior_holder(scene, observer)
    if holder and same_subject(scene, holder, target):
        rel["inside_source"] = True
    elif holder and not same_subject(scene, observer, target) \
            and not _shares_enclosure(scene, holder, target):
        # Enclosed, and this source is NEITHER the enclosure NOR in it. The
        # mass of a body is between them, so this is the opposite relation to
        # `inside_source` and needs its own name: everything outside is shut
        # out by the same wall that makes the enclosure itself overwhelming.
        #
        # Two exclusions, and both are the kind that would have been found
        # fifty beats later as "the character has gone strange". A perceiver is
        # never sealed away from THEMSELVES -- their own body is the one thing
        # no enclosure can put a wall in front of. And two bodies inside the
        # same enclosure are in the same place: they see, hear and smell each
        # other normally, which is the rule `containment_conceals` already
        # states by comparing innermost holders.
        rel["enclosed_from_source"] = True
    # A carried body's position derives to its carrier's, so a body enclosed in
    # something standing right here reads as `same_room` -- which answers sight
    # before barriers or light are consulted at all.
    if containment_conceals(scene, observer, target):
        rel["concealed"] = True
    # The third direction, and the one the other two hid. `inside_source` is
    # the perceiver inside the source; `enclosed_from_source` is the perceiver
    # inside something else. This is the SOURCE sealed inside something the
    # perceiver is outside of -- a voice trying to get out through a body's
    # mass. `hear_level` used to be told this was handled by the barrier rules,
    # and for an interior ROOM it was, because the two sides sat in different
    # rooms with a wall between them. Expressed as a containment ledger the
    # position derives to the carrier's own room, so there is no barrier left
    # to muffle anything and an enclosed body's cries reached the body around
    # them at full, unattenuated clarity.
    if not rel.get("inside_source") \
            and not same_subject(scene, observer, target):
        # A BODY's mass specifically, not any enclosure: opaque is not
        # soundproof, and a crate must stay a thing you can be heard through.
        target_holder = _body_interior_holder(scene, target)
        if target_holder and not _shares_enclosure(
                scene, _body_interior_holder(scene, observer), target):
            rel["source_enclosed"] = True
    return rel


_SIGHT_ORDER = {"none": 0, "shapes": 1, "full": 2}


def _weaker_sight(a: str, b: str) -> str:
    """The dimmer of two sight grades -- caps only ever subtract."""
    return a if _SIGHT_ORDER.get(a, 2) <= _SIGHT_ORDER.get(b, 2) else b


# How many 45-degree steps an egocentric sector sits from dead ahead.
_SECTOR_STEPS = {"ahead": 0, "ahead_left": 1, "ahead_right": 1,
                 "left": 2, "right": 2,
                 "behind_left": 3, "behind_right": 3, "behind": 4}


def _opening_view_cap(scene: dict, room_id, body: str, other_room) -> str:
    """S2a: how much of `body`, standing in `room_id`, the view through this
    room's opening to/from `other_room` can carry: full | shapes | none.

    Sight through an opening used to be whole-room binary -- a body pressed
    against the wall beside the doorframe was fully seen from the next room,
    the one leak-shaped over-grant in the FOV model (330 live cross-room pairs
    sit across a sight-passing barrier). The cone is derived entirely from
    data the scene already persists; where nothing supports an answer the cap
    is `full`, i.e. exactly today's behaviour.

    Geometry, at 8-way room grain: the opening sits on the wall at the edge's
    bearing from this room's centre, and a viewer on the other side sees the
    slice of the room on the FAR side of that opening -- the strip from the
    doorway through the centre to the opposite wall. So a body is in the cone
    iff its anchor bearing is within one sector of the direction pointing
    AWAY from the opening (`opposite_bearing` of this room's edge bearing),
    OR it stands at this very edge's door pseudo-anchor, OR it is still
    visibly crossing this edge. A body at a bearing NEAR the door wall but at
    a different anchor is precisely "beside the doorframe" -- the place a
    doorway does not show -- and caps to `none`. (Design note 07 words the
    cone as `opposite_bearing(d)` with d taken from the far side, which is
    this same set; read from this room's own edge the axis is the opposite
    bearing.)

    Placement unknown: fall back by room size -- tiny/small has no off-axis
    corner worth modelling (always in cone), medium keeps today's fail-open,
    large+ caps at `shapes` (through a door you can tell a big room is
    occupied, not read a face across it). The same test gates the OBSERVER's
    side, called with both orderings: someone off-axis beside their own
    doorframe cannot see through the opening either. Pure subtraction: every
    failure mode of the approximation can only withhold, never grant.
    """
    rec = crossing_of(scene, body)
    if rec and {rec.get("from"), rec.get("to")} == {room_id, other_room}:
        return "full"
    at = effective_station(scene, body).get("at")
    if at and at == door_anchor_id(other_room):
        return "full"
    size = effective_room_size(scene, room_id)
    if size in ("tiny", "small"):
        return "full"
    bearing = _anchor_dir(scene, room_id, at) if at else None
    edge_bearing = travel_bearing(scene, room_id, other_room)
    if bearing and edge_bearing:
        away = opposite_bearing(edge_bearing)
        steps = _SECTOR_STEPS.get(relative_bearing(away, bearing))
        if steps is not None:
            return "full" if steps <= 1 else "none"
    if size in ("large", "huge", "vast"):
        return "shapes"
    return "full"


def visual_level_between(scene: dict, observer: str, target: str) -> str:
    """Graded sight from one BODY to another, accounting for local light.

    The room-level form cannot know that the target is standing in a torch's
    pool while the observer is not -- and that difference is exactly what a
    carried light is for.

    Cross-room sight through an opening is additionally capped by the
    opening's view-cone (`_opening_view_cap`, S2a) on BOTH sides, and by an
    authored far/remote edge distance (a figure across a courtyard is
    `shapes`, not a readable face). Both caps default to today's behaviour
    exactly where the data is absent.
    """
    o_room = room_of(scene, observer)
    t_room = room_of(scene, target)
    rel = spatial_rel(scene, o_room, t_room)
    crossing = crossing_visible_from(scene, o_room, target)
    if containment_conceals(scene, observer, target):
        return "shapes" if crossing else "none"
    if not _sight_line(rel):
        # Still going through: a shape in the doorway, not yet gone.
        return "shapes" if crossing else "none"
    # You see what is LIT, so the light that matters is the light on the thing
    # being looked at.
    level = _LIGHT_SIGHT.get(light_at(scene, target), "full")
    # DIM IS A RENDERING FACT UP CLOSE, AN ADMISSION FACT AT RANGE (design
    # note 18). The light verdict used to apply FLAT -- distance could only
    # ever weaken it -- so two bodies in continuous contact in a dim room saw
    # each other as silhouettes (measured live: kneeling over a body, both
    # hands on it, every region concealed by "vantage"). The firewall's own
    # rule decides the fix: a mind may know anything it has a channel to, and
    # an observer with hands on a body at arm's reach has one. Lifted ONLY on
    # positive measurements -- a standing contact between the pair, or a
    # station-measured within_reach -- never on proximity_rel's "near", which
    # is the documented no-station-data fallback and would un-dim every
    # ordinary room. Dark is deliberately NOT lifted: sight fails and the
    # touch channel already delivers what closeness in darkness gives;
    # a carried light beside its holder is light_at's business, not this.
    if level == "shapes" and rel.get("same_room") \
            and _measured_intimacy(scene, observer, target):
        level = "full"
    if not rel.get("same_room"):
        cap = _weaker_sight(
            _opening_view_cap(scene, t_room, target, o_room),
            _opening_view_cap(scene, o_room, observer, t_room),
        )
        if rel.get("distance") in ("far", "remote"):
            cap = _weaker_sight(cap, "shapes")
        level = _weaker_sight(level, cap)
    if crossing and level == "none":
        return "shapes"
    return level


def _measured_intimacy(scene: dict, observer: str, target: str) -> bool:
    """Is this pair's closeness a MEASUREMENT the engine holds?

    The evidence set is closed on purpose (design note 18): a standing
    contact between the two (either direction, `same_subject`-matched -- the
    strongest closeness fact the ledger records), or a station-measured
    `within_reach`. `proximity_rel`'s "near" is deliberately absent: it is
    returned both as a reading and as the no-station-data fallback, and a
    gate that loosens on a fallback would un-dim every ordinary room.
    """
    for contact in contacts_of(scene, observer):
        pair = (contact.get("actor"), contact.get("target"))
        if any(same_subject(scene, side, target) for side in pair if side):
            return True
    return proximity_rel(scene, observer, target) == "within_reach"


# Edge `distance` tiers, most intimate first. Measured live (S1d): 86% of
# edges author a distance, in 29 surface forms -- `3m`, `20m`, `1 step`, bare
# numbers, `close`, `immediate` -- while the ONLY value any code consumed
# (`remote`, hear_level's dead-drop branch) appeared zero times. The exact
# inverse of the stations failure: data everyone writes and nothing can read.
# This normalizer is the read-side fix, mirroring normalize_barrier: applied
# at spatial_rel's one edge-read site so every consumer inherits it.
DISTANCE_TIERS = ("adjacent", "near", "far", "remote")

_DISTANCE_ALIASES = {
    "adjacent": "adjacent", "close": "adjacent", "immediate": "adjacent",
    "touching": "adjacent", "beside": "adjacent", "short": "adjacent",
    "step": "adjacent", "steps": "adjacent", "same": "adjacent",
    "near": "near", "nearby": "near", "mid": "near", "middle": "near",
    "moderate": "near", "medium": "near",
    "far": "far", "long": "far", "distant": "far",
    "remote": "remote",
}

# Rough meters-per-unit for the metric/imperial/stride forms the corpus
# actually writes. A bare number is read as meters -- `10` and `10m` appear
# side by side live and plainly mean the same thing.
_DISTANCE_UNIT_METERS = {
    "m": 1.0, "meter": 1.0, "meters": 1.0, "metre": 1.0, "metres": 1.0,
    "km": 1000.0, "kilometer": 1000.0, "kilometers": 1000.0,
    "ft": 0.3048, "foot": 0.3048, "feet": 0.3048,
    "yd": 0.9144, "yard": 0.9144, "yards": 0.9144,
    "mi": 1609.0, "mile": 1609.0, "miles": 1609.0,
    "step": 0.75, "pace": 0.75, "paces": 0.75, "stride": 0.75, "strides": 0.75,
}


def normalize_edge_distance(value) -> str:
    """Collapse an authored edge `distance` to one of DISTANCE_TIERS.

    Word aliases and numeric/metric parsing (<=5m adjacent, <=20m near,
    <=75m far, beyond remote -- a `200 m` gallery edge is a genuinely remote
    edge that used to read as `near` by raw passthrough). Absent or
    unparseable answers `near`, which is exactly the default every consumer
    already assumed -- the default can never masquerade as a measurement
    because only authored values can reach the other three tiers.
    """
    raw = str(value if value is not None else "").strip().casefold()
    if not raw:
        return "near"
    if raw in _DISTANCE_ALIASES:
        return _DISTANCE_ALIASES[raw]
    matched = re.match(r"^~?\s*(\d+(?:\.\d+)?)\s*([a-z]+)?\.?$", raw)
    if not matched:
        return "near"
    scale = _DISTANCE_UNIT_METERS.get(matched.group(2) or "m")
    if scale is None:
        # An unrecognized unit is not evidence of anything; refuse to guess.
        return "near"
    meters = float(matched.group(1)) * scale
    if meters <= 5:
        return "adjacent"
    if meters <= 20:
        return "near"
    if meters <= 75:
        return "far"
    return "remote"


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

    for index, (source, target) in enumerate((
        (a_room, b_room),
        (b_room, a_room),
    )):
        room = rooms.get(source) or {}

        for edge in room.get("adjacent") or []:
            if not isinstance(edge, dict):
                continue

            if edge.get("to") != target:
                continue

            barrier = normalize_barrier(edge.get("barrier"))
            # `a_room` is the OBSERVER, and this loop reads their own side
            # first -- so the forward direction of a one-way window needs no
            # special case at all. Found on the SECOND pass means we are
            # standing on the far side of one, which is a wall: that is what
            # the back of a two-way mirror is, and it is why the asymmetry can
            # live on a single edge instead of two declarations that
            # contradict each other. Sound and scent land in the same place a
            # wall does either way, so nothing else is lost by saying it this
            # way.
            if index == 1 and barrier == "one_way_window":
                barrier = "wall"

            return {
                "same_room": False,
                "barrier": barrier,
                # What the barrier is made of, carried through so hearing can
                # account for it. Absent means "ordinary", which is the
                # behaviour every existing scene already had.
                "material": edge.get("material") or "",
                "distance": normalize_edge_distance(edge.get("distance")),
                # The light in the room being LOOKED AT: seeing into a dark
                # room from a lit one is still seeing nothing.
                "light": effective_light(scene, b_room),
            }

    return {
        "same_room": False,
        "barrier": "separated",
        "distance": "far",
    }


def passable_neighbors(scene: dict) -> dict:
    """{room_id: {rooms reachable in one step}} over passable edges only.

    Undirected, following the `nearby_rooms` precedent: an open doorway
    declared from either side can be walked through either way. Lifted out of
    `passable_route_exists` when crowds needed the same graph -- a crowd moves
    on the one graph everyone else walks, and §5 of the crowd proposal asks for
    exactly no second pathfinder.
    """
    neighbors: dict[str, set] = {}
    for room_id, room in (scene.get("rooms") or {}).items():
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
    return neighbors


def passable_route_next_step(
    scene: dict,
    from_room: Optional[str],
    to_room: Optional[str],
) -> Optional[str]:
    """The FIRST room on a shortest passable walk from one room to another,
    or None when there is no such walk.

    `passable_route_exists` answers "could they get there"; this answers
    "where does one beat of getting there put them". It exists for travel
    that CONTINUES: a walk the player declared once and did not repeat,
    which the engine advances a leg at a time rather than teleporting at the
    end or abandoning the moment a beat is spent talking.

    Deterministic by construction, which the whole feature depends on --
    reroll and resume-from-stage both require the diff to be a function of
    its inputs, so neighbours are walked in sorted order and a tie between
    two equally short routes always breaks the same way. Same passability
    rule as `passable_route_exists`: only edges already open this beat make
    a path, so a walk does not advance through a door nobody has opened.
    """
    if not from_room or not to_room or from_room == to_room:
        return None
    rooms = scene.get("rooms") or {}
    if to_room not in rooms:
        return None
    neighbors = passable_neighbors(scene)

    # BFS from the destination BACKWARDS: the graph is undirected, so the
    # first neighbour of `from_room` this reaches is a first hop on some
    # shortest route. Searching from the destination means one pass answers
    # the question rather than one pass per candidate hop.
    seen = {to_room}
    frontier = [to_room]
    while frontier:
        nxt = []
        for room_id in frontier:
            for neighbor in sorted(neighbors.get(room_id, ())):
                if neighbor in seen:
                    continue
                if neighbor == from_room:
                    return room_id
                seen.add(neighbor)
                nxt.append(neighbor)
        frontier = sorted(nxt)
    return None


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

    neighbors = passable_neighbors(scene)

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

    # The other side of that same mass. `enclosed_from_source` says the
    # LISTENER is sealed inside something and this source is beyond it, which
    # is the muffling `inside_source` deliberately does not apply -- and which
    # the barrier rules below cannot reach, because a contained body's position
    # derives to its carrier's and so reads `same_room` with the whole room it
    # can no longer hear. Measured live: a body fully enclosed in another was
    # delivered a window latch rattling across the room at full clarity while
    # the enclosure around her was scored as a distant wall. Only a raised
    # voice gets through, and only in pieces.
    if rel.get("enclosed_from_source"):
        return "fragment" if volume in ("loud", "shout") else "none"

    # A voice coming OUT through a body's mass. The comment above once claimed
    # the barrier rules already modelled this, which held only while the two
    # sides sat in different rooms; a containment ledger derives the enclosed
    # body's position to its carrier's, so `same_room` below would hand the
    # room a sealed-away voice at full clarity.
    if rel.get("source_enclosed"):
        return "none" if volume in ("mutter", "whisper") else "fragment"

    if rel.get("same_room"):
        # The two quiet volumes are NOT one tier, and writing them as one
        # ("A whisper (mutter)", as this comment used to read) is how the
        # QUIETEST volume came to be the least attenuated: this branch tested
        # only 'mutter', so 'whisper' fell through to full at any in-room
        # distance. The deterministic floor runs this function with no model
        # in the loop (agents/loops.py's deterministic_micro_perception), so a
        # whispered line was delivered verbatim to a whole room.
        #
        # Whisper is therefore held to mutter's tiers -- and deliberately no
        # tighter YET, though the spec ("whisper: ONLY same-room perceivers in
        # close proximity") would justify silence beyond reach. The blocker is
        # data, not intent: `across` needs both bodies anchored, and measured
        # over the live corpus only 6.7% of bodies carry an anchored station
        # and only 8.6% of multi-occupant rooms have two. So `near` is
        # overwhelmingly a DEFAULT meaning "no station data", not a measured
        # distance -- and reading it as a measurement would turn ~91% of
        # whispers into silence for everyone, deleting authored dialogue to
        # close a leak. Parity with mutter closes the leak (no verbatim
        # content at range) without inventing a distance nobody recorded.
        #
        # Tighten `near` to "none" for whisper once station coverage is real
        # -- that is the point at which the tier becomes evidence.
        if volume in ("mutter", "whisper"):
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


# ---------------------------------------------------------------------------
# S3a/S4a/S4b: directional hearing, the bounded loudness walk, and alarm.
# All derived -- no new fields anywhere.
# ---------------------------------------------------------------------------

# Barriers a loud sound will WALK through for multi-hop propagation. The
# passable set plus `bars` -- a grate is an acoustic hole (hear_level's own
# precedent), even though nobody walks through it.
_SOUND_WALK_BARRIERS = {"open", "open_door", "membrane", "bars"}


def sound_path(scene: dict, from_room, to_room, max_hops: int = 2):
    """Shortest room path (inclusive list of room ids) between two rooms over
    sound-passing edges, at most `max_hops` edges long; None when no such
    path exists. Undirected (an edge declared from either side counts, the
    nearby_rooms precedent) and deterministic (sorted neighbour order)."""
    if not from_room or not to_room or from_room == to_room:
        return None
    neighbors: dict[str, set] = {}
    for rid, room in (scene.get("rooms") or {}).items():
        if not isinstance(room, dict):
            continue
        for edge in room.get("adjacent") or []:
            if not isinstance(edge, dict) or not edge.get("to"):
                continue
            if normalize_barrier(edge.get("barrier")) in _SOUND_WALK_BARRIERS:
                neighbors.setdefault(rid, set()).add(edge["to"])
                neighbors.setdefault(edge["to"], set()).add(rid)
    prev = {from_room: None}
    frontier = [from_room]
    for _ in range(max(0, int(max_hops))):
        next_frontier = []
        for current in frontier:
            for nb in sorted(neighbors.get(current, ())):
                if nb in prev:
                    continue
                prev[nb] = current
                if nb == to_room:
                    path = [nb]
                    while path[-1] is not None:
                        path.append(prev[path[-1]])
                    path.pop()
                    path.reverse()
                    return path
                next_frontier.append(nb)
        frontier = next_frontier
    return None


def sound_walk_level(scene: dict, observer_room, source_room, volume,
                     max_hops: int = 2) -> str:
    """S4a -- DELIBERATE SPEC CHANGE: a bounded multi-hop loudness walk.

    Today non-adjacent is `separated`, so only a shout-fragment survives and
    a gunshot two rooms down an open corridor arrives as nothing -- which
    leaves G2's alarm semantics hollow. This walks the open-edge graph from
    the source, max `max_hops` (default 2), ONLY for raised volumes
    (loud/shout, and G1's `violent` event loudness); normal speech and below
    never propagate (unchanged). Grades the worst barrier on the path,
    shifted one _SOUND_LADDER rung more solid per hop past the first (the
    `_material_shifted_barrier` mechanism), and the result caps at `fragment`
    beyond the first hop -- so "the castle hears every shout" stays
    impossible by construction. Answers "none" for same-room/adjacent pairs:
    those belong to hear_level.
    """
    volume = str(volume or "").strip().casefold()
    if volume not in ("loud", "shout", "violent"):
        return "none"
    if volume == "violent":
        volume = "shout"
    path = sound_path(scene, observer_room, source_room, max_hops=max_hops)
    if not path or len(path) < 3:
        return "none"
    worst = 0
    for a, b in zip(path, path[1:]):
        barrier = spatial_rel(scene, a, b).get("barrier")
        if barrier == "membrane":
            # Not on the ladder by design; acoustically it grades exactly as
            # a closed door does, so that is what the walk shifts.
            barrier = "closed_door"
        if barrier in _SOUND_LADDER:
            worst = max(worst, _SOUND_LADDER.index(barrier))
    hops = len(path) - 1
    shifted = _SOUND_LADDER[min(worst + hops - 1, len(_SOUND_LADDER) - 1)]
    level = hear_level({"same_room": False, "barrier": shifted,
                        "distance": "near"}, volume)
    return "none" if level == "none" else "fragment"


def is_alarming(loudness=None, targets=None, perceiver=None) -> bool:
    """S4b/G2: is this event ALARMING for this perceiver -- derived, never
    authored. Alarming = raised loudness (loud/shout, or G1's `violent`), or
    the event targets the perceiver's own body. An alarming event is the one
    class that bypasses rear-arc/periphery/focus for any perceiver it reaches
    through any channel, and snaps focus toward the bearing it arrived by
    (the doorway the bang came through -- which is also all the information
    the perceiver legitimately has)."""
    if str(loudness or "").strip().casefold() in ("loud", "shout", "violent"):
        return True
    if perceiver and targets:
        me = str(perceiver).strip().casefold()
        return any(str(t or "").strip().casefold() == me for t in targets)
    return False


_COMPASS_WORDS = {"n": "north", "ne": "northeast", "e": "east",
                  "se": "southeast", "s": "south", "sw": "southwest",
                  "w": "west", "nw": "northwest"}

# Reader-facing prose, spliced straight into a perception sentence, so it
# follows the story language like every other engine phrase. Held English
# before, which put "to your left" inside a Japanese view.
def _phrase_table(name):
    from language_runtime import compositor_value
    try:
        return dict(compositor_value(name))
    except Exception:
        return {}


def _sound_barrier_phrases():
    return _phrase_table("sound_barrier_phrases")


def _sector_phrases():
    return _phrase_table("sector_phrases")


#: English compatibility views for tests and audits.
_SOUND_BARRIER_PHRASES = {
    "open": "through the opening", "open_door": "through the doorway",
    "closed_door": "through the door", "window": "through the window",
    "bars": "through the bars", "membrane": "through the curtain",
    "wall": "beyond the wall",
}

_SECTOR_PHRASES = {"ahead": "ahead of you", "behind": "behind you",
                   "left": "to your left", "right": "to your right"}


def _edge_vertical(scene: dict, from_room, to_room) -> Optional[str]:
    """The normalized up/down of the edge between two rooms, read from
    `from_room`'s side (reciprocal edges flip, per normalize_scene_bearings)."""
    rooms = scene.get("rooms") or {}
    for edge in (rooms.get(from_room) or {}).get("adjacent") or []:
        if isinstance(edge, dict) and edge.get("to") == to_room:
            level = normalize_vertical(edge.get("vertical"))
            if level:
                return level
    for edge in (rooms.get(to_room) or {}).get("adjacent") or []:
        if isinstance(edge, dict) and edge.get("to") == from_room:
            level = normalize_vertical(edge.get("vertical"))
            if level:
                return opposite_vertical(level)
    return None


def sound_bearing(scene: dict, observer: str, source: str):
    """S3a: where a heard sound comes from, in the OBSERVER's own frame.
    None when nothing supports an answer -- a bearing is never guessed.

    Same room: the egocentric sector ("behind you", "to your left"), from the
    derivation layer's facing and stations. Adjacent room: the connecting
    edge as seen from the observer's room, rendered against its barrier and
    the observer's facing ("through the doorway to your right"), compass-only
    without a facing ("through the doorway, from the north"). Non-adjacent:
    the FIRST edge of the sound path out of the observer's room -- you hear
    which doorway it came through, not the route.

    Firewall-clean by construction: every field names the observer's OWN
    room's edges (which already survive blind-edge projection with barrier
    and dir but no destination) or a relative sector. The returned dict
    carries no room ids and no room names, so a bearing never names an
    unseen room and grants no layout knowledge the payload did not already
    carry.
    """
    o_room = room_of(scene, observer)
    s_room = room_of(scene, source)
    if not o_room or not s_room:
        return None
    if o_room == s_room:
        label = _sector_label(_relative_sector(scene, observer, source))
        if not label:
            return None
        return {"scope": "same_room", "direction": label,
                "phrase": _sector_phrases().get(label, label)}
    if rooms_adjacent(scene, o_room, s_room):
        next_room, scope = s_room, "adjacent"
    else:
        path = sound_path(scene, o_room, s_room, max_hops=2)
        if not path:
            return None
        next_room, scope = path[1], "beyond"
    barrier = spatial_rel(scene, o_room, next_room).get("barrier")
    bearing = travel_bearing(scene, o_room, next_room)
    vertical = _edge_vertical(scene, o_room, next_room)
    facing = effective_facing(scene, observer)
    direction = _sector_label(relative_bearing(facing, bearing)) \
        if facing and bearing else None
    out = {"scope": scope, "barrier": barrier}
    if bearing:
        out["bearing"] = bearing
    if direction:
        out["direction"] = direction
    if vertical:
        out["vertical"] = vertical
    from language_runtime import compositor_text
    base = (_sound_barrier_phrases().get(barrier)
            or compositor_text("bearing_barrier_fallback"))
    if vertical:
        out["phrase"] = compositor_text(
            "bearing_from_above" if vertical == "up" else "bearing_from_below")
    elif direction:
        # The ORDER of base and sector differs by language, so the join is a
        # template rather than an f-string.
        out["phrase"] = compositor_text(
            "bearing_barrier_sector", base=base,
            sector=_sector_phrases().get(direction, direction))
    elif bearing:
        out["phrase"] = compositor_text(
            "bearing_barrier_compass", base=base,
            compass=_phrase_table("compass_words").get(
                bearing, _COMPASS_WORDS[bearing]))
    else:
        out["phrase"] = base
    return out


# ---------------------------------------------------------------------------
# S3b/G4: the perceiver-senses gate. Cards have carried typed senses
# {channel, acuity, range, notes} forever (character_schema default data) and
# no channel function ever read them -- enhanced hearing existed only in the
# perception prompt. These wrappers describe the PERCEIVER; the grade
# functions above keep describing the CHANNEL, and mixing them would make the
# single-sight-authority migration harder, which is why acuity is applied at
# call sites, never inside hear_level/sight_level/scent_level themselves.
# ---------------------------------------------------------------------------

# The hearing ladder gains one contentless rung: `trace` -- detected,
# direction at best, NO content. The perception prompt's ceiling is explicit:
# "ONLY extraordinary senses explicitly stated may register gross direction
# and noise character -- NEVER words, NEVER identity, NEVER visual detail."
# `fragment` carries words, so a rescue from `none` that landed on `fragment`
# would turn enhanced hearing into a wiretap. Existing callers of hear_level
# never see this value; it exists only downstream of sense_adjusted, and only
# for a perceiver whose card explicitly says extraordinary.
HEARING_LEVELS = ("none", "trace", "fragment", "full")
SCENT_LEVELS = ("none", "muffled", "full")

_SENSE_LADDERS = {
    "hearing": HEARING_LEVELS,
    "sight": SIGHT_LEVELS,
    "scent": SCENT_LEVELS,
}

_SENSE_CHANNEL_ALIASES = {
    "sight": "sight", "vision": "sight", "visual": "sight", "eyes": "sight",
    "eyesight": "sight", "seeing": "sight",
    "hearing": "hearing", "audition": "hearing", "auditory": "hearing",
    "ears": "hearing",
    "scent": "scent", "smell": "scent", "olfaction": "scent",
    "olfactory": "scent", "nose": "scent",
}

# Acuity vocabulary, token-matched so "super enhanced" reads as +2 and
# "hard of hearing" as -1. Anything unrecognized is 0: free text never adds
# capability -- only vocabulary this table explicitly knows can.
_ACUITY_ABSENT = frozenset({
    "absent", "none", "blind", "deaf", "missing", "gone", "lost", "destroyed",
})
_ACUITY_PLUS_TWO = frozenset({
    "extraordinary", "supernatural", "superhuman", "preternatural",
    "uncanny", "extreme", "inhuman", "legendary", "super", "perfect",
})
_ACUITY_PLUS_ONE = frozenset({
    "keen", "acute", "sharp", "enhanced", "heightened", "expert", "superior",
    "exceptional", "excellent", "trained", "practiced", "fine", "high",
    "master", "hawkeyed",
})
_ACUITY_MINUS_ONE = frozenset({
    "dulled", "dull", "impaired", "poor", "weak", "failing", "dim",
    "reduced", "damaged", "hard", "muffled",
})

_RANGE_EXTENDED = frozenset({
    "extended", "long", "far", "extraordinary", "extreme", "vast",
    "unlimited", "universal", "great", "superhuman",
})
_RANGE_REDUCED = frozenset({
    "close", "short", "near", "limited", "local", "touch", "contact",
    "reduced", "adjacent",
})


def _sense_channel(value) -> Optional[str]:
    """Map a card's free-ish channel name onto an engine channel
    (sight | hearing | scent), or None for channels the deterministic floor
    does not model (touch, intuition, ...)."""
    raw = str(value or "").strip().casefold()
    if raw in _SENSE_CHANNEL_ALIASES:
        return _SENSE_CHANNEL_ALIASES[raw]
    for token in re.split(r"[^a-z]+", raw):
        if token in _SENSE_CHANNEL_ALIASES:
            return _SENSE_CHANNEL_ALIASES[token]
    return None


def sense_entry(senses, channel) -> Optional[dict]:
    """The FIRST card entry for this engine channel (author order wins when a
    card lists a channel twice); None when the card says nothing about it --
    which reads as ordinary, byte-identical to today."""
    if not isinstance(senses, list):
        return None
    for sense in senses:
        if isinstance(sense, dict) and _sense_channel(sense.get("channel")) == channel:
            return sense
    return None


def sense_acuity_offset(senses, channel) -> Optional[int]:
    """Integer ladder offset for this perceiver on this channel: -1 dulled,
    0 ordinary, +1 keen, +2 extraordinary. None means the channel is ABSENT
    (blind / deaf) -- a full cut, not a shift. An unlisted channel and an
    empty acuity are both 0: an authoring gap must never blind a body."""
    entry = sense_entry(senses, channel)
    if entry is None:
        return 0
    tokens = {t for t in re.split(
        r"[^a-z]+", str(entry.get("acuity") or "").casefold()) if t}
    if not tokens:
        return 0
    if tokens & _ACUITY_ABSENT and not tokens & (_ACUITY_PLUS_TWO | _ACUITY_PLUS_ONE):
        return None
    if tokens & _ACUITY_PLUS_TWO:
        return 2
    if tokens & _ACUITY_PLUS_ONE:
        return 1
    if tokens & _ACUITY_MINUS_ONE:
        return -1
    return 0


def sense_range_class(senses, channel) -> str:
    """reduced | ordinary | extended -- the card's `range`, which extends the
    ENVELOPE (how far: the multi-hop walk's hop budget) separately from
    acuity (how well). Consumers pass sound_walk_level a bigger max_hops for
    `extended`; `reduced` is carried for completeness and reads as ordinary
    until a consumer wants it."""
    entry = sense_entry(senses, channel)
    if entry is None:
        return "ordinary"
    tokens = {t for t in re.split(
        r"[^a-z]+", str(entry.get("range") or "").casefold()) if t}
    if tokens & _RANGE_EXTENDED:
        return "extended"
    if tokens & _RANGE_REDUCED:
        return "reduced"
    return "ordinary"


def sense_adjusted(level: str, channel: str, senses) -> str:
    """THE senses gate (G4): shift a channel grade by the perceiver's card
    acuity. Ordinary (offset 0), an unlisted channel, or senses=None return
    the level UNCHANGED -- byte-identical behaviour for every existing card.

    Downward: a plain ladder shift (dulled hearing turns a fragment into a
    contentless trace; absent turns everything to none).

    Upward, the one direction that ADDS -- and only when explicitly authored
    on a card -- is semantically capped: a shift never mints content the
    channel did not carry. From `none`, hearing rescues at most `trace`
    (detected, direction at best, no words, no identity) and ONLY at
    extraordinary (+2); sight and scent never leave `none` (a sight line or
    an airtight seal is not something acuity penetrates, and `none` cannot
    say which it was). Above `none`, the shift upgrades clarity of content
    already flowing (fragment->full is an ear pressed to the door), which is
    the ladder semantics the card promises.
    """
    if senses is None:
        return level
    ladder = _SENSE_LADDERS.get(channel)
    if ladder is None or level not in ladder:
        return level
    offset = sense_acuity_offset(senses, channel)
    if offset is None:
        return ladder[0]
    if not offset:
        return level
    if offset > 0 and level == "none":
        return "trace" if (channel == "hearing" and offset >= 2) else "none"
    index = ladder.index(level) + offset
    return ladder[max(0, min(index, len(ladder) - 1))]

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


def spatial_digest(scene, observer, label_for=None):
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
        out = {"room": (rooms.get(rid) or {}).get("name") or rid,
               "barrier": edge.get("barrier")}
        # Which way the doorway itself faces. The buckets are EGOCENTRIC and
        # relative to the last move, so on a first beat -- no movement history
        # -- every exit lands in `unclassified` and carries no direction at
        # all, while `corridor_sight` beside it speaks in compass points. A
        # character holding both frames has to bridge them by guessing, and
        # does: read live from a thinking model's own trace, "two open exits:
        # one to Chamber 0001 (south) and one to Chamber 0100 (south)" -- the
        # same bearing given to two different exits, one of which was east.
        # And a beat later, "east is the intended exit, but it's not detailed
        # in spatial_frame; I need to infer it's ahead or something."
        #
        # The bearing is on the edge already. Omitted when the edge carries
        # none, since a scene without directions has none to give.
        bearing = normalize_bearing(edge.get("dir"))
        if bearing:
            out["bearing"] = bearing
        return out

    out = {}
    for bucket in ("behind", "ahead", "left", "right", "aside",
                   "above", "below", "unclassified"):
        refs = [ref(e) for e in frame.get(bucket) or []]
        if refs:
            out[bucket] = refs
    if frame.get("ahead_entity"):
        # ref is an entity id (look up its name) or already a character name.
        ent = (scene.get("entities") or {}).get(frame["ahead_entity"]) or {}
        ahead = ent.get("name") or frame["ahead_entity"]
        # THE ONE FIELD HERE THAT NAMES A BODY, and the only one that needs an
        # identity decision -- every other bucket names rooms. `positions` and
        # `stations` are keyed by CANONICAL name, so without a gate this hands
        # a character the identity of whoever is in front of them regardless of
        # whether they have any way to know it.
        #
        # Observed live: a character asked the person across the desk for her
        # name twice, in dialogue, and was refused both times, while her view,
        # her memories and her own claims all correctly said "the auditor".
        # `ahead_entity` said "Auditor Dana Rennick" from beat three. By beat
        # eight she used the surname aloud.
        #
        # `label_for` is `agents/common.observer_label_fn` -- perception's own
        # gate and its own `_unknown_actor_label`. Optional because the
        # narrator writes for the player, whose recognition is decided
        # elsewhere, and because this function is also called for internal
        # geometry where nothing is shown to a mind.
        out["ahead_entity"] = label_for(ahead) if label_for else ahead
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
    """Compass bearing of an anchor within its room, or None. Resolves through
    `effective_anchors`, so an implicit door pseudo-anchor bears too."""
    if not anchor_id:
        return None
    a = effective_anchors(scene, room_id).get(anchor_id)
    return normalize_bearing(a.get("dir")) if isinstance(a, dict) else None


# ---------------------------------------------------------------------------
# S1: the read-time derivation layer. Pure functions answering "where in the
# room is this body, which way does it face" from data the scene ALREADY
# persists -- edges, contacts, crossings, focus -- falling back to today's
# behaviour when nothing supports an answer. Nothing here is ever stored: a
# value that is never written needs no commit path, no restore path, no
# archive handling, and can never go stale in a checkpoint. Authored data
# always wins; the derivations are the fallback UNDER it.
# ---------------------------------------------------------------------------

_DOOR_ANCHOR_PREFIX = "door:"


def door_anchor_id(neighbor_room_id) -> str:
    """The id of the implicit pseudo-anchor a room's edge to `neighbor_room_id`
    contributes -- a doorway IS a named feature of the room at a known wall."""
    return f"{_DOOR_ANCHOR_PREFIX}{neighbor_room_id}"


_BARRIER_ANCHOR_DESC = {
    "open": "the opening",
    "open_door": "the open doorway",
    "closed_door": "the doorway",
    "window": "the window",
    "bars": "the bars",
    "membrane": "the curtained way",
    "wall": "the far wall",
}


def effective_anchors(scene: dict, room_id) -> dict:
    """S1a: the room's authored anchors plus one implicit `door:<to>`
    pseudo-anchor per adjacency edge (declared from either side), each
    carrying the edge's bearing when it has one.

    Every beared edge IS an anchor -- a doorway is a feature of the room at a
    known wall -- so the 54 live multi-occupant rooms with zero authored
    anchors gain at least one usable anchor wherever they have a beared edge,
    with zero authoring. Authored anchors always win an id collision; implicit
    ones are marked `implicit: True` and are never written anywhere.
    """
    rooms = scene.get("rooms") or {}
    room = rooms.get(room_id) or {}
    out = {}
    for aid, anchor in (room.get("anchors") or {}).items():
        if isinstance(anchor, dict):
            out[aid] = anchor

    def add(neighbor_id, barrier, bearing, vertical):
        aid = door_anchor_id(neighbor_id)
        if aid in out:
            return
        anchor = {
            "desc": _BARRIER_ANCHOR_DESC.get(normalize_barrier(barrier))
            or "the way through",
            "implicit": True,
        }
        if bearing:
            anchor["dir"] = bearing
        if vertical:
            anchor["vertical"] = vertical
        out[aid] = anchor

    for edge in room.get("adjacent") or []:
        if isinstance(edge, dict) and edge.get("to"):
            add(edge["to"], edge.get("barrier"),
                normalize_bearing(edge.get("dir")),
                normalize_vertical(edge.get("vertical")))
    # An edge declared only from the neighbour's side is still a doorway in
    # THIS room; its bearing and verticality read reciprocally, the same rule
    # travel_bearing already applies.
    for other_id, other in rooms.items():
        if other_id == room_id or not isinstance(other, dict):
            continue
        for edge in other.get("adjacent") or []:
            if isinstance(edge, dict) and edge.get("to") == room_id:
                add(other_id, edge.get("barrier"),
                    opposite_bearing(normalize_bearing(edge.get("dir"))),
                    opposite_vertical(normalize_vertical(edge.get("vertical"))))
    return out


def effective_station(scene: dict, name: str) -> dict:
    """S1b: the station `name` EFFECTIVELY holds, derived at read time.

    Resolution order, authored first:
      1. the authored/persisted station (`scene.stations[name]`) -- unchanged,
         always wins;
      2. contact-derived placement -- a standing contact is physical touch, so
         a partner backed by an anchored room feature seats the body there,
         and a co-located body partner becomes a mutual `near` link (two
         bodies in sustained contact are within reach by definition; the
         contacts ledger is one the Director reliably maintains);
      3. crossing-derived door placement -- a body with a live threshold
         crossing stands at the implicit door-anchor of the edge it entered
         through, and falls back to unplaced the moment the crossing record
         expires, so it can never go stale;
      4. nothing -> callers keep their current defaults.

    Never stored: this is an accessor, not a writer, so it reruns correctly
    under restore by construction. Unknown station keys (e.g. a future
    `cover`) pass through untouched.
    """
    authored = _station(scene, name)
    out = {k: v for k, v in authored.items() if k not in ("at", "near")}
    at = authored.get("at") or None
    near = list(authored.get("near") or [])
    room = room_of(scene, name)
    if room is None:
        out["at"] = at
        out["near"] = near
        return out
    me = str(name or "").strip().casefold()
    positions = scene.get("positions") or {}
    for contact in (scene.get("contacts") or []):
        if not isinstance(contact, dict):
            continue
        pair = (str(contact.get("actor") or "").strip(),
                str(contact.get("target") or "").strip())
        for mine, other in (pair, (pair[1], pair[0])):
            if not other or mine.casefold() != me:
                continue
            anchor = _anchor_for_entity(scene, room, other)
            if anchor:
                if not at:
                    at = anchor
            elif _ci_get(positions, other) == room and not any(
                    str(n).strip().casefold() == other.casefold() for n in near):
                near.append(other)
    if not at:
        rec = crossing_of(scene, name)
        if rec and rec.get("to") == room and rec.get("from") \
                and door_anchor_id(rec["from"]) in effective_anchors(scene, room):
            at = door_anchor_id(rec["from"])
    out["at"] = at
    out["near"] = near
    return out


def effective_facing(scene: dict, name: str) -> Optional[str]:
    """S1c: the bearing `name` is facing, derived at read time.

    `orientation.facing` when set (written by spatial_frames.infer_facing at
    commit -- unchanged, always wins); otherwise the bearing of the current
    focus target or edge, resolvable NOW through the derived anchors and
    stations above. This catches the window between a focus change and the
    next commit, and lifts scenes restored from checkpoints that predate
    infer_facing. Never guessed: no focus, no beared anchor -> None, and
    every egocentric consumer keeps asserting no direction.
    """
    rec = _ci_get(scene.get("orientation") or {}, name) or {}
    facing = normalize_bearing(rec.get("facing"))
    if facing:
        return facing
    focus = rec.get("focus") if isinstance(rec.get("focus"), dict) else None
    ref = focus.get("ref") if focus else None
    room = room_of(scene, name)
    if not ref or not room:
        return None
    if focus.get("kind") == "edge":
        return travel_bearing(scene, room, ref)
    if focus.get("kind") in ("target", "entity"):
        if room_of(scene, ref) != room:
            return None
        t_at = effective_station(scene, ref).get("at")
        if not t_at or t_at == effective_station(scene, name).get("at"):
            # Side by side at the same anchor: its room bearing is not the
            # target's direction from the observer. Never guessed.
            return None
        return _anchor_dir(scene, room, t_at)
    return None


# Rooms whose NAME says "big" even when nobody authored `size`. Deliberately
# blunt and deliberately short: the hint only widens the `near`->`across`
# distinction, fails toward today's behaviour, and an authored size always
# wins. Token-matched, so "hallway" never reads as a hall.
_ROOM_SIZE_HINT_WORDS = frozenset({
    "hall", "ballroom", "cathedral", "warehouse", "hangar", "plaza",
    "arena", "atrium", "concourse", "auditorium", "amphitheater",
    "amphitheatre", "stadium", "gymnasium", "courtyard", "nave", "field",
})


def effective_room_size(scene: dict, room_id) -> str:
    """S1e: the room's authored `size`, else a keyword hint from its
    name/desc/notes (hall, warehouse, plaza... -> `large`), else `medium` --
    the safe default the engine already assumed. Derived-with-default; only
    proximity-grade consumers should read it."""
    room = (scene.get("rooms") or {}).get(room_id) or {}
    size = str(room.get("size") or "").strip().casefold()
    if size:
        return size
    text = " ".join(str(room.get(key) or "") for key in ("name", "desc", "notes"))
    if set(re.split(r"[^a-z]+", text.casefold())) & _ROOM_SIZE_HINT_WORDS:
        return "large"
    return "medium"


def _occupancy(scene: dict) -> dict:
    counts = {}
    for room_id in ((scene or {}).get("positions") or {}).values():
        counts[str(room_id)] = counts.get(str(room_id), 0) + 1
    return counts


def guessed_room_sizes(scene: dict, prev_scene: dict = None) -> list[dict]:
    """G6: a room that just became shared, whose size nobody ever authored.

    Size used to be prose flavour. It is not any more: `proximity_rel` reads
    it to decide whether two people are `across` a room rather than `near`
    it, and S2a's placement-unknown fallback caps sight in a large room at
    `shapes`. An unauthored size is therefore a perception GRADE the engine
    picked for itself, and it picks silently -- 175 of 392 live rooms carry
    no `size`, of which the keyword hint rescues 24 and 151 fall to
    `medium`.

    Two subtractions keep this readable. Only rooms with two or more
    occupants, because a room with nobody in it has no proximity to grade.
    And only the beat the room CROSSES into being shared -- pass
    `prev_scene` and a scene that sits in the same unsized room for two
    hundred beats says so once, not two hundred times. A standing condition
    reported every beat is one the reader learns to skip, which is the
    failure this warning exists to avoid in the first place.

    `derived` says which way the guess went, so "sized `large` by the word
    'hall'" reads differently from "fell to `medium` because nothing said
    otherwise".

    Returns rows, not warnings -- the seam that knows whose warning list to
    write to does the reporting.
    """
    rooms = (scene or {}).get("rooms") or {}
    counts = _occupancy(scene)
    before = _occupancy(prev_scene) if prev_scene is not None else None
    out = []
    for room_id, room in rooms.items():
        if not isinstance(room, dict):
            continue
        if str(room.get("size") or "").strip():
            continue
        occupants = counts.get(str(room_id), 0)
        if occupants < 2:
            continue
        if before is not None and before.get(str(room_id), 0) >= 2 \
                and str(room_id) in ((prev_scene or {}).get("rooms") or {}):
            continue                    # already shared, already reported
        derived = effective_room_size(scene, room_id)
        out.append({
            "room": str(room_id),
            "name": str(room.get("name") or room_id),
            "derived": derived,
            "occupants": occupants,
            "by_keyword": derived == "large",
        })
    return sorted(out, key=lambda r: (-r["occupants"], r["room"]))


def proximity_rel(scene: dict, observer: str, target: str) -> Optional[str]:
    """Within-room proximity tier between two entities: 'within_reach' | 'near'
    | 'across', or None when they are not co-located. within_reach: same anchor,
    or a mutual 'near' station link. across: distinct anchors in a room flagged
    size 'large' OR BIGGER -- 'huge' and 'vast' are equally real scene sizes
    (see _ROOM_COST), and gating on 'large' exactly made the two largest floors
    read as more intimate than a merely large one. Otherwise 'near' -- the safe
    default for an ordinary same-room pair, including when no stations exist.

    Note for callers reasoning about distance: 'near' is returned BOTH as a
    measurement and as that default, and the default dominates (6.7% of live
    bodies carry an anchored station). Do not read 'near' as positive evidence
    of separation -- see hear_level's quiet-volume branch."""
    o_room = room_of(scene, observer)
    t_room = room_of(scene, target)
    if not o_room or o_room != t_room:
        return None
    o_st = effective_station(scene, observer)
    t_st = effective_station(scene, target)
    o_at, t_at = o_st.get("at"), t_st.get("at")

    def _in_near(near, who):
        w = str(who or "").strip().casefold()
        return any(str(n).strip().casefold() == w for n in near or [])

    if (o_at and t_at and o_at == t_at) \
            or _in_near(o_st.get("near"), target) \
            or _in_near(t_st.get("near"), observer):
        return "within_reach"
    size = effective_room_size(scene, o_room)
    if o_at and t_at and o_at != t_at and size in ("large", "huge", "vast"):
        return "across"
    return "near"


def measured_proximity_rel(scene: dict, observer: str, target: str) -> Optional[str]:
    """`proximity_rel`, but only when the answer is a MEASUREMENT.

    `proximity_rel` returns "near" both as a real reading (two anchored
    stations a few steps apart) and as its fallback when no station data
    exists -- and station data is mostly absent (measured live: 6.7% of bodies
    carry an anchored station, 8.6% of multi-occupant rooms have two). A
    delivery gate that treats the fallback as positive evidence of separation
    silences legitimate content wholesale: `hear_level` degrades a same-room
    mutter to a fragment at "near", which is the right answer for a measured
    few-steps gap and the wrong answer for nine rooms in ten where "near" just
    means "no one wrote stations".

    within_reach and across already require station data by construction;
    "near" is passed through only when both parties hold an anchor, and
    otherwise collapses to None -- "unknown", which downgrades nothing.
    """
    tier = proximity_rel(scene, observer, target)
    if tier != "near":
        return tier
    if effective_station(scene, observer).get("at") \
            and effective_station(scene, target).get("at"):
        return tier
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
    facing = effective_facing(scene, observer)
    if not facing:
        return None
    o_at = effective_station(scene, observer).get("at")
    t_at = effective_station(scene, target).get("at")
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
    facing = effective_facing(scene, observer)
    anchors = []
    # EFFECTIVE anchors: the look-around map gains its exits as positioned
    # features -- the doorway to the kitchen is a thing in the room with a
    # side, not only an entry in the exits digest.
    for aid, a in effective_anchors(scene, o_room).items():
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
    that person's anchor direction (see spatial_frames.infer_facing). Reads the
    EFFECTIVE station, so a body just through a doorway, or in contact with an
    anchored feature, bears without any authored station."""
    room = room_of(scene, name)
    if not room:
        return None
    return _anchor_dir(scene, room, effective_station(scene, name).get("at"))


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

    for name in list(stations.keys()):
        st = stations.get(name)
        my_room = _ci_get(positions, name)
        if not isinstance(st, dict) or my_room is None:
            stations.pop(name, None)   # tolerant: a case-variant of a positioned name survives
            continue
        # EFFECTIVE anchors, so a station at an implicit door pseudo-anchor
        # ("door:<to>") survives the merge instead of being blanked as a
        # phantom -- a room change still auto-clears it, because the door
        # anchors of the new room name different neighbours.
        anchors = effective_anchors(scene, my_room)
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


_POSE_FIELDS = ("posture", "support", "relative_to", "relation",
                "constraint", "detail")


def _clean_pose(raw):
    """One body's complete current pose snapshot, or None when empty.

    Values stay open strings: fictional bodies and supports are unbounded.
    Structure separates the body's own posture from what supports it and its
    relation to another body, so "lying", "on the table", "beneath Mara" and
    "pinned" cannot collapse into one stale prose field.
    """
    if not isinstance(raw, dict):
        return None
    pose = {
        field: " ".join(str(raw.get(field) or "").split())[:240]
        for field in _POSE_FIELDS
    }
    return pose if any(pose.values()) else None


def normalize_scene_poses(scene: dict) -> dict:
    """Prune pose relations invalidated by departure or room separation."""
    poses = scene.get("poses")
    if not isinstance(poses, dict):
        scene["poses"] = {}
        return scene
    positions = scene.get("positions") or {}
    stations = scene.get("stations") or {}
    rooms = scene.get("rooms") or {}
    for name in list(poses):
        pose = _clean_pose(poses.get(name))
        my_room = _ci_get(positions, name)
        if pose is None or my_room is None:
            poses.pop(name, None)
            continue
        other = pose.get("relative_to")
        if other:
            # A pose may be relative to a co-located BODY or to a FIXTURE of
            # the body's own room. `support` has always accepted both (see the
            # anchors check below); `relative_to` accepted only bodies, and
            # silently cleared anything else.
            #
            # That asymmetry threw away the only structured record of which way
            # a body had turned. Live (chat 74 turn 57): the Director declared
            # `relative_to: "towel_rack"` for a character who had turned to face
            # the wall, back to the room. `towel_rack` is a real anchor of that
            # room bearing 'ne' -- but it is not a body, so this cleared it, and
            # the only surviving trace was prose in `detail`. `focus` then kept a
            # stale doorway edge from an earlier beat, `infer_facing` pinned the
            # heading to that doorway's 'w', and the adjacent room stayed in
            # full view: the same composed view read "back to the room" and
            # "You see Hinami" a sentence apart.
            #
            # A body turned toward a fixture is exactly as real as a body
            # leaning on one, and the room already says where its fixtures are.
            anchors = effective_anchors(scene, my_room) or {}
            if other not in anchors and _ci_get(positions, other) != my_room:
                pose["relative_to"] = ""
                pose["relation"] = ""
                pose["constraint"] = ""
        support = pose.get("support")
        if support:
            anchors = (rooms.get(my_room) or {}).get("anchors") or {}
            support_is_anchor = support in anchors
            support_room = _ci_get(positions, support)
            if not support_is_anchor and support_room not in (None, my_room):
                pose["support"] = ""
            station = _ci_get(stations, name)
            if support_is_anchor and isinstance(station, dict) \
                    and station.get("at") not in (None, support):
                pose["support"] = ""
        poses[name] = pose
    return scene


def apply_pose_diff(scene: dict, incoming) -> dict:
    """Replace touched pose snapshots; null/empty explicitly clears one."""
    scene.setdefault("poses", {})
    if not isinstance(scene["poses"], dict):
        scene["poses"] = {}
    if not isinstance(incoming, dict):
        return scene
    for name, raw in incoming.items():
        label = str(name or "").strip()
        if not label:
            continue
        for old in [key for key in scene["poses"]
                    if str(key).strip().casefold() == label.casefold()]:
            scene["poses"].pop(old, None)
        pose = _clean_pose(raw)
        if pose is not None:
            scene["poses"][label] = pose
    return scene


def pose_facts(scene: dict, observer: str, visible_names=()) -> list[str]:
    """Authoritative current body arrangements using observer-safe labels."""
    facts = []
    allowed = {str(name) for name in (visible_names or [])} | {str(observer)}
    for name, raw in ((scene or {}).get("poses") or {}).items():
        if not any(same_subject(scene, name, allowed_name)
                   for allowed_name in allowed):
            continue
        pose = _clean_pose(raw)
        if pose is None:
            continue
        is_self = same_subject(scene, name, observer)
        parts = []
        if pose["posture"]:
            parts.append(f"posture: {pose['posture']}")
        if pose["support"]:
            parts.append(f"support: {pose['support']}")
        if pose["relative_to"]:
            other = ("you" if same_subject(
                scene, pose["relative_to"], observer)
                else pose["relative_to"])
            relation = f" ({pose['relation']})" if pose["relation"] else ""
            parts.append(f"relative to {other}{relation}")
        if pose["constraint"]:
            parts.append(f"constraint: {pose['constraint']}")
        if pose["detail"]:
            parts.append(f"detail: {pose['detail']}")
        if parts:
            prefix = "Your current body pose" if is_self \
                else f"{name}'s current body pose"
            facts.append(prefix + " — " + "; ".join(parts) + ".")
    return facts


def _anchor_for_entity(scene: dict, room_id: str, name: str):
    """The anchor id of the room feature `name` refers to, or None.

    Identifier recognition, never prose: a room's `bed` anchor and its `bed`
    entity are the same bed when their ids, names or aliases slugify the same.
    Anything looser would start reading furniture out of sentences.
    """
    anchors = ((scene.get("rooms") or {}).get(room_id) or {}).get("anchors") or {}
    if not isinstance(anchors, dict) or not anchors:
        return None
    slugs = {re.sub(r"[^a-z0-9]", "", str(a).casefold()): a for a in anchors}
    labels = [name]
    for eid, entity in (scene.get("entities") or {}).items():
        if not isinstance(entity, dict):
            continue
        names = [eid, entity.get("name"), *(entity.get("aliases") or [])]
        if any(str(n or "").strip().casefold() == str(name).strip().casefold()
               for n in names):
            labels.extend(n for n in names if n)
            break
    for label in labels:
        hit = slugs.get(re.sub(r"[^a-z0-9]", "", str(label).casefold()))
        if hit:
            return hit
    return None


def derive_scene_stations(scene: dict, explicit=None, fresh_ops=None) -> dict:
    """Fill in within-room position from what the beat already recorded.

    The Director fills `contact_ops` reliably and `stations` essentially never
    -- 147 contact adds in one measured story against zero stations in the
    whole database. But contact IS position at this grain: a hand on the quilt
    is a body at the bed, and two bodies touching are two bodies within reach.
    So the ledger the models do maintain seeds the one they do not.

    Additive and idempotent, and it never argues with a statement. A station
    named in THIS beat's diff is untouchable. An existing `at` is only replaced
    when the contact deriving it was asserted this beat -- this beat's physical
    evidence outranks a stale record, an old contact does not.

    A derived station outlives the contact that produced it, deliberately: a
    hold ends when the Director stops mentioning it, but you do not leave the
    bed by taking your hand off the quilt. Only a room change clears it, which
    `normalize_scene_stations` already does.
    """
    positions = scene.get("positions") or {}
    if not positions:
        return scene
    stated = {str(k).strip().casefold() for k in (explicit or {})}
    fresh = set()
    for raw in fresh_ops or []:
        if not isinstance(raw, dict):
            continue
        if str(raw.get("op") or "add").strip().casefold() != "add":
            continue
        contact = _clean_contact(raw, scene)
        if contact is not None:
            fresh.add(_contact_key(contact))

    stations = scene.setdefault("stations", {})
    if not isinstance(stations, dict):
        stations = scene["stations"] = {}

    for contact in (scene.get("contacts") or []):
        if not isinstance(contact, dict):
            continue
        recent = _contact_key(_clean_contact(contact, scene) or {}) in fresh
        pair = (contact.get("actor"), contact.get("target"))
        for me, other in (pair, tuple(reversed(pair))):
            me, other = str(me or "").strip(), str(other or "").strip()
            room = _ci_get(positions, me)
            if not me or not other or room is None or me.casefold() in stated:
                continue
            # Only bodies get stationed. A bed touched by a hand is furniture
            # that a body is AT, not a guest with a position in the room.
            #
            # Tested by what the thing IS in the room rather than by
            # `_is_body_entity`, which reads `scene.attire` -- a table commit
            # fills AFTER the merge, so on any beat that establishes a scene it
            # is still empty and every body would fail. A room feature is a
            # thing you stand at; a body never is. Kinds are model-written free
            # text ("kitsune", "succubus", "nine-tailed kitsune" all appear
            # live), so the object list is a DENYLIST -- an unrecognised kind
            # is taken for a body, which is the recoverable direction.
            if _anchor_for_entity(scene, room, me) \
                    or str(_entity_named(scene, me).get("kind") or "").strip(
                        ).casefold() in _NEVER_STATIONED_KINDS:
                continue
            station = stations.setdefault(me, {"at": None, "near": []})
            if not isinstance(station, dict):
                continue
            anchor = _anchor_for_entity(scene, room, other)
            if anchor and (recent or not station.get("at")):
                station["at"] = anchor
            elif not anchor and _ci_get(positions, other) == room:
                # Two bodies in contact are within reach of each other, which
                # is what makes a whisper between them arrive whole.
                near = station.setdefault("near", [])
                if isinstance(near, list) and other not in near:
                    near.append(other)

    # Last resort: the body's own `state.position`. The Director has always
    # written the arrangement there as free text -- "seated_on_bed_edge" is the
    # live record, and it was the ONLY thing in the whole engine that knew she
    # was on the bed, read by nothing. This is identifier recognition, not
    # prose parsing: an anchor id of that body's OWN room, matched as a whole
    # word, and only where nothing better has already spoken. A body that
    # merely walked past the bed can be stationed at it by this, which the
    # Director now sees in its payload and can correct -- against a body that
    # has been sitting on one for seventeen beats with nowhere to say so.
    for name, room in list(positions.items()):
        name = str(name or "").strip()
        if not name or name.casefold() in stated:
            continue
        station = stations.get(name)
        if isinstance(station, dict) and station.get("at"):
            continue
        state = _entity_named(scene, name).get("state")
        if not isinstance(state, dict):
            continue
        words = [w for w in re.split(r"[^a-z0-9]+",
                                     str(state.get("position") or "").casefold()) if w]
        if not words:
            continue
        for word in words:
            anchor = _anchor_for_entity(scene, room, word)
            if anchor:
                stations.setdefault(name, {"at": None, "near": []})["at"] = anchor
                break
    return scene


def repair_entity_positions(scene: dict) -> list:
    """A position naming an ENTITY rather than a room is a category error.

    `positions` maps a body to a ROOM. The Director periodically writes an
    entity id there instead -- "she is in Elyndra" is a true sentence and an
    invalid position -- and nothing rejected it, because every spatial query
    resolves an unknown room to the safe-closed default rather than raising.

    Measured live (chat 60): a body enclosed inside another sat at the literal
    string `"elyndra_succubus"` for the rest of the story, a room that does not
    exist. The relation to the body around her came back

        {"same_room": false, "barrier": "separated", "distance": "far"}

    -- the same answer the engine gave for a window across the room. Nothing
    was broken loudly. She was simply nowhere, and every channel read as
    distance, which is exactly what being nowhere looks like from inside a
    ranking function.

    The repair is the reading the Director meant: put the body in the entity's
    own room and record a station AT that entity, which is the engine's
    existing vocabulary for being at a thing rather than in it. Containment is
    NOT inferred here -- `derive_contained_positions` has already run and owns
    that case, and inventing an enclosure from a mistyped position would turn a
    typo into a firewall change. Returns what it repaired, for warnings.
    """
    positions = scene.get("positions")
    rooms = scene.get("rooms") or {}
    if not isinstance(positions, dict) or not isinstance(rooms, dict):
        return []
    repaired = []
    for name, where in list(positions.items()):
        key = str(where or "").strip()
        if not key or key in rooms or _ci_get(rooms, key) is not None:
            continue
        entity = _entity_named(scene, key)
        if not entity:
            continue
        room = _position_of(scene, key)
        if room is None or room == key:
            continue
        positions[name] = room
        stations = scene.setdefault("stations", {})
        if isinstance(stations, dict):
            slot = stations.get(name)
            if not isinstance(slot, dict):
                slot = {"at": None, "near": []}
                stations[name] = slot
            if not slot.get("at"):
                slot["at"] = key
        repaired.append((name, key, room))
    return repaired


def prune_bodiless_positions(scene: dict) -> list:
    """Drop `positions` entries belonging to a bodiless voice.

    A ship's computer, a station PA and a public-address system are not
    standing anywhere -- `scene.is_ubiquitous_entity` calls giving one a room
    a category error, and the Director prompt tells it to declare such a thing
    with NO position. It still happens: measured live, one was created with a
    room in the same breath as a description reading "a voice-activated system
    with no physical body", trailed the player for five beats, and was then
    stranded in the room it was last voiced in for eighty more.

    A stale entry like that is not inert. Every reader that asks where the
    speaker is gets an answer, and the answer is wrong -- the delivery rescue
    in perception is the one that matters, and it is now asked of the entity
    rather than of the position, but nothing was removing the record itself
    and there is no way for an author to. So merge hygiene removes it, the
    same way position changes prune an impossible contact.

    Returns the names dropped, for the caller to report; mutates in place.
    """
    positions = scene.get("positions")
    entities = scene.get("entities")
    if not isinstance(positions, dict) or not isinstance(entities, dict):
        return []
    try:  # lazy: scene.py imports THIS module, so the edge only goes one way
        from scene import ubiquitous_speaker_names
        bodiless = ubiquitous_speaker_names(scene)
    except Exception:
        return []
    if not bodiless:
        return []
    dropped = [key for key in list(positions)
               if str(key).strip().casefold() in bodiless]
    for key in dropped:
        positions.pop(key, None)
    return dropped


def contact_phrase(contact: dict, *, subject_first=True, you=None) -> str:
    """One STANDING contact as a plain clause -- state, never event.

    'Bramwell's hand grips Hinami's waist'. Every consumer of this phrase
    (narrator ground truth via `spatial_facts`, the perception scene payload)
    is asking what is true right now, so a manner naming an ACT renders as the
    touch that act left behind: a contact recorded `kiss` reads "X's lips is
    against Y's forehead", not "X's lips kiss Y's forehead". The act itself is
    delivered from the beat's declared sequence, which is the representation
    that carries WHEN it happened.

    Measured live, before this: a forehead kiss from four beats earlier was
    still rendered in the active present into a perceiver's view, and the
    character answered it as a live advance.

    `you` names the observer this phrase is FOR, when there is one. Their side
    renders in the second person ("your palm presses against her sternum"),
    because handing a perceiver a third-person clause about their own body --
    naming them canonically, in a view that must be written as "you" -- is the
    same objective-state-into-a-subjective-context pattern the engine forbids
    everywhere else, and it invites exactly the person drift it sounds like.
    """
    if not isinstance(contact, dict):
        return ""
    actor = str(contact.get("actor") or "").strip()
    target = str(contact.get("target") or "").strip()
    if not actor or not target:
        return ""
    manner = str(contact.get("manner") or "touch").strip() or "touch"
    actor_part = str(contact.get("actor_part") or "").strip()
    target_part = str(contact.get("target_part") or "").strip()
    target_interior = str(contact.get("target_interior") or "").strip()

    observer = str(you or "").strip().casefold()
    actor_is_you = bool(observer) and actor.casefold() == observer
    target_is_you = bool(observer) and target.casefold() == observer

    def _side(who, part, is_you):
        if is_you:
            return f"your {part}" if part else "you"
        return f"{who}'s {part}" if part else who

    left = _side(actor, actor_part, actor_is_you)
    right = _side(target, target_part, target_is_you)
    relation_kind = contact_relation(contact)
    motion_kind = contact_motion(contact)
    if relation_kind == "interior":
        # Interior topology says the ACTOR PART is within the TARGET. The
        # target_part is the precise endpoint/contact site, not necessarily the
        # structure doing the enclosing. Treating it as the container turned a
        # blade at a shoulder into "inside the shoulder" and a contact at a
        # terminal boundary into "inside the boundary".
        if target_interior:
            container = (f"your {target_interior}" if target_is_you else
                         f"{target}'s {target_interior}")
        else:
            container = "you" if target_is_you else target
        plural = _part_is_plural(actor_part) if actor_part else actor_is_you
        verb = ("move" if plural else "moves") if motion_kind == "moving" \
            else ("remain" if plural else "remains")
        phrase = f"{left} {verb} within {container}"
        if target_part:
            endpoint = f"your {target_part}" if target_is_you \
                else f"{target}'s {target_part}"
            phrase += f", maintaining contact at {endpoint}"
        detail = str(contact.get("detail") or "").strip()
        return f"{phrase}, {detail}" if detail else phrase
    if not subject_first:
        return f"{right} is under {left} ({manner})"
    # "You" always takes the plural verb form ("you are", "you hold"), and a
    # bare name the singular; with a part, the part decides.
    plural = _part_is_plural(actor_part) if actor_part else actor_is_you
    if manner in _MOMENTARY_SET:
        verb = _CONTACT_RESIDUE_VERB[plural]
    elif manner in _CONTACT_STATE_VERBS:
        verb = _CONTACT_STATE_VERBS[manner][plural]
    else:
        # Outside both vocabularies the fiction is on its own: inflect only
        # when the model has not already done it ("throttles" must not become
        # "throttleses"), and never for a plural subject.
        verb = manner if (plural or manner.endswith("s")) else f"{manner}s"
    detail = str(contact.get("detail") or "").strip()
    return f"{left} {verb} {right}, {detail}" if detail else f"{left} {verb} {right}"


def contact_sensation(contact: dict, *, you: str, scene: dict = None,
                      label_for=None) -> str:
    """What one STANDING contact continuously delivers to ONE party's body.

    `label_for` is the identity floor (AGENTS.md: every payload that hands a
    mind prose somebody else wrote needs one): a callable mapping the OTHER
    party's canonical name to what THIS observer may call them. Without it,
    this clause named the other body canonically and the composer tripwire
    fired on every contact beat with an unrecognized partner (measured live,
    chat 70: `unearned identity ['Elyra Voss'] reached the composed view` —
    the scrub held the line; the floor belongs here at the source). Absent,
    the canonical name passes through unchanged, for callers rendering an
    omniscient or self-only view.

    `contact_phrase` renders a contact as an objective third-party fact -- who
    is touching whom, where. That is what a narrator needs and it is not what
    the touching party FEELS, so a perceiver in sustained contact received a
    diagram of the contact and no sensation from it.

    The gap this closes: the perception contract specified the tactile channel
    only as a SUBSTITUTE for sight -- every mandatory clause was conditioned on
    sight being absent (in the dark, behind a wall, sealed inside something).
    With both parties in a lit room and in continuous contact, the channel is
    wide open and nothing required a word of it, so under a token budget the
    view rendered what was seen and dropped what was felt. Measured across the
    corpus before this: 46.8% of all observations classified as `mixed`
    because no sensory cue matched them at all, and `interoception` accounted
    for 2.4%.

    A standing contact is neither an event nor inert state. It is a CONTINUOUS
    PERCEPT: true every beat and felt every beat, until it ends. This renders
    that percept, in the second person, from the named party's side, in plain
    physical terms -- pressure, movement, friction, warmth -- and says nothing
    about what the other body is doing internally, which no contact carries.

    Returns "" when the named party is not a party to the contact: a bystander
    watching two other people touch feels nothing, and this must never be the
    thing that tells them otherwise.
    """
    if not isinstance(contact, dict):
        return ""
    actor = str(contact.get("actor") or "").strip()
    target = str(contact.get("target") or "").strip()
    observer = str(you or "").strip()
    if not actor or not target or not observer:
        return ""
    # Through `same_subject`, never `==`: one being routinely carries a cast
    # display name and a scene entity id at once, and a contact recorded under
    # one spelling against a perceiver named by the other would silently match
    # nobody -- leaving the party to a contact feeling nothing from it.
    def _is_observer(name):
        if scene is not None:
            return same_subject(scene, name, observer)
        return str(name or "").strip().casefold() == observer.casefold()

    actor_is_observer = _is_observer(actor)
    if actor_is_observer:
        mine, theirs = contact.get("actor_part"), contact.get("target_part")
        other = target
    elif _is_observer(target):
        mine, theirs = contact.get("target_part"), contact.get("actor_part")
        other = actor
    else:
        return ""
    if callable(label_for):
        other = str(label_for(other) or other)

    # A slot holding an act, a sound or a state is a malformed record, not a
    # body. Say nothing rather than render a sensation nobody could have.
    if not (_is_anatomical_part(mine) and _is_anatomical_part(theirs)):
        return ""

    relation_kind = contact_relation(contact)
    motion_kind = contact_motion(contact)
    if relation_kind != "interior" and contact_is_momentary(contact):
        # A momentary manner names the ACT that made the touch, and the act's
        # own `motion` field says how the act moved -- a kiss is recorded
        # `moving`. The standing record outlives the act, so rendering that
        # stored motion delivered "movement and friction" for a kiss four
        # beats gone (measured: a head-kiss from turn 42 was still felt as a
        # live, moving kiss at turn 47, while its owner held a conversation).
        # What a momentary SURFACE contact continuously delivers is its
        # RESIDUE -- lips resting where the kiss landed -- exactly as
        # `contact_phrase` already renders it; the act itself reaches
        # perceivers through the beat's declared sequence, the representation
        # that carries WHEN. An INTERIOR contact is different: its enclosure
        # persists by definition, so `moving` there describes standing
        # kinematics (a blade working in a wound, a thrust not yet stilled),
        # not the echo of a finished act.
        motion_kind = "settled"
    if relation_kind == "interior":
        # `actor` is the party whose part goes in; the TARGET encloses it.
        # `target_part` names the endpoint/contact site. It does not mean that
        # endpoint is itself a cavity, so interior rendering must keep the
        # target entity and endpoint as two separate facts.
        side = "entering" if actor_is_observer else "enclosing"
        tail = "continuous while it stays there"
    else:
        side, tail = "either", "continuous while the contact holds"
    mine = str(mine or "").strip().replace("_", " ")
    theirs = str(theirs or "").strip().replace("_", " ")
    target_interior = str(
        contact.get("target_interior") or "").strip().replace("_", " ")
    if relation_kind == "interior":
        if motion_kind == "moving":
            quality = ("changing pressure, heat and friction along its length"
                       if side == "entering" else
                       "fullness, stretch, shifting pressure and movement")
        else:
            quality = ("pressure, heat and movement along its length"
                       if side == "entering" else
                       "pressure, fullness and movement")
        if side == "entering":
            site = f"your {mine}" if mine else "your body"
            plural = _part_is_plural(mine) if mine else False
            verb = "register" if plural else "registers"
            pronoun = "them" if plural else "it"
            enclosure = (f"{other}'s {target_interior}"
                         if target_interior else other)
            relation = f"{enclosure} enclosing {pronoun}"
            if theirs:
                relation += f", with contact at {other}'s {theirs}"
        else:
            site = "your body"
            source = f"{other}'s {theirs}" if theirs else other
            enclosure = f"your {target_interior}" if target_interior else "you"
            relation = f"{source} within {enclosure}"
            if mine:
                relation += f", with contact at your {mine}"
            verb = "registers"
        return f"{site} {verb} {relation}: {quality}, {tail}"

    sensation_kind = "moving" if motion_kind == "moving" else "settled"
    relation, quality = _SENSATION_FORMS[(sensation_kind, side)]
    site = f"your {mine}" if mine else "your body"
    source = f"{other}'s {theirs}" if theirs else other
    # Body parts are routinely plural, and the subject here is the PART, not
    # the person: "your legs registers" and "against it" for two legs are the
    # same agreement bug `contact_phrase` already carries `_part_is_plural`
    # for. The trailing pronoun refers back to the perceiver's own part.
    plural = _part_is_plural(mine) if mine else False
    verb = "register" if plural else "registers"
    relation = relation.replace(" it", " them") if plural else relation
    return f"{site} {verb} {source} {relation}: {quality}, {tail}"


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
    facts.extend(pose_facts(scene, observer, source_names))

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
                # The passage bends. You cannot see ROUND a corner, but you can
                # see that it goes on rather than stopping -- which is the
                # difference between "bends and continues" and "bends into
                # who knows what". Nothing beyond the corner is claimed.
                terminus = "turn"
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


# What one beat of running buys, in small-room units. A pace of three ordinary
# chambers is brisk without being a teleport; a large hall eats two of them and
# a vast one the whole budget, so a run crosses distance rather than room COUNT.
# Deliberately coarse: the engine is not simulating gait, it is answering "does
# a body cross this much ground in one beat" well enough that the answer is
# never absurd.
SPRINT_BUDGET = 3
_ROOM_COST = {"tiny": 1, "small": 1, "": 1, "medium": 1,
              "large": 2, "huge": 3, "vast": 3}


def passable_path(scene, from_room, to_room, limit=12):
    """The shortest walk of passable doorways from one room to another, as a
    list of rooms EXCLUDING the start and ending at `to_room` -- or [] when
    there is none.

    `passable_route_exists` answers whether; this answers which rooms. A body
    that crosses several rooms in one beat has been in every one of them, and
    a caller recording only where they stopped leaves holes in their memory
    exactly where their feet went. Adjacent rooms give a one-element path, so
    an ordinary step needs no special case.

    `limit` bounds the search: past a dozen rooms a single-beat "walk" is a
    teleport wearing a route, and reconstructing a path for it would dress the
    teleport up as ground covered.
    """
    if not from_room or not to_room or from_room == to_room:
        return []
    rooms = scene.get("rooms") or {}
    neighbors: dict[str, set] = {}
    for room_id, room in rooms.items():
        if not isinstance(room, dict):
            continue
        for edge in room.get("adjacent") or []:
            if not isinstance(edge, dict) or not edge.get("to"):
                continue
            if normalize_barrier(edge.get("barrier")) not in _PASSABLE_BARRIERS:
                continue
            neighbors.setdefault(str(room_id), set()).add(str(edge["to"]))
            neighbors.setdefault(str(edge["to"]), set()).add(str(room_id))

    from collections import deque
    prev = {str(from_room): None}
    queue = deque([(str(from_room), 0)])
    while queue:
        cur, depth = queue.popleft()
        if cur == str(to_room):
            path = []
            while cur is not None and prev[cur] is not None:
                path.append(cur)
                cur = prev[cur]
            return list(reversed(path))
        if depth >= limit:
            continue
        for nxt in sorted(neighbors.get(cur, ())):
            if nxt not in prev:
                prev[nxt] = cur
                queue.append((nxt, depth + 1))
    return []


def sprint_reach(scene, room_id, known_rooms=None):
    """How far a body could RUN out of this room, per passage, bends allowed.

    A character could only ever move one room per beat, which makes a courier
    whose whole craft is speed indistinguishable from someone strolling, and
    turns any distance into a queue of identical beats. Running is the obvious
    missing verb.

    The bound is DECISION, not sight -- and the first version got that wrong.
    It stopped a run at every bend on the reasoning that you cannot see round
    a corner, and the measurement said what that reasoning was worth: in a
    live 7x7 perfect maze, 39 of 49 rooms were two-exit corridor cells and
    almost every corridor cell was a bend, so 72 of 96 runnable passages
    offered exactly one room, the mean offer was 1.3 rooms, and the
    SPRINT_BUDGET never once bound. Winding is what makes a maze a maze;
    a sight-bounded run cannot exist in one. The worry sight was standing in
    for was never the corner itself -- a body enters a room it has not seen
    every time it walks through a doorway, and perceives it by being in it.
    The thing that genuinely costs a beat is a CHOICE: a junction run through
    at speed is a route picked without looking. So the run follows a corridor
    round its bends for as long as there is exactly one passable way onward,
    and stops where a decision (junction), the world (door, darkness,
    dead end), or the beat (full_reach) stops it. Decision-bounded, the same
    maze offers a mean of 2.48 rooms and the budget binds 64 times.

    A see-through side opening (window, bars) is not a junction: it offers no
    route, so it forces no choice. And the run itself still follows only
    PASSABLE doorways -- you can see through bars and you cannot run through
    them.

    `known_rooms` is the OFFER-side firewall, and it is why this function has
    two modes. Objectively (known_rooms=None, the Director's resolve ceiling)
    the reach reports the scene as it is -- the Director owns objective
    causality and may see it. But handed to a deciding character, that same
    report would smuggle unearned map: a mind standing still would learn that
    an unvisited passage winds on for three rooms and ends at a junction,
    geometry it never perceived. Running through ground teaches it; being
    TOLD the reach does not. So a character-facing caller passes the rooms
    that character has legitimately been in, and the offer extends only
    through what can be vouched for: the straight sightline from here (looking
    down a passage is ordinary sight, and it ends at the first bend), plus
    remembered rooms beyond it. Where the passage runs on into ground the
    view cannot vouch for, the offer stops with `stops: "unknown"` -- the run
    itself may still be declared open-ended, and resolves against the
    objective reach. One residue is documented rather than hidden: within
    remembered ground beyond the sightline, `door`/`darkness` stops read the
    room's CURRENT state, which anticipates by one beat what the run would
    discover anyway.

    Returns one entry per runnable passage:

        {"bearing": "n", "path": [rid, ...], "rooms": 2,
         "stops": "junction"|"dead_end"|"darkness"|"door"|"full_reach"|"unknown"}

    `bearing` is ABSENT when the doorway carries no `dir` -- the world gives
    no compass there, and the run is declared by destination instead. Such a
    passage's sightline ends at its first room: with no heading there is no
    straight line to certify, so everything beyond is remembered ground only.

    `full_reach` is the budget stop, and its name is deliberately about
    DISTANCE, not physiology. It was `winded` first, and the word beat its
    own documentation -- third label in this engine to do so (`closed` read
    as "no way through" kept a shrine unentered for five runs; `spent` read
    as "do not go" turned a courier off his own proven route). Observed
    verbatim: "he would be winded? But he might not want to be winded if he
    needs to assess contents" -- the best offer a run can get, the passage
    outlasting the beat, read as a penalty for taking it. A MARGINAL
    deterrent, measured precisely: the same character took one such run in
    full (beat 1 of the same arm) and then reasoned against later ones, so
    the label tipped close decisions rather than forbidding anything --
    which is how a mislabel does its damage. Worse, the penalty
    reading was FALSE as a distinguishing fact: every hard run arrives
    winded (the Director applies that cost whatever ends the run), so the
    label implied a consequence specific to maximal runs that is not
    specific at all. The stop reason names why the run ENDED; what running
    COSTS is the Director's to narrate, and the two must not share a word.

    `bearing` is the doorway taken OUT of this room; the path beyond it may
    bend. `path` is every room crossed, in order, ENDING at the room they
    finish in -- callers need the whole list, not the destination: a body
    that runs through three chambers has been in three chambers, and
    recording only where they stopped would leave holes in their map where
    their feet went. Empty list when nothing is runnable that way, and the
    passage is omitted.
    """
    rooms = (scene or {}).get("rooms") or {}
    start = rooms.get(room_id)
    if not isinstance(start, dict):
        return []
    known = None if known_rooms is None else {str(r) for r in known_rooms}
    out = []
    for edge in start.get("adjacent") or []:
        if not isinstance(edge, dict) or not edge.get("to"):
            continue
        if normalize_barrier(edge.get("barrier")) not in _PASSABLE_BARRIERS:
            continue
        # A doorway with no bearing is still a doorway, and a run through it
        # is still a run. Requiring `dir` here silently deleted the passage
        # from every run offer -- measured live (maze arm) as a shrine whose
        # ONLY approach could never be run, and beats of "fails to move east
        # due to missing bearing" while the character re-declared a compass
        # the world could not bind. The offer carries no `bearing` key
        # (absent means the world gives no compass here, per the
        # _onward_exits convention); `run_ends_at`/`path` still name it, so
        # a run is declared by its destination instead of a heading.
        heading = normalize_bearing(edge.get("dir"))
        cur, prev, spent, path, stops = edge.get("to"), room_id, 0, [], None
        # Whether `cur` is still on the straight line of sight from where the
        # body stands. The first room always is (you see it through the
        # doorway); a bend ends the line for good, even if the passage later
        # resumes the original heading.
        on_sightline = True
        while cur:
            cur = str(cur)
            room = rooms.get(cur)
            if not isinstance(room, dict):
                stops = "unknown"
                break
            # The offer-side firewall: past the sightline, only remembered
            # ground can be vouched for. Checked before light, because the
            # current darkness of a room you cannot see and have never
            # entered is exactly the kind of fact this gate exists to hold
            # back.
            if known is not None and not on_sightline and cur not in known:
                stops = "unknown"
                break
            # Running into a room you cannot see into is how a body breaks an
            # ankle. The world stopping you, not a decision.
            if _LIGHT_SIGHT.get(effective_light(scene, cur), "full") != "full":
                stops = "darkness"
                break
            cost = _ROOM_COST.get(
                str(room.get("size") or "").strip().lower(), 1)
            if spent + cost > SPRINT_BUDGET:
                stops = "full_reach"
                break
            spent += cost
            path.append(cur)
            onward = [
                e for e in (room.get("adjacent") or [])
                if isinstance(e, dict) and str(e.get("to")) != str(prev)
                and e.get("to")
            ]
            if not onward:
                stops = "dead_end"
                break
            passable = [e for e in onward if normalize_barrier(
                e.get("barrier")) in _PASSABLE_BARRIERS]
            if len(passable) > 1:
                # A junction is a decision, and a decision is a beat. Running
                # blind through one would be choosing without looking.
                stops = "junction"
                break
            if not passable:
                # The only way on is shut. The world stopping you.
                stops = "door"
                break
            nxt = passable[0]
            # No heading means no straight line to certify: the first room
            # is vouched by ordinary sight through the doorway, everything
            # beyond it must be remembered ground. Without this, a chain of
            # bearingless edges would hold `on_sightline` open forever and
            # walk the offer through ground the character never earned.
            if on_sightline and (heading is None
                                 or normalize_bearing(nxt.get("dir"))
                                 != heading):
                on_sightline = False
            prev, cur = cur, nxt.get("to")
        if path:
            entry = {"path": path, "rooms": len(path),
                     "stops": stops or "full_reach"}
            if heading:
                entry["bearing"] = heading
            out.append(entry)
    return out


def _onward_exits(scene, all_rooms, target_id, from_room):
    """How many ways out of `target_id` lead somewhere other than back here.

    Looking through a doorway into a chamber, you see whether it has another
    way out -- that is ordinary sight, not deduction. Without it a character
    has to physically walk into a dead end to discover it is one, which is
    exactly what was observed: a maze runner entered the same one-exit chamber
    six times, having never been given the one fact that would have told him.

    Requires FULL sight of the chamber, not merely some sight. Light spilling
    through an open doorway makes a dark room read `dim`, which is enough for
    bulk and movement and nowhere near enough to count doorways or tell which
    wall they are in -- `corridor_sightlines` already stops its line at
    anything short of full sight for exactly that reason, and the two must not
    disagree about what gloom can be read through. Absent means "could not
    tell", never "none" -- a caller must not read a missing key as a dead end.

    `onward_bearings` names WHICH ways those are, and it is not decoration. A
    bare count is read as a promise to continue: observed live, a runner given
    `onward_exits: 1` for the chamber to his west walked west into it four
    times over nine beats hunting a west exit that never existed -- the one
    other way out went north. He was not reasoning badly; he was told a number
    where he needed a bearing. Omitted per-edge when an edge carries no `dir`,
    and omitted entirely when none do, because a scene without directions has
    no bearings to give and inventing them would be inventing a sense.
    """
    if _LIGHT_SIGHT.get(effective_light(scene, target_id), "full") != "full":
        return {}
    # Counted by DESTINATION, and over reverse-declared edges too. A doorway
    # is one doorway whichever room's `adjacent` list happens to name it, and
    # the director routinely declares only one side: counting `target`'s own
    # edges alone reported nought for chambers that plainly had a way on, and
    # nought is what raises `visibly_no_way_through`. Inventing a dead end is
    # the worse error of the two -- it argues against a real route.
    ways = {}
    for edge in (all_rooms.get(target_id) or {}).get("adjacent") or []:
        if not isinstance(edge, dict):
            continue
        if normalize_barrier(edge.get("barrier")) == "wall":
            continue
        dest = str(edge.get("to") or "")
        if dest and dest != str(from_room):
            ways.setdefault(dest, normalize_bearing(edge.get("dir")))
    for other_id, other in all_rooms.items():
        if str(other_id) in (str(target_id), str(from_room)):
            continue
        if not isinstance(other, dict) or str(other_id) in ways:
            continue
        for edge in other.get("adjacent") or []:
            if not isinstance(edge, dict) or str(edge.get("to")) != str(target_id):
                continue
            if normalize_barrier(edge.get("barrier")) == "wall":
                continue
            # Seen from the far side, so the bearing is the far side's,
            # reversed. Same doorway, opposite wall.
            ways[str(other_id)] = opposite_bearing(
                normalize_bearing(edge.get("dir")))
            break
    out = {"onward_exits": len(ways)}
    bearings = []
    for heading in ways.values():
        if heading and heading not in bearings:
            bearings.append(heading)
    if bearings:
        out["onward_bearings"] = bearings
    return out


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

        # This list is delivered as literal sight -- a perceiver's
        # `visible_rooms` admits the whole room record into their payload --
        # and an unlit room shows an opening full of nothing. The doorway
        # itself survives elsewhere (the current room's edge keeps its
        # barrier; only the destination is withheld, the same shape as the
        # F6 projection). `effective_light` already accounts for spill, so a
        # dark cellar behind a lit doorway reads dim and stays visible as
        # shapes; only total dark is withheld.
        if light_blocks_sight(effective_light(scene, adjacent_id)):
            continue

        room_data = all_rooms[adjacent_id]
        notes = (
            room_data.get("notes")
            or room_data.get("desc")
            or ""
        )

        # No prose does NOT mean no room. The reverse loop below has always
        # kept a descriptionless neighbour (test_reverse_adjacency exercises
        # exactly that), so skipping it here made visibility depend on which
        # side happened to declare the edge and on whether anyone had written
        # notes yet -- a bidirectional edge to the same undescribed room was
        # already included via the reverse pass. Sight is physical: an
        # unwritten room is still visibly THERE, and the deterministic
        # consumers of this list (commit.py's dead-end ledger, character.py's
        # seen_onward, narration.py's portal gating) read absence as "cannot
        # see", not as "nothing authored yet".
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
                # The reverse pass exists so a bidirectional doorway declared
                # from one side is visible from both. A one-way window is the
                # one edge where that generosity is wrong: it is declared in
                # the direction it looks, and looking back is what it refuses.
                or barrier == "one_way_window"
                or barrier not in _SIGHT_BARRIERS
                or _is_carried_interior(scene, other_id)
                # Same light gate as the forward loop: sight does not care
                # which room declared the edge, and neither does the dark.
                or light_blocks_sight(effective_light(scene, other_id))
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
                # Sight does not care which room declared the edge. Omitting
                # this here made a whole class of neighbour permanently
                # opaque -- absent reads as "cannot tell from here", so a
                # visibly closed chamber that happened to be reverse-declared
                # had to be walked into to be ruled out.
                **_onward_exits(scene, all_rooms, other_id, room_id),
            })
            seen.add(other_id)

            break

    return visible


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

    # Edge FIELDS get the same silence-vs-erasure doctrine the edges
    # themselves already have. A model re-mentioning a doorway ("r0503
    # connects to r0603, open") has no reliable way to also echo back the
    # bearing it never thinks about, and wholesale replacement here was
    # erasing authored `dir`s every time -- measured live (maze arm): 18 of
    # 98 edge-sides stripped bare, including the shrine's ONLY approach,
    # after which every declared "run east" through them failed and
    # sprint_reach stopped offering the passage at all. An absent field is
    # silence; a value (barrier changes, a re-bearing) still lands.
    for edge in (incoming.get("adjacent") or []):
        if isinstance(edge, dict) and edge.get("to"):
            prior = existing_edges.get(edge["to"])
            if prior:
                spoken = {k: v for k, v in edge.items()
                          if v is not None and v != ""}
                existing_edges[edge["to"]] = {**prior, **spoken}
            else:
                existing_edges[edge["to"]] = dict(edge)

    merged_room["adjacent"] = list(existing_edges.values())

    for key, value in incoming.items():
        if key in ("name", "desc", "notes", "parent_entity", "adjacent"):
            continue
        # An empty container is indistinguishable from "the model did not
        # mention this", so it cannot be read as an erasure -- the doctrine
        # `_ENTITY_DEFAULT_FIELDS` already applies to entities, and the same
        # trap on rooms costs more: blanking `anchors` takes every station
        # hanging off them with it, silently, on any beat that re-echoes the
        # room. Emptying one goes through an explicit write, not a default.
        if key in _ROOM_SILENT_WHEN_EMPTY and not value:
            continue
        merged_room[key] = value

    return merged_room


# Room fields whose empty value means "unmentioned" rather than "cleared".
_ROOM_SILENT_WHEN_EMPTY = frozenset({"anchors", "size", "zone", "light",
                                     "exposure"})

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


def _shield_standing_bearings(prior_rooms, incoming_rooms):
    """Refuse a ONE-SIDED re-bearing of a doorway both sides already agree on.

    A doorway whose two declared sides carry opposite-consistent bearings is
    a standing agreement -- usually authored world geometry. A model
    re-declaring one room routinely emits a wrong `dir` for an edge it is
    only mentioning in passing, and letting that single claim through
    destroys the agreement twice over: normalize_scene_bearings sees the
    contradiction and drops BOTH sides ("dropped rather than guessed"), and
    its reciprocal inference then faithfully rebuilds whatever wrong bearing
    gets asserted next. Measured live (maze arm): five doorway pairs carried
    internally-consistent bearings that were geometrically FALSE, and a
    runner was walked north on a declared "west" -- model noise laundered
    into scene truth by the engine's own repair machinery.

    So: an incoming `dir` that contradicts a standing opposite-consistent
    pair is stripped (the edge itself still merges -- barrier and distance
    changes land) unless the SAME diff re-declares the reciprocal side with
    the matching opposite. Changing settled geometry takes a two-sided
    declaration; a one-sided one falls back to the incumbent. Returns a
    sanitized copy; never mutates the caller's diff.
    """
    if not isinstance(incoming_rooms, dict) or not isinstance(
            prior_rooms, dict):
        return incoming_rooms

    def _edge_dir(rooms, room_id, to_id):
        room = rooms.get(room_id)
        if not isinstance(room, dict):
            return None
        for e in room.get("adjacent") or []:
            if isinstance(e, dict) and str(e.get("to")) == str(to_id):
                return normalize_bearing(e.get("dir"))
        return None

    out = {}
    for room_id, room in incoming_rooms.items():
        if not isinstance(room, dict) or not room.get("adjacent"):
            out[room_id] = room
            continue
        edges = []
        touched = False
        for edge in room.get("adjacent") or []:
            if not isinstance(edge, dict) or not edge.get("to"):
                edges.append(edge)
                continue
            new_dir = normalize_bearing(edge.get("dir"))
            to_id = edge["to"]
            if new_dir:
                fwd = _edge_dir(prior_rooms, room_id, to_id)
                back = _edge_dir(prior_rooms, to_id, room_id)
                standing = (fwd and back
                            and opposite_bearing(fwd) == back)
                if standing and new_dir != fwd:
                    recip = _edge_dir(incoming_rooms, to_id, room_id)
                    if recip != opposite_bearing(new_dir):
                        edge = {k: v for k, v in edge.items() if k != "dir"}
                        touched = True
            edges.append(edge)
        out[room_id] = {**room, "adjacent": edges} if touched else room
    return out


def _shield_standing_passage(prior_rooms, incoming_rooms, add_warning=None):
    """Refuse a ONE-SIDED sealing of a doorway that is standing open.

    The mirror of `_shield_standing_bearings`, and it exists because the same
    thing happened to `barrier` that had already happened to `dir`. Live, chat
    63 turn 165, across five consecutive rerolls: `mapping_stage` authored the
    stair between the shrine's two floors as `open_shoji` every single time,
    and `director_resolve` then re-declared the RETURN edge alone as `wall` --
    leaving one direction passable, the other sealed, and no route between a
    hall and its own upstairs.

    A barrier is a property of the doorway, not of the side you stand on. So a
    one-sided downgrade from passable to `wall` falls back to the incumbent
    unless the SAME diff seals the reciprocal side too. Sealing a passage takes
    a two-sided declaration; everything else about the edge still merges, and a
    room the diff opens UP is never blocked -- this only refuses the close.
    """
    if not isinstance(incoming_rooms, dict) or not isinstance(prior_rooms, dict):
        return incoming_rooms

    def _edge_barrier(rooms, room_id, to_id):
        room = rooms.get(room_id)
        if not isinstance(room, dict):
            return None
        for e in room.get("adjacent") or []:
            if isinstance(e, dict) and str(e.get("to")) == str(to_id):
                return normalize_barrier(e.get("barrier"))
        return None

    out = {}
    for room_id, room in incoming_rooms.items():
        if not isinstance(room, dict) or not room.get("adjacent"):
            out[room_id] = room
            continue
        edges = []
        touched = False
        for edge in room.get("adjacent") or []:
            if not isinstance(edge, dict) or not edge.get("to"):
                edges.append(edge)
                continue
            to_id = edge["to"]
            new_barrier = normalize_barrier(edge.get("barrier"))
            if new_barrier == "wall":
                fwd = _edge_barrier(prior_rooms, room_id, to_id)
                back = _edge_barrier(prior_rooms, to_id, room_id)
                standing = (fwd in _PASSABLE_BARRIERS
                            or back in _PASSABLE_BARRIERS)
                recip = _edge_barrier(incoming_rooms, to_id, room_id)
                if standing and recip != "wall":
                    edge = {k: v for k, v in edge.items() if k != "barrier"}
                    touched = True
                    if add_warning:
                        add_warning(
                            "kept the passage %s -> %s open: it was sealed "
                            "from one side only, and the other side still "
                            "reads %r" % (room_id, to_id,
                                          recip or fwd or back))
            edges.append(edge)
        out[room_id] = {**room, "adjacent": edges} if touched else room
    return out


def connect_orphan_new_rooms(scene: dict, prev_scene: dict) -> list:
    """A room created this turn must be reachable from somewhere.

    Adjacency resolves BOTH ways, so a room with an empty `adjacent` is fine as
    long as something points AT it -- which is why `alley_room` works while
    carrying no edges of its own. The failure is the stronger one: a room no
    edge reaches in EITHER direction. `spatial_rel` answers `separated`/`far`
    for every pair involving it, so it is an island, and the only thing its
    occupants can perceive is whatever happens to be standing in it with them.

    Live (chat 58): `northern_plaza` was minted with `adjacent: []` and nothing
    pointing at it. The player stepped out of the TARDIS into a described city
    plaza -- shuttered buildings, dripping awnings, an alley the Dalek was
    grinding out of -- and her view could only offer her the police box she had
    just left, because the dock edge was the single edge the map admitted.

    Applied ONLY to rooms that are new in this merge, and only at the moment
    they are created, because that is the one point where the engine still has
    the context to place them: where the bodies were standing immediately
    before. After the fact there is nothing left to infer from, which is why
    this cannot be a periodic repair pass.

    Interiors are skipped: a `parent_entity` room's doorway is DERIVED by
    `apply_transit_dock_edges` (which runs straight after this), and a sealed
    or in-transit hull is severed from the world on purpose.

    Mutates `scene` in place. Returns [(room_id, attached_to), ...].
    """
    rooms = scene.get("rooms")
    if not isinstance(rooms, dict) or len(rooms) < 2:
        return []
    known = set((prev_scene or {}).get("rooms") or {})
    fresh = [rid for rid in rooms if rid not in known]
    if not fresh:
        return []

    reached = set()
    for rid, room in rooms.items():
        for edge in (room.get("adjacent") or []):
            if isinstance(edge, dict) and edge.get("to"):
                reached.add(str(edge["to"]))
                reached.add(str(rid))

    # Where the bodies were standing BEFORE this turn's diff -- the scene's
    # centre of gravity, and the only honest guess available.
    counts = {}
    for room_id in ((prev_scene or {}).get("positions") or {}).values():
        if room_id and room_id in rooms:
            counts[room_id] = counts.get(room_id, 0) + 1
    attached = []
    for rid in fresh:
        room = rooms[rid]
        if not isinstance(room, dict) or room.get("parent_entity"):
            continue
        if rid in reached:
            continue
        anchor = max((r for r in counts if r != rid),
                     key=counts.get, default=None)
        if anchor is None:
            anchor = next((r for r in rooms if r != rid), None)
        if not anchor:
            continue
        room.setdefault("adjacent", []).append(
            {"to": anchor, "barrier": "open", "distance": "near"})
        reached.add(rid)
        reached.add(anchor)
        attached.append((rid, anchor))
    return attached


def _position_key(scene: dict, name) -> Optional[str]:
    """Canonical existing position key for an actor label, case-insensitive."""
    label = str(name or "").strip()
    if not label:
        return None
    positions = scene.get("positions") or {}
    if label in positions:
        return label
    folded = label.casefold()
    return next(
        (key for key in positions
         if str(key).strip().casefold() == folded),
        None,
    )


def apply_following_ops(scene: dict, operations) -> dict:
    """Apply voluntary durable follower -> target relations to ``scene``.

    Following records intention and ordinary travel affiliation; it never
    changes a position here. Movement follow-through is deliberately owned by
    the Director, where pace, barriers, and actor decisions are available.
    This function only maintains the durable ledger used equally by mid-turn
    perception merges, commit, checkpoints, branches, and rerolls.
    """
    following = scene.get("following")
    if not isinstance(following, dict):
        following = scene["following"] = {}

    for raw in operations or []:
        if not isinstance(raw, dict):
            continue
        op = str(raw.get("op") or "").strip().casefold()
        follower = _position_key(scene, raw.get("follower"))
        if follower is None:
            continue
        if op == "stop":
            for key in list(following):
                if str(key).strip().casefold() == follower.casefold():
                    following.pop(key, None)
            continue
        if op != "start":
            continue
        target = _position_key(scene, raw.get("target"))
        if target is None or target.casefold() == follower.casefold():
            continue

        # A follows B follows A is not travel; it is an ownerless cycle. Longer
        # cycles are rejected on the same terms. Case-tolerant because older
        # scenes can carry human-authored labels.
        cursor = target
        visited = {follower.casefold()}
        cyclic = False
        while cursor:
            folded = cursor.casefold()
            if folded in visited:
                cyclic = True
                break
            visited.add(folded)
            rec = next(
                (value for key, value in following.items()
                 if str(key).strip().casefold() == folded
                 and isinstance(value, dict)),
                None,
            )
            cursor = _position_key(scene, (rec or {}).get("target"))
        if cyclic:
            continue

        # Replace a case-variant/old target in place; one body follows at most
        # one target at a time.
        for key in list(following):
            if str(key).strip().casefold() == follower.casefold():
                following.pop(key, None)
        following[follower] = {
            "target": target,
            "since_turn": raw.get("turn"),
            "reason": str(raw.get("reason") or "").strip(),
        }

    # A departed/deleted actor cannot remain in the travel ledger. Separation
    # alone does NOT clear it: a follower left behind by a sprint may still be
    # trying to catch up and decides that on their next beat.
    positioned = {
        str(key).strip().casefold() for key in (scene.get("positions") or {})
    }
    for follower, rec in list(following.items()):
        target = str((rec or {}).get("target") or "").strip().casefold() \
            if isinstance(rec, dict) else ""
        if str(follower).strip().casefold() not in positioned \
                or target not in positioned:
            following.pop(follower, None)
    return scene


def merge_scene_with_diff(
    scene: dict,
    diff: dict | None,
    *,
    contact_report=None,
    substance_report=None,
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

    _prior_rooms = (merged["rooms"]
                    if isinstance(merged.get("rooms"), dict) else {})
    incoming_rooms = _shield_standing_bearings(
        _prior_rooms, diff.get("rooms") or {})
    incoming_rooms = _shield_standing_passage(
        _prior_rooms, incoming_rooms)
    incoming_entities = diff.get("entities") or {}
    incoming_positions = diff.get("positions") or {}
    incoming_stations = diff.get("stations") or {}
    incoming_poses = diff.get("poses") or {}

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

    # A FIELD NAME can never key an entity. A sibling field written one
    # nesting level too deep (or its validation debris) arrives in the
    # entities map keyed `remove_entities`, `notes`, ... -- chat 80's scene
    # carried six such "entities", each a verbatim copy of the Interview
    # Chair. The hoist in schemas.preprocess_llm_output now stops new ones at
    # validation; this floor refuses whatever still arrives AND heals a scene
    # already carrying them, since the merged blob is what commits -- the
    # same heal-on-load shape commit._fold_duplicate_presences uses, so a
    # live story needs no migration.
    for _bad in [k for k in merged["entities"] if k in NON_ENTITY_FIELD_KEYS]:
        merged["entities"].pop(_bad, None)

    if isinstance(incoming_positions, dict):
        merged["positions"].update(incoming_positions)
    # The same refusal for the position ledger: a field name is not a body,
    # so it cannot stand in a room. After the update so an incoming key is
    # refused too, before the dedup below reads the ledger.
    for _bad in [k for k in merged["positions"] if k in NON_ENTITY_FIELD_KEYS]:
        merged["positions"].pop(_bad, None)
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
    apply_pose_diff(merged, incoming_poses)

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
        folded_names = {str(name).strip().casefold() for name in names if name}
        merged["poses"] = {
            name: pose for name, pose in (merged.get("poses") or {}).items()
            if str(name).strip().casefold() not in folded_names
        }
        for pose in (merged.get("poses") or {}).values():
            if isinstance(pose, dict) and str(
                    pose.get("relative_to") or "").strip().casefold() in folded_names:
                pose["relative_to"] = ""
                pose["relation"] = ""
                pose["constraint"] = ""
        merged["substances"] = [
            record for record in (merged.get("substances") or [])
            if not isinstance(record, dict)
            or str(record.get("target") or "").strip().casefold()
            not in folded_names
        ]

    occupied_rooms = set(merged["positions"].values())

    for room_id in diff.get("remove_rooms") or []:
        if room_id in occupied_rooms:
            continue
        merged["rooms"].pop(room_id, None)
        merged["substances"] = [
            record for record in (merged.get("substances") or [])
            if not isinstance(record, dict)
            or str(record.get("target") or "") != str(room_id)
        ]

    # A body's interior is opaque whether or not anyone declared it so. Runs
    # BEFORE the dock-edge rewrite, which reads `enclosure` to pick the
    # doorway's barrier.
    infer_body_enclosures(merged)

    # Derived dock/portal edges are a function of the merged scene, not an
    # authored fact -- recompute them here so every consumer of a merge
    # (commit preparation, perception's mid-turn merges) sees the same
    # correct doorways. Runs before barrier normalization, which then
    # canonicalizes whatever the rewrite emitted.
    # A room minted this turn that no edge reaches is an island: every pair
    # involving it answers `separated`/`far`, so its occupants can perceive
    # nothing but each other. Runs BEFORE the dock rewrite, which owns
    # interiors and is left to derive those on its own.
    connect_orphan_new_rooms(merged, scene)

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
    # Station hygiene moved to the end of the merge, beside contact hygiene:
    # it has to run after `derive_contained_positions`, or a carried body keeps
    # the anchor it was standing at while its carrier walks off with it.
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
    # One spelling per being, BEFORE anything resolves a subject against
    # another ledger. A containment record naming an entity id and a positions
    # map keyed by the display name are the same fact written twice, and every
    # lookup between them fails silently until they agree.
    normalize_scene_subjects(merged)
    normalize_scene_containment(merged)
    # Derived LAST among position writes: whatever else this beat did to
    # positions, a carried body ends up where its carrier is.
    derive_contained_positions(merged)
    # ...and a position that names an ENTITY rather than a room is repaired
    # after that, so a real containment record always wins over the guess.
    repair_entity_positions(merged)
    # A bodiless voice is not standing anywhere; a position on one is a
    # category error that no author can currently delete by hand.
    prune_bodiless_positions(merged)

    # Durable travel affiliation. This changes only the relation ledger;
    # position follow-through already ran at Director resolution so perception
    # and commit merge the exact same destinations.
    apply_following_ops(merged, diff.get("following_ops"))

    # Non-discrete matter is located while onset contact still stands.  That
    # ordering is causal: a release can occur through an interior relation and
    # the bodies can withdraw later in the same beat.  Deriving after contact
    # removals would erase the route that established the destination.
    apply_substance_ops(merged, diff.get("substance_ops"),
                        report=substance_report)

    apply_contact_ops(merged, diff.get("contact_ops"),
                      report=contact_report)
    normalize_scene_contacts(merged)

    # Within-room position, last of all. Contact is settled by now, and contact
    # is what the derivation reads: a hand on the quilt is a body at the bed.
    # Then the same hygiene as before -- prune a stale anchor (which auto-heals
    # a room move), drop non-co-located `near` links, symmetrize what survives.
    derive_scene_stations(merged, diff.get("stations"), diff.get("contact_ops"))
    merged.setdefault("stations", {})
    normalize_scene_stations(merged)
    normalize_scene_poses(merged)

    # Channels, after rooms have settled: a channel names rooms, so it can only
    # be pruned once this beat's room retirements are known.
    apply_comms_ops(merged, diff.get("comms_ops"))
    normalize_scene_comms(merged)

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
