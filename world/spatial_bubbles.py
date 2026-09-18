"""Causality-bubble detectors: the two questions `spatial_frames.py` cannot
currently ask, as pure functions.

`spatial_frames.detect_split` answers "have two PLAYERS separated" -- it
refuses outright unless the chat has an attached extra persona and the
primary player is standing in a zoned room. `detect_merge` answers "are the
two parties CO-LOCATED again" -- a shared zone or a shared room id
(`_parties_share_a_room`). Both are about humans, and both are about
standing in the same place.

A causality bubble is about neither. It fires for a MAJOR CHARACTER who
walks away with no player attached to them, and it is opened, pre-empted
and ended by a VOICE CHANNEL rather than by co-location. This module holds
those detectors, and only the detectors:

    bubble_split_decision   the non-persona sibling of detect_split
    couple_decision         a live channel now joins two frames
    uncouple_decision       the channel is gone; the couple should end

NOTHING HERE HAS SIDE EFFECTS. The three functions above are pure functions
of constructed scenes and name lists; `detect_bubble` and
`detect_couple_between_frames` at the bottom are read-only gatherers that
fetch those arguments out of the database and call the pure core. The
drivers that ACT on a decision -- `spatial_frames.perform_split`,
`open_couple`, `close_couple` -- live in `spatial_frames.py`, which is
where every other write to a frame already lives.

WHY THE PREDICATE IS `comms_link` AND NOTHING ELSE. A channel already
decides liveness (`live`), direction (`_comms_transmits`'s broadcast
`source` check), where a handset physically is (`_comms_carrier_room`) and
who in the room overhears it (`_comms_delivers`). Asking whether two frames
are joined is therefore not a new judgement -- it is the existing question
asked across a pair of scenes instead of within one. There is no prose read
here, no word list, and no new notion of "far".

WHY THE FUSED VIEW CARRIES NO ROOMS. `comms_link` reads `scene["rooms"]`
for exactly one thing: the suppression clause that refuses to put a radio
between two bodies an ordinary voice already reaches. Two bodies in two
frames are never that pair -- a frame split is the engine's own statement
that they are not within earshot -- so the clause must not fire, and an
empty room map is what guarantees it cannot. Everything else `comms_link`
needs is in `positions` and `comms`. The room dicts -- the expensive,
collision-prone half -- would have to be fused to ACT on the answer, which
is why the room-id collision check below is a refusal rather than a merge
strategy.
"""

from __future__ import annotations

from world.spatial import comms_link, room_of
from world.spatial_frames import _effective_zone


# --------------------------------------------------------------- fusing comms
#
# Each frame's scene carries its OWN copy of `scene["comms"]`: `perform_split`
# seeds the child with `{**scene, ...}`, so both sides start from identical
# channel records and then diverge independently as each side's Director
# writes `comms_ops` into its own frame.
#
# Reconciling two divergent copies of one channel needs a rule, and the rule
# has to be stated in the direction that cannot invent a voice:
#
#   * SILENCE IS NOT REFUSAL. A channel present on only one side still counts.
#     A radio picked up after the split is written into the frame of whoever
#     picked it up and nowhere else, so requiring both sides to attest would
#     make a couple essentially unopenable from the away side -- the exact
#     case the feature exists for.
#   * HANGING UP IS. `live: False` on EITHER side vetoes the channel. An
#     explicit close is a positive act somebody performed; the other side's
#     stale open copy must not undo it.
#   * A CONTESTED CHANNEL IS NO CHANNEL. If both sides carry the same id with
#     different endpoints, mode, source or privacy, there is no fact of the
#     matter about which endpoints it joins, and picking one silently (what
#     `{**a, **b}` would do) is how a voice ends up somewhere it never went.
#     Refuse it.

_CONTESTED_FIELDS = ("rooms", "carriers", "mode", "source", "private")


def _channel_copies(scene_a, scene_b, channel_id):
    out = []
    for scene in (scene_a, scene_b):
        chans = (scene or {}).get("comms")
        chan = chans.get(channel_id) if isinstance(chans, dict) else None
        if isinstance(chan, dict):
            out.append(chan)
    return out


def fuse_comms(scene_a, scene_b):
    """The channels both frames can be held to, as one `comms` dict.

    Pure. Returns `{}` when nothing survives; never mutates either input.
    """
    ids = []
    for scene in (scene_a, scene_b):
        chans = (scene or {}).get("comms")
        if isinstance(chans, dict):
            for cid in chans:
                if str(cid) not in ids:
                    ids.append(str(cid))

    fused = {}
    for cid in ids:
        copies = _channel_copies(scene_a, scene_b, cid)
        if not copies:
            continue
        if any(not c.get("live") for c in copies):
            continue                                    # somebody hung up
        if len(copies) == 2 and any(
                copies[0].get(f) != copies[1].get(f) for f in _CONTESTED_FIELDS):
            continue                                    # contested; no fact
        fused[cid] = dict(copies[0])
    return fused


# ------------------------------------------------------ the crossing predicate


def _cross_link(scene, names_a, names_b):
    """The first live channel carrying a voice between the two name sets, as
    `(channel, speaker, observer)`, or None.

    Both endpoints must be POSITIONED. A body the scene cannot place has no
    room, and a couple opened on a body that is nowhere would have nothing to
    partition back, so this fails closed instead. `comms_link` refuses the
    same pair on its own (an endpoint named but unplaceable is not an end of
    a channel); this is the same rule stated where the decision is made,
    because a detector that depends on a predicate's refusal without saying
    so breaks silently when the predicate is widened.

    Names are visited in sorted order so the answer depends on the scene and
    not on the order a caller happened to build its lists in.
    """
    if not isinstance(scene, dict):
        return None
    for a in sorted(str(n) for n in (names_a or []) if n):
        room_a = room_of(scene, a)
        if not room_a:
            continue
        for b in sorted(str(n) for n in (names_b or []) if n):
            if a.casefold() == b.casefold():
                continue
            room_b = room_of(scene, b)
            if not room_b:
                continue
            for speaker, observer, s_room, o_room in (
                    (a, b, room_a, room_b), (b, a, room_b, room_a)):
                channel = comms_link(scene, s_room, o_room,
                                     speaker_name=speaker,
                                     observer_name=observer)
                if channel:
                    return (channel, speaker, observer)
    return None


def _occupied_rooms(scene, names=None):
    """Every room id a body stands in, in one scene.

    `names=None` means every key in `positions`, not just the party -- an
    unattached body holding a radio is still a body the fused scene would
    have to place.
    """
    positions = (scene or {}).get("positions") or {}
    keys = list(positions.keys()) if names is None else [
        str(n) for n in names if n]
    rooms = set()
    for name in keys:
        room = room_of(scene, name)
        if room:
            rooms.add(room)
    return rooms


# --------------------------------------------------------- 1. the bubble split


def in_range_rooms(scene, party_names, *, hops=1):
    """The rooms the player's beat attends to -- the PLAYER'S CAUSALITY BUBBLE.

    `spatial.attended_rooms` is the same arithmetic that decides which rooms a
    stage payload carries (`agents/common._contextual_rooms`), asked from the
    human party's standing places instead of from the whole cast's. So "inside
    the Director's range" and "in the Director's payload" are one answer, and
    cannot drift into two.
    """
    from world.spatial import attended_rooms

    centers = set()
    for name in (party_names or []):
        room = room_of(scene, str(name)) if name else None
        if room:
            centers.add(room)
    if not centers:
        return None                      # no reference frame; see refusal 3
    return set(attended_rooms(scene, centers, hops=hops,
                              names=[str(n) for n in (party_names or []) if n]))


def _clusters(scene, names, *, hops=1):
    """The away bodies grouped by whether they are in each other's range.

    TWO PEOPLE WHO WALKED OFF IN DIFFERENT DIRECTIONS ARE TWO THREADS. One
    frame for both would put them in a room together without either of them
    moving, which is the same information expansion a careless fuse makes,
    pointing the other way. The grouping question is the range question asked
    among themselves -- the primitive is already here -- so there is one
    notion of "together" in this module rather than two.
    """
    from world.spatial import attended_rooms

    groups = []
    for name in sorted(str(n) for n in (names or []) if n):
        room = room_of(scene, name)
        if not room:
            continue
        reach = set(attended_rooms(scene, {room}, hops=hops))
        for group in groups:
            if room in group["rooms"] or group["reach"] & {room} or \
                    reach & group["rooms"]:
                group["names"].append(name)
                group["rooms"].add(room)
                group["reach"] |= reach
                break
        else:
            groups.append({"names": [name], "rooms": {room}, "reach": reach})
    return groups


def bubble_split_decision(scene, *, party_names, cast_names,
                          frame_is_live_spatial=False, paradox_active=False,
                          hops=1):
    """Should a major character get a causality bubble of their own?

    Pure: a function of the scene, the bodies each side answers for, and two
    flat facts about the frame. Returns `None`, or
    `{"kind": "bubble", "characters": [...], "rooms": [...]}`.

    THE RULE IS ONE SENTENCE: a cast body the beat does not attend to has left
    the player's causality bubble, and gets its own. Attending is
    `spatial.attended_rooms` -- where the human party stands, the rooms one
    step off them, and the far end of any live two-way channel reaching those
    -- which is the same set the Director is shown. A body in the payload is
    in range; a body outside it is outside the beat.

    ZONES ARE NO LONGER THE TRIGGER (owner ruling, 2026-09-17: "whenever they
    are outside the player causality bubble"). A declared `zone` was the
    ORIGINAL trigger and it had a defect this replaces rather than tunes: it
    required somebody to have LABELLED the away place. Measured live the same
    day, `google/gemini-3.8-flash`, the Millbrook story: a courier accepted an
    errand across the water, walked out of the tap room, and got no bubble,
    because the road she walked down carried no zone and nobody had thought to
    give it one. The engine could not tell she had gone. A second run only
    produced a bubble because the landing she reached had been authored with
    one by hand. Range is derived from where bodies actually are, so nothing
    has to be labelled for it to be true.

    `spatial_frames.detect_split` keeps the zone rule, deliberately and
    unchanged: it answers whether two PLAYERS have separated, a split it
    cannot undo cheaply, and a declared locale is the positive evidence that
    one is intended. This answers a different question about a different
    subject and takes the cheaper, reversible answer.

    FIVE REFUSALS, and one that used to be here is gone:

      1. NESTED SPLIT. `detect_split` refuses "for an already-spatial frame
         (no nested splits in this slice)". A bubble inside a bubble has the
         same problem and takes the same answer.
      2. ACTIVE PARADOX. Same rule, same direction: a temporal wound in
         progress. These two mechanics must not cross.
      3. NO REFERENCE FRAME. Nobody the party answers for is standing
         anywhere, so there is no range to be outside of. Refuse rather than
         treat an unplaced party as a party that is nowhere near anyone.
      4. A BODY THE SCENE CANNOT PLACE. Nowhere is not away: a body with no
         room has nothing to partition into a frame, and `perform_split`
         would hand its new frame an empty scene.
      5. A HUMAN IS OUT THERE TOO. Then this is `detect_split`'s case, not
         this one, and firing both would produce exactly the nested split
         refusal 1 exists to forbid. Defer.

    THE CHANNEL REFUSAL IS GONE BECAUSE IT IS NOW STRUCTURAL. The zone-era
    rule needed a sixth refusal -- "an open channel already reaches them", on
    the ground that a mind answering over a comm channel from another room is
    already a full participant of the unsplit frame. `attended_rooms` folds a
    live two-way channel's far end into the range itself, so a body on the
    radio is IN range and is never a candidate. One rule where there were two,
    and the case the clause was written for is reached by construction rather
    than by remembering to check it.

    One decision per call, matching `detect_split`'s one-split-per-commit
    shape; a second cluster is next beat's question.
    """
    if frame_is_live_spatial or paradox_active:
        return None
    if not isinstance(scene, dict):
        return None

    party = [str(n) for n in (party_names or []) if n]
    in_range = in_range_rooms(scene, party, hops=hops)
    if in_range is None:
        return None                                     # refusal 3

    away = []
    for name in (str(n) for n in (cast_names or []) if n):
        room = room_of(scene, name)
        if not room:
            continue                                    # refusal 4
        if room not in in_range:
            away.append(name)
    if not away:
        return None

    for name in party:
        room = room_of(scene, name)
        if room and room not in in_range:
            return None                                 # refusal 5

    groups = _clusters(scene, away, hops=hops)
    if not groups:
        return None
    first = groups[0]
    # THE REACH, NOT JUST THE ROOM THEY STAND IN. A frame holding one room has
    # nowhere for its occupant to walk to, so her first beat would be a person
    # in a sealed box -- and the movement she is in the middle of is exactly
    # what a bubble exists to keep going. Same `attended_rooms` the trigger
    # used, so what she can reach and what counted as range are one function.
    return {"kind": "bubble", "characters": sorted(first["names"]),
            "rooms": sorted(first["reach"] | first["rooms"])}


# -------------------------------------------------------------- 2. the couple


def couple_decision(scene_a, names_a, scene_b, names_b, *,
                    paradox_active=False):
    """Does a live voice channel now join these two frames?

    Pure: a function of two scenes and the two name lists. Returns `None`, or
    `{"kind": "couple", "channel_id", "channel", "speaker", "observer"}`. The
    answer says which way the voice ran -- a broadcast reaches its receivers
    and hears nothing back -- so `speaker` is the side that can talk, and a
    couple may well be one-way.

    FOUR REFUSALS:

      1. ACTIVE PARADOX, mirroring `detect_split`'s. Opening a couple is a
         structural change to the frame graph, which is the thing a temporal
         wound must not be crossed with.
      2. NAME COLLISION. If one name is positioned in BOTH scenes, the fused
         `positions` dict cannot say which body it means, and
         `_comms_carrier_room` resolves carriers by name. Two bodies wearing
         one name is not a scene that can be fused.
      3. ROOM-ID COLLISION. `perform_split` gives the child every away-zoned
         AND every unzoned room while the parent keeps ALL rooms, so the two
         id spaces overlap by construction and then diverge independently. If
         an OCCUPIED room id appears on both sides, `{**a, **b}` would
         silently prefer one side's version of a room two different people
         are standing in. Fail closed.
      4. NO LINK. The predicate itself: no live, uncontested channel carries a
         voice from a positioned body on one side to a positioned body on the
         other, in either direction.
    """
    if paradox_active:
        return None
    if not isinstance(scene_a, dict) or not isinstance(scene_b, dict):
        return None

    pos_a = scene_a.get("positions") or {}
    pos_b = scene_b.get("positions") or {}
    if {str(k).casefold() for k in pos_a} & {str(k).casefold() for k in pos_b}:
        return None                                     # refusal 2
    if _occupied_rooms(scene_a) & _occupied_rooms(scene_b):
        return None                                     # refusal 3

    fused_comms = fuse_comms(scene_a, scene_b)
    if not fused_comms:
        return None
    fused = {"positions": {**pos_a, **pos_b}, "comms": fused_comms, "rooms": {}}

    found = _cross_link(fused, names_a, names_b)
    if not found:
        return None                                     # refusal 4
    channel, speaker, observer = found
    return {"kind": "couple", "channel_id": channel.get("id"),
            "channel": channel, "speaker": speaker, "observer": observer}


# ------------------------------------------------------------ 3. the uncouple


def uncouple_decision(scene, names_a, names_b):
    """Has the channel holding a couple together gone?

    Pure: a function of the COUPLE frame's own single scene plus the partition
    map recorded when the couple opened. Returns `None` while any live channel
    still carries a voice across the partition, else a decision carrying the
    reason it ended.

    TWO REASONS, AND CONFLATING THEM IS THE BUG THIS FUNCTION EXISTS TO AVOID.
    `comms_link` deliberately answers None for two people a voice already
    reaches without it. So the naive negation of `couple_decision` -- "no
    link, therefore uncouple" -- fires hardest exactly when the two parties
    have WALKED INTO THE SAME ROOM, and would tear into two frames a pair of
    people standing face to face. That is a reunion, and a reunion is
    `detect_merge`'s question, not this one. The decision therefore reports
    `reason` and the caller routes on it:

        "reunited"       a member of each side shares a room id. Do NOT
                         partition; the two frames are one party again and
                         the close is permanent.
        "channel_closed" the parties are still apart and nothing carries a
                         voice between them. Partition back to two frames.

    NO PARADOX ARGUMENT, deliberately, and this is the one asymmetry with the
    two detectors above. They refuse under a paradox because opening a frame
    is the risky direction. Ending a couple returns the world to MORE
    separation, not less, so a wound in progress is no reason to keep two
    parties fused.
    """
    if not isinstance(scene, dict):
        return None
    if _cross_link(scene, names_a, names_b):
        return None

    for a in sorted(str(n) for n in (names_a or []) if n):
        room_a = room_of(scene, a)
        if not room_a:
            continue
        for b in sorted(str(n) for n in (names_b or []) if n):
            if a.casefold() == b.casefold():
                continue
            if room_of(scene, b) == room_a:
                return {"kind": "uncouple", "reason": "reunited",
                        "shared_room": room_a, "who": [a, b]}
    return {"kind": "uncouple", "reason": "channel_closed",
            "shared_room": None, "who": []}


# ---------------------------------------------------- read-only DB gatherers
#
# These fetch the pure cores' arguments and nothing else. They perform no
# writes and schedule nothing. The decision is always the pure function's.


def detect_bubble(chat_id, frame_id, turn_idx=None):
    """`bubble_split_decision` against a live chat. Read-only.

    The signature mirrors `detect_split(chat_id, frame_id, turn_idx)`, whose
    `turn_idx` parameter is likewise never read in its body -- it is there for
    symmetry with `perform_split` at the call site -- so this keeps it
    optional rather than pretending to use it.
    """
    from core.db import wget_for_frame
    from core.frames import get_frame
    from story.character_schema import (character_name,
                                        normalized_character_from_text)
    from story.scene import active_cast
    from world.paradox import get_paradox
    from world.spatial_frames import _all_party_names

    scene = wget_for_frame(chat_id, "scene", frame_id, None)
    if not isinstance(scene, dict):
        return None

    # THE CHEAPEST REFUSAL FIRST, and it is the one almost every beat takes.
    # A story whose whole cast is standing with the player has nobody out of
    # range, and asking costs one already-loaded scene rather than a cast read
    # and a persona query. `_all_party_names` is one query; the range is pure
    # arithmetic over the scene in hand.
    party = _all_party_names(chat_id, frame_id)
    in_range = in_range_rooms(scene, party)
    if in_range is None:
        return None
    positions = scene.get("positions") or {}
    if not any(room not in in_range for room in positions.values() if room):
        return None

    # `normalized_character_from_text`, not `character_name(json.loads(...))`:
    # the same memo the four frame-surgery reads in `spatial_frames` use, and
    # for the same reason -- a card that will not parse must stop the split
    # rather than zone an unreadable body under a name it shares with every
    # other unreadable body.
    cast_names = [character_name(normalized_character_from_text(row["sheet"]))
                  for row in active_cast(chat_id, frame_id)]

    frame = get_frame(frame_id)
    return bubble_split_decision(
        scene,
        party_names=party,
        cast_names=[n for n in cast_names if n],
        frame_is_live_spatial=bool(
            frame and frame.get("kind") == "spatial"
            and frame.get("merged_turn_idx") is None),
        paradox_active=bool(get_paradox(chat_id, frame_id)),
    )


def frame_body_names(chat_id, frame_id):
    """Every named body one frame answers for: its human party plus its active
    cast. Read-only."""
    from story.character_schema import character_name, normalized_character_from_text
    from story.scene import active_cast
    from world.spatial_frames import _all_party_names

    names = list(_all_party_names(chat_id, frame_id))
    for row in active_cast(chat_id, frame_id):
        name = character_name(normalized_character_from_text(row["sheet"]))
        if name and name not in names:
            names.append(name)
    return names


def detect_couple_between_frames(chat_id, frame_a, frame_b):
    """`couple_decision` for two live frames of one chat. Read-only."""
    from core.db import wget_for_frame
    from world.paradox import get_paradox

    return couple_decision(
        wget_for_frame(chat_id, "scene", frame_a, {}) or {},
        frame_body_names(chat_id, frame_a),
        wget_for_frame(chat_id, "scene", frame_b, {}) or {},
        frame_body_names(chat_id, frame_b),
        paradox_active=bool(get_paradox(chat_id, frame_a)
                            or get_paradox(chat_id, frame_b)),
    )
