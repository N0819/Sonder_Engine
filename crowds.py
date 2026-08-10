"""Crowds: one object with many people in it.

A market square with forty people cannot be represented today. `max_managed`
defaults to 6 and is hard-capped at 8, so a populous place either eats the
whole manager budget or is silently absent -- and chat 57 spent three of those
six slots on ONE Dalek, split three ways by its article. `scene.py` already
says what the answer is, in prose, and has never had an object: "past that, a
crowd is better represented as one chorus presence than as several
individually-voiced extras."

So a crowd is a single row that costs the same whatever it contains, and it
**must never consume a managed-presence slot** -- if it does it has solved
nothing.

Design notes that are load-bearing rather than stylistic:

**The count is a BAND, not an integer.** The moment two sources disagree about
whether 37 people became 34 there is a contradiction with no resolution, and
this project's rule is that contradiction becomes a dispute rather than an
average. Bands also make splitting free, and are what prose actually needs --
nobody writes "thirty-seven dockworkers".

**Density is DERIVED, never stored.** It is a function of the band and the
ROOM: forty across a market square is loose and walkable, the same forty in a
gate passage is a crush. Storing it would be a second source of truth that
drifts the moment the crowd moves -- the `wearing`/`state`/`regions` scar,
which this module is written after rather than before.

**`uid`, never a display name.** Five ledgers in this engine already key beings
by display name and it is one defect, not five. A crowd is a new writer, and a
new writer into the wrong key space is exactly what subject identity exists to
stop.

This module is PURE: dicts in, dicts out, no database. Persistence and the
perception surface live with their own seams.
"""

from __future__ import annotations

import hashlib

#: How many, coarsely. Ordered; the index is the rank.
BANDS = ("a handful", "a dozen or so", "a few dozen", "a throng")

#: How big the room is. Ordered; the index is the rank. `RoomDef.size` is a
#: free string and 66 of the live corpus's rooms leave it unset, so an unknown
#: size is treated as `medium` rather than refused -- an unsized room is the
#: commonest room, and a crowd that vanished in one would be a worse answer
#: than a crowd of ordinary density.
ROOM_SIZES = ("tiny", "small", "medium", "large", "huge", "vast")
DEFAULT_ROOM_SIZE = "medium"

#: `spatial._ROOM_COST` looks like this rank and is NOT: it collapses tiny,
#: small, "" and medium all to 1, because it prices WALKING rather than
#: describing extent. Reusing it would make a crush in a broom cupboard read
#: the same as one in a hall.
CRUSH = "crush"
PACKED = "packed"
LOOSE = "loose"


def normalize_band(value):
    """The nearest known band, or the smallest when nothing matches.

    Falling back to the smallest is deliberate: a crowd the engine cannot size
    should read as fewer people rather than more, because over-claiming a
    throng puts bodies in a room that nothing authored.
    """
    text = " ".join(str(value or "").split()).casefold()
    for band in BANDS:
        if text == band:
            return band
    return BANDS[0]


def band_rank(band):
    return BANDS.index(normalize_band(band)) + 1


def room_size_rank(size):
    text = " ".join(str(size or "").split()).casefold()
    if text not in ROOM_SIZES:
        text = DEFAULT_ROOM_SIZE
    return ROOM_SIZES.index(text) + 1


def density(band, room_size):
    """`crush` | `packed` | `loose`, from the band against the room.

    The property worth having is that the crowd does not decide to release
    you -- the room does. A few dozen in a gate passage is a crush; pushed
    through into the square beyond, the same crowd is loose, and the escape
    that was impossible in the gateway is simply available because the
    geometry changed and nothing else did.
    """
    difference = band_rank(band) - room_size_rank(room_size)
    if difference >= 1:
        return CRUSH
    if difference == 0:
        return PACKED
    return LOOSE


def split_band(band):
    """The band each half gets when a crowd divides.

    BAND-PRESERVING, not count-preserving: "a few dozen" splitting toward two
    exits gives "a dozen or so" and "a dozen or so". No arithmetic, no
    conservation bookkeeping, and therefore no drift. The smallest band does
    not divide -- a handful that splits is two smaller things the story has no
    word for, so it stays whole and the Director may move it instead.
    """
    rank = band_rank(band)
    if rank <= 1:
        return None
    return BANDS[rank - 2]


def crowd_uid(chat_id, room_uid, since_turn, composition):
    """A stable id minted once, from what the crowd IS rather than what it is
    called. Never a display name."""
    material = "|".join([
        str(int(chat_id)), str(room_uid or ""), str(int(since_turn)),
        " ".join(str(composition or "").split()).casefold(),
    ])
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
    return "crowd:%s" % digest


def new_crowd(chat_id, room_uid, *, band, composition, since_turn,
              mood="", heading=None):
    """One crowd. `density` is absent by construction -- see the module note."""
    return {
        "uid": crowd_uid(chat_id, room_uid, since_turn, composition),
        "room_uid": str(room_uid or ""),
        "band": normalize_band(band),
        "composition": " ".join(str(composition or "").split())[:120],
        "heading": str(heading) if heading else None,
        "mood": " ".join(str(mood or "").split())[:24],
        "since_turn": int(since_turn),
    }


def crowds_in_room(crowds, room_uid):
    """Every crowd currently in one room, in a stable order."""
    room = str(room_uid or "")
    if not room:
        return []
    return sorted(
        (c for c in (crowds or [])
         if isinstance(c, dict) and str(c.get("room_uid") or "") == room),
        key=lambda c: str(c.get("uid") or ""))


def describe(crowd, room_size):
    """One phrase for a prompt or a panel: what an observer registers.

    Deliberately not a line of dialogue and not a count. A crowd murmurs; it
    does not speak, and anyone who speaks has emerged and is no longer part of
    it.
    """
    if not isinstance(crowd, dict):
        return ""
    band = normalize_band(crowd.get("band"))
    composition = str(crowd.get("composition") or "people").strip()
    packed = density(band, room_size)
    phrase = "%s %s" % (band, composition)
    if packed == CRUSH:
        phrase += ", packed shoulder to shoulder"
    elif packed == PACKED:
        phrase += ", filling the space"
    mood = str(crowd.get("mood") or "").strip()
    if mood:
        phrase += " (%s)" % mood
    return phrase
