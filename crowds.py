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

#: The world-KV key crowds live under, spelled once. It is frame-scoped in
#: `db.FRAME_SCOPED_WORLD_KEYS`: a branch that never went to the market must
#: not inherit the market's throng.
CROWDS_WORLD_KEY = "crowds"

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


#: What a crowd presents to the spatial layer, in the barrier vocabulary
#: `spatial.py` already folds words into. Nothing new is invented here on
#: purpose: `membrane` is ALREADY passable and already absent from
#: `_SIGHT_BARRIERS` -- you push through it and you cannot see across it --
#: and its own comment in spatial glosses it as "a curtain, a tent flap, a
#: body's soft wall". The vocabulary anticipated bodies.
_TERRAIN = {LOOSE: "open", PACKED: "membrane", CRUSH: "membrane"}

#: What the press does to someone who does nothing. `pull` is a tendency the
#: Director may honour or override; `carry` is the press winning by default.
#: Both are OFFERS -- see `drift`.
PULL = "pull"
CARRY = "carry"


def terrain(band, room_size):
    """The barrier a crowd of this density is, for passage and for sight.

    Loose is open ground with people on it. Packed and a crush are both a
    membrane, and they differ in the CURRENT rather than in the wall -- see
    `drift`. This is the deterministic half of §5a and it belongs here rather
    than in `spatial.py` because a crowd is world state, not scene geometry:
    the room does not know it is full.
    """
    return _TERRAIN[density(band, room_size)]


def drift(crowd, room_size):
    """What the press OFFERS to do to a body standing in it: None, or
    {toward, strength}.

    Every barrier in this engine is inert -- it permits or it refuses. A crowd
    imposes its own movement on whoever is inside it, and that is the one
    genuinely new concept, which is why it is named rather than smuggled in as
    a special case of passability. Passability answers "may I"; drift answers
    "what happens if I do nothing".

    **This function never moves anybody.** It returns an offer, and the
    Director resolves it. `_guard_approach_is_not_arrival` exists because a
    beat describing approach and a beat placing a body somewhere are different
    things, and conflating them wrote positions nobody declared. A crowd
    carrying someone is exactly an arrival the player did not declare, so it
    goes through the commit path and shows up in the state diff like any other
    move. A crowd that moved someone quietly would be that same defect with a
    worse cause -- the player would have reason to believe they had moved
    themselves.

    A crowd with nowhere to go has no current. A stationary crush is a wall
    with good prose, and pretending otherwise would push bodies around a room
    for no reason anyone could point at.
    """
    if not isinstance(crowd, dict):
        return None
    toward = str(crowd.get("heading") or "").strip()
    if not toward:
        return None
    packed = density(crowd.get("band"), room_size)
    if packed == CRUSH:
        return {"toward": toward, "strength": CARRY}
    if packed == PACKED:
        return {"toward": toward, "strength": PULL}
    return None


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


#: The ops a Director may write. `emerge` and `absorb` land LAST by design:
#: they are the pair that touches what the story will still be able to say
#: about a person after the scene ends, and the cheap half had to earn them.
OP_SET = "set"
OP_MOVE = "move"
OP_SPLIT = "split"
OP_DISPERSE = "disperse"
OP_EMERGE = "emerge"
OP_ABSORB = "absorb"
_OPS = (OP_SET, OP_MOVE, OP_SPLIT, OP_DISPERSE, OP_EMERGE, OP_ABSORB)

#: How many crowds one era may hold at once. Not a cost limit -- a crowd is one
#: row and costs nothing to carry. It is a coherence limit: past this the
#: Director is populating rooms nobody is standing in, and the perception
#: surface only ever shows the observer's own room anyway.
MAX_CROWDS = 8


def _op_word(value):
    word = " ".join(str(value or "").split()).casefold()
    return word if word in _OPS else ""


def apply_ops(crowds, ops, *, chat_id, turn, known_rooms, roster=(), spoken=()):
    """Fold Director crowd ops into the crowd list. Pure; returns
    ``(crowds, rejected)``.

    Deterministic validation lives HERE rather than at the commit seam so it
    can be tested without a database, and so there is one place that decides
    what a crowd may be -- the alternative is a guard every caller must
    remember, which this project's history says is a guard that gets forgotten.

    Two rules do the real work:

    **A `crowd_id` the engine did not mint is refused, never created.** The
    model may only name a uid it was shown, and it is shown them by
    `agents.common.crowds_for_room`. Minting under a model-authored key is how
    five ledgers ended up keyed by display name, and a crowd is a new writer:
    the wrong key space at birth is exactly what subject identity exists to
    stop.

    **A room nobody authored is refused.** A crowd in an unknown room would be
    invisible to every observer (perception is room-scoped) while still
    occupying a slot -- a silent no-op, which is worse than a rejection nobody
    can see.

    A bad `heading` does NOT sink the op it rides on. Where the crowd IS was
    declared; where it is drifting is a flourish, and losing the flourish is
    cheaper than losing the crowd.
    """
    out = [dict(c) for c in (crowds or []) if isinstance(c, dict)]
    rooms = {str(r) for r in (known_rooms or ()) if str(r or "")}
    rejected = []
    by_uid = {str(c.get("uid") or ""): c for c in out}

    for raw in (ops or []):
        if not isinstance(raw, dict):
            rejected.append("crowd op was not an object")
            continue
        op = _op_word(raw.get("op") or OP_SET)
        if not op:
            rejected.append("unknown crowd op %r" % (raw.get("op"),))
            continue

        # `absorb` names a person rather than a crowd -- whoever they came out
        # of is the engine's to remember, not the model's to re-state.
        if op == OP_ABSORB:
            out, reason = absorb(out, raw.get("who"), spoken=spoken)
            by_uid = {str(c.get("uid") or ""): c for c in out}
            if reason:
                rejected.append(reason)
            continue

        uid = str(raw.get("crowd_id") or "").strip()
        room = str(raw.get("room") or "").strip()
        heading = str(raw.get("heading") or "").strip()
        if heading and heading not in rooms:
            rejected.append("dropped heading %r: no such room" % heading)
            heading = ""

        target = by_uid.get(uid) if uid else None
        if uid and target is None:
            rejected.append("no crowd %r; refusing to mint one under it" % uid)
            continue

        if op == OP_SET and target is None:
            if room not in rooms:
                rejected.append("crowd in unknown room %r" % room)
                continue
            composition = " ".join(str(raw.get("composition") or "").split())
            if not composition:
                rejected.append("crowd in %r has no composition" % room)
                continue
            if len(out) >= MAX_CROWDS:
                rejected.append("at the %d-crowd ceiling; %r not minted"
                                % (MAX_CROWDS, composition))
                continue
            crowd = new_crowd(chat_id, room, band=raw.get("band"),
                              composition=composition, since_turn=turn,
                              mood=raw.get("mood"), heading=heading or None)
            if crowd["uid"] in by_uid:
                rejected.append("crowd %r already stands in %r"
                                % (composition, room))
                continue
            out.append(crowd)
            by_uid[crowd["uid"]] = crowd
            continue

        if target is None:
            rejected.append("crowd op %r names no crowd" % op)
            continue

        if op == OP_EMERGE:
            out, reason = emerge(out, uid, raw.get("who"), roster=roster)
            by_uid = {str(c.get("uid") or ""): c for c in out}
            target = by_uid.get(uid)
            if reason:
                rejected.append(reason)
            continue

        if op == OP_DISPERSE:
            out = [c for c in out if c is not target]
            by_uid.pop(uid, None)
            continue

        if op == OP_SPLIT:
            half = split_band(target.get("band"))
            if half is None:
                rejected.append("a handful does not divide")
                continue
            if not heading:
                rejected.append("a split needs somewhere for the half to go")
                continue
            if len(out) >= MAX_CROWDS:
                rejected.append("at the %d-crowd ceiling; no split"
                                % MAX_CROWDS)
                continue
            target["band"] = half
            peeled = new_crowd(chat_id, target.get("room_uid"), band=half,
                               composition=target.get("composition"),
                               since_turn=turn, mood=target.get("mood"),
                               heading=heading)
            # Band-preserving splitting gives both halves the same band and the
            # same composition in the same room, so the uid material is
            # identical to its parent's but for the turn -- and a split on the
            # turn the parent was minted collides. Recorded origin doubles as
            # the disambiguator.
            peeled["uid"] = crowd_uid(chat_id, target.get("room_uid"), turn,
                                      "%s|from:%s"
                                      % (target.get("composition"),
                                         target.get("uid")))
            peeled["from_uid"] = str(target.get("uid") or "")
            out.append(peeled)
            by_uid[peeled["uid"]] = peeled
            continue

        if op == OP_MOVE:
            if room not in rooms:
                rejected.append("crowd moved to unknown room %r" % room)
                continue
            target["room_uid"] = room
            target["heading"] = None if heading == room else (heading or None)
            continue

        # op == OP_SET on a crowd that already exists: an edit in place.
        if room:
            if room not in rooms:
                rejected.append("crowd set into unknown room %r" % room)
                continue
            target["room_uid"] = room
        if raw.get("band"):
            target["band"] = normalize_band(raw.get("band"))
        if raw.get("composition"):
            target["composition"] = \
                " ".join(str(raw.get("composition")).split())[:120]
        if raw.get("mood") is not None:
            target["mood"] = " ".join(str(raw.get("mood") or "").split())[:24]
        if heading:
            target["heading"] = heading

    return out, rejected


def emerge(crowds, uid, who, *, roster=()):
    """Someone steps out of the crowd. Pure; returns ``(crowds, reason)``.

    Emergence needs far less new machinery than it looks like, because
    `commit.track_background_presences` ALREADY discovers anyone the Director
    gives a dialogue line or an entity def to. Building a second writer for the
    person would be building a second identity space for them, which is the
    defect this whole module is written around. So what this records is the one
    thing that path cannot know: that the stranger came OUT of the crowd rather
    than having been standing there all along.

    **A crowd may never emerge a named character.** It produces strangers. If
    the Director wants a cast member in the square, they ARRIVE -- a cast
    member emerging from the extras is indistinguishable in the record from one
    who was always there, and that is a canon write nobody authored.

    **The band does not move.** A throng minus one is a throng; a handful minus
    one is still a handful. Bands are coarse precisely so that nothing has to
    do arithmetic on them, and subtracting a person from a word is the
    conservation bookkeeping the band exists to refuse.
    """
    out = [dict(c) for c in (crowds or []) if isinstance(c, dict)]
    name = " ".join(str(who or "").split())
    if not name:
        return out, "an emergence with no one in it"
    known = {str(n or "").casefold() for n in (roster or ())}
    if name.casefold() in known:
        return out, ("%s is a named character; a crowd produces strangers, "
                     "and someone the story already knows arrives" % name)
    for crowd in out:
        if str(crowd.get("uid") or "") != str(uid or ""):
            continue
        emerged = [str(n) for n in (crowd.get("emerged") or [])]
        if name.casefold() in {n.casefold() for n in emerged}:
            return out, "%s has already stepped out of that crowd" % name
        crowd["emerged"] = emerged + [name]
        return out, ""
    return out, "no crowd %r for anyone to step out of" % uid


def absorb(crowds, who, *, spoken=()):
    """Someone who only acted goes back into the crowd. Pure; returns
    ``(crowds, reason)``.

    **Emergence is one-way for anyone who speaks.** Once a line is attributed
    to someone the story has a record of them: `dialogue_log` outlives the
    scene, `track_background_presences` is already counting their mentions, and
    an owed reply may be keyed to their name. Re-absorbing them would delete a
    person the record still points at. Someone who merely stepped aside or
    looked up left nothing behind and may go back.

    The test is not "did they matter" but "does anything durable now name
    them", which is a question deterministic code can answer and a model
    cannot be trusted to.
    """
    out = [dict(c) for c in (crowds or []) if isinstance(c, dict)]
    name = " ".join(str(who or "").split())
    if not name:
        return out, "an absorption with no one in it"
    if name.casefold() in {str(n or "").casefold() for n in (spoken or ())}:
        return out, ("%s has spoken; the story has a record of them and they "
                     "cannot go back into the crowd" % name)
    for crowd in out:
        emerged = [str(n) for n in (crowd.get("emerged") or [])]
        kept = [n for n in emerged if n.casefold() != name.casefold()]
        if len(kept) != len(emerged):
            crowd["emerged"] = kept
            return out, ""
    return out, "%s did not come out of any crowd" % name


def advance_crowds(crowds, neighbors):
    """Move every crowd that has somewhere to be one room along. Pure;
    returns ``(crowds, moves)``.

    A crowd's `heading` is an ADJACENT room rather than a destination across
    the map, and it moves on the same graph everyone else walks -- no second
    pathfinder, which is the one thing §5 asks for. A market thins toward the
    gate because the Director said the gate; it does not compute a route to
    the harbour.

    A heading into a room that is no longer adjacent is dropped rather than
    honoured. The scene is edited between beats and a crowd should not walk
    through a wall that appeared while it was deciding.
    """
    out = []
    moves = []
    for crowd in (crowds or []):
        if not isinstance(crowd, dict):
            continue
        crowd = dict(crowd)
        here = str(crowd.get("room_uid") or "")
        toward = str(crowd.get("heading") or "")
        if toward and toward != here:
            if toward in (neighbors.get(here) or ()):
                crowd["room_uid"] = toward
                moves.append({"uid": crowd.get("uid"), "from": here,
                              "to": toward})
            crowd["heading"] = None
        elif toward == here:
            crowd["heading"] = None
        out.append(crowd)
    return out, moves


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
