# spatial_senses.py
"""What reaches a perceiver: comms channels, sight grading, hearing with its
material ladder and bearing, scent, and perceiver acuity."""

import re
from typing import Optional

from world.spatial_orientation import (
    normalize_vertical,
    opposite_bearing,
    opposite_vertical,
    relative_bearing,
    travel_bearing,
)

from world.spatial_barriers import _SIGHT_BARRIERS, normalize_barrier
from world.spatial_containment import (_body_interior_holder, _shares_enclosure,
                                 containment_conceals)
from world.spatial_contacts import contacts_of
from world.spatial_geometry import (
    _anchor_dir,
    _relative_sector,
    _sector_label,
    crossing_of,
    door_anchor_id,
    effective_facing,
    effective_room_size,
    effective_station,
    proximity_rel,
)
from world.spatial_identity import _ci_get, room_of, same_subject
from world.spatial_light import SIGHT_LEVELS, _LIGHT_SIGHT, light_at, normalize_light
from world.spatial_routing import rooms_adjacent, spatial_rel


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
