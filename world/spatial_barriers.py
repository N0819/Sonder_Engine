# spatial_barriers.py
"""Barrier vocabulary: normalising model-written barrier names into engine
vocabulary, and the class sets saying what a barrier passes."""

import re

from world.spatial_orientation import (
    normalize_bearing, normalize_vertical, opposite_bearing, opposite_vertical,
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
    "one-way window": "one_way_window",
    "one_way_mirror": "one_way_window",
    "one-way mirror": "one_way_window",
    "one way mirror": "one_way_window",
    "two_way_mirror": "one_way_window",
    "two-way mirror": "one_way_window",
    "two way mirror": "one_way_window",
    # `one_way_mirror` was ALSO already an alias for plain `window`, thirty
    # lines up, and this binding silently won on source order -- the reading
    # below is the one the engine has always had. The dead line is gone.
    #
    # NOT `observation_window`: it was already an alias for plain `window`
    # and it genuinely is ambiguous -- a hospital nursery's observation window
    # is glass both ways, an interrogation suite's is not. The word does not
    # decide, so it keeps the reading it had and the unambiguous spellings
    # below carry the one-way meaning.
    "mirrored_glass": "one_way_window",
    "mirrored glass": "one_way_window",
    "peephole": "one_way_window",
    "spy_hole": "one_way_window",
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
    # Stairs. A staircase is a way between two floors and nothing else -- a
    # body walks it, sight runs up it -- but no spelling of one was in this
    # table, so every stair in the database normalized to `wall` and sealed the
    # floor it joined. Live: `shrine_interior_first_floor` and its own upstairs
    # were walled apart across five consecutive rerolls while the mapping agent
    # authored the edge correctly every single time.
    "stair": "open",
    "stairs": "open",
    "staircase": "open",
    "stairway": "open",
    "stairwell": "open",
    "steps": "open",
    "ladder": "open",
    "ramp": "open",
    "path": "open",
    "ground": "open",
    "gap": "open",
    "opening": "open",
    "torii": "open",
    "gate": "open",
    # The entryway of a Japanese house. Used as a barrier value the model means
    # as "the way in through the genkan".
    "genkan": "open",
    "hatch": "open_door",
    "doors": "open_door",
    "double_doors": "open_door",
    "double doors": "open_door",
    "docking_port": "open_door",
    "airlock": "closed_door",
    "blast_door": "closed_door",
    "blast door": "closed_door",
    "pressure_door": "closed_door",
    "pressure door": "closed_door",
    "fire_door": "closed_door",
    "fire door": "closed_door",
    # A paper screen: what "shoji door" already meant, in the spellings the
    # model actually reaches for.
    "shoji": "closed_door",
    "shoji_screen": "closed_door",
    "shoji screen": "closed_door",
    "fusuma": "closed_door",
    "noren": "membrane",
    "partition": "wall",
    "bulkhead": "wall",
    "warded_door": "wall",
    "warded door": "wall",
}

# What a qualifier does to the family it is attached to. `open_shoji` and
# `hatch_open` were unrecognized as whole strings and so became walls, though
# both halves were understood: the model is describing the STATE of a known
# thing, not naming an unknown one.
_BARRIER_OPEN_FORM = {
    "wall": "open", "closed_door": "open_door", "membrane": "open_door",
    "open": "open", "open_door": "open_door", "window": "window",
    "bars": "bars", "separated": "open", "unknown": "open",
}
_BARRIER_CLOSED_FORM = {
    "open": "closed_door", "open_door": "closed_door", "wall": "wall",
    "closed_door": "closed_door", "membrane": "membrane", "window": "window",
    "bars": "bars", "separated": "separated", "unknown": "unknown",
}
_BARRIER_OPEN_QUALIFIERS = ("open", "unlocked", "ajar", "propped", "unbarred")
_BARRIER_CLOSED_QUALIFIERS = ("closed", "shut", "locked", "jammed", "stuck",
                              "padlocked", "blocked")
# Stronger than closed: the existing table already read `sealed_door` and
# `bolted_door` as walls, and a qualifier must not quietly promote one back to
# a door it can be opened through. `barred` is deliberately absent -- it is a
# FAMILY here (`bars`), not a state.
_BARRIER_SEAL_QUALIFIERS = ("sealed", "warded", "bolted", "welded", "bricked",
                            "boarded", "solid")
# A sealed anything is a wall, whatever it was before. Sight-passing families
# keep their sight: a welded-shut viewport is still glass.
_BARRIER_SEALED_FORM = {
    "window": "window", "bars": "bars",
    "open": "wall", "open_door": "wall", "closed_door": "wall",
    "membrane": "wall", "wall": "wall", "separated": "separated",
    "unknown": "wall",
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
    # Sight passes ONE WAY -- the direction the edge is declared in -- and not
    # back. A two-way mirror, an observation window, a peephole, a hunting
    # blind, a confessional screen. Every other barrier is a property of the
    # doorway rather than of the side you stand on, and that rule is right for
    # passage and for sound: sealing a stair from one end must not leave it
    # open from the other. It is WRONG for sight, and a real class of object
    # sat unrepresentable because of it.
    #
    # The asymmetry lives on the doorway too, which is why this is one barrier
    # value rather than a pair of contradicting declarations. `spatial_rel`
    # already reads the OBSERVER's own edge first, so the forward direction
    # needs nothing; what needed saying is that the way back is a wall.
    "one_way_window",
    "wall",
    "separated",
    "unknown",
}

# The three questions a barrier answers, kept apart because they genuinely
# differ. Conflating them is what left the engine with no way to say "you can
# see it but you cannot reach it" -- or, in `membrane`'s case, the reverse.
_SIGHT_BARRIERS = {"open", "open_door", "window", "bars", "one_way_window"}

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
#: barrier -> how much scent crosses it. Absent means none.
#:
#: A TABLE, not a set, because scent is the one channel of the four that is
#: GRADED: a closed door and a curtain both pass it, weakened, where sight and
#: passage are yes-or-no. Its three siblings above answer a membership
#: question and are sets; this one cannot, and pretending otherwise is what
#: made it decorative -- it was a set naming everything scent crosses AT ALL,
#: which `scent_level` could not use without restating the full/muffled split
#: itself. So it restated the whole rule, and the two were free to disagree.
#:
#: `scent_level` is now this table's only reader, and its only statement.
#: window and wall are deliberately absent: glass stops air, and a wall stops
#: everything. So is an unrecognized barrier, which normalizes to `wall`.
_SCENT_BARRIER_LEVELS = {
    "open": "full",
    "open_door": "full",
    "bars": "full",
    "membrane": "muffled",
    "closed_door": "muffled",
}


def _barrier_exact(key):
    """One lookup, both spellings. The table is written in both underscore and
    space forms and the model uses either."""
    for form in (key, key.replace("_", " "), key.replace(" ", "_")):
        if form in _BARRIER_ALIASES:
            return _BARRIER_ALIASES[form]
        if form in _VALID_BARRIERS:
            return form
    return None


def normalize_barrier(value: str | None, *, unresolved: set | None = None) -> str:
    """Normalize model-generated barrier names into engine vocabulary.

    The last line of this function used to be `return "wall"` for anything
    unrecognized, and a wall is the most restrictive answer the vocabulary has:
    nothing passes it and nothing sees through it. So every barrier word the
    table had not been taught became a sealed surface -- silently, with no
    warning and no way to tell an authored wall from an unread one. Measured
    over every director and mapping output in the live database: 250 of 1,716
    barrier declarations, 14.6%, were being turned into walls. The words lost
    were `staircase`, `narrow wooden staircase`, `shoji`, `open_shoji`,
    `genkan`, `open_archway`, `hatch_open` -- the parts a building is made of.

    So the phrase is FOLDED rather than enumerated, because a table that must
    be extended for every new spelling will always be one spelling behind:

    1. the exact string, in either spelling (unchanged, and still first);
    2. punctuation folded to one separator;
    3. a state qualifier applied to a understood family -- `open_shoji` is a
       shoji that is open, not an unknown thing;
    4. the head noun of the phrase, taken as the LAST understood token, which
       is where English puts it: `narrow wooden staircase` is a staircase.

    Only then `wall`. Pass `unresolved` to collect the raw words that reached
    that last line, so an unread barrier can be reported instead of quietly
    sealing a doorway.
    """
    raw = str(value or "").strip().casefold()
    direct = _barrier_exact(raw)
    if direct is not None:
        return direct

    key = re.sub(r"[^a-z0-9]+", "_", raw).strip("_")
    if not key:
        return "wall"
    folded = _barrier_exact(key)
    if folded is not None:
        return folded

    tokens = key.split("_")

    # 3. A qualifier on a known family. Either end: the model writes both
    # `open_shoji` and `hatch_open`.
    for qualifiers, form in ((_BARRIER_SEAL_QUALIFIERS, _BARRIER_SEALED_FORM),
                             (_BARRIER_OPEN_QUALIFIERS, _BARRIER_OPEN_FORM),
                             (_BARRIER_CLOSED_QUALIFIERS, _BARRIER_CLOSED_FORM)):
        for qualifier in qualifiers:
            if qualifier not in tokens or len(tokens) < 2:
                continue
            rest = [t for t in tokens if t != qualifier]
            base = _barrier_exact("_".join(rest))
            if base is None and len(rest) > 1:
                # The remainder may itself be a phrase -- `open_shoji_stair`.
                understood = [b for b in (_barrier_exact(t) for t in rest)
                              if b is not None]
                base = understood[-1] if understood else None
            if base is not None:
                return form.get(base, base)

    # 4. The head noun, which English puts last.
    understood = [b for b in (_barrier_exact(t) for t in tokens) if b is not None]
    if understood:
        return understood[-1]

    if unresolved is not None and raw:
        unresolved.add(raw)
    return "wall"


def unresolved_barrier_words(rooms) -> list:
    """Every barrier word in these rooms that nothing in the vocabulary reads.

    Reported rather than silently sealed: a doorway that becomes a wall because
    the engine could not read the word for it is indistinguishable, downstream,
    from a wall somebody meant.
    """
    seen = set()
    for room in (rooms or {}).values():
        if not isinstance(room, dict):
            continue
        for edge in (room.get("adjacent") or []):
            if isinstance(edge, dict) and edge.get("barrier"):
                normalize_barrier(edge.get("barrier"), unresolved=seen)
    return sorted(seen)

def normalize_scene_barriers(scene: dict) -> dict:
    """Normalize every adjacency barrier in a scene in place.

    Also drops a `passage_from` that names neither end of the edge it sits on
    -- the same refusal `sight_direction` makes for `sight_from`, and for the
    same reason. A direction has to name one of the two rooms to be a
    direction; a value naming the doorway, the mechanism, or a room somewhere
    else would otherwise seal the passage from BOTH sides silently, which is
    the one failure a directed edge must never have.
    """
    if not isinstance(scene, dict):
        return scene

    for room_id, room in (scene.get("rooms") or {}).items():
        if not isinstance(room, dict):
            continue

        adjacency = room.get("adjacent")
        if not isinstance(adjacency, list):
            room["adjacent"] = []
            continue

        for edge in adjacency:
            if not isinstance(edge, dict):
                continue
            edge["barrier"] = _barrier_against_its_own_name(
                normalize_barrier(edge.get("barrier")), edge.get("name"))
            named = passage_direction(edge)
            if named and named not in (str(room_id), str(edge.get("to"))):
                edge.pop("passage_from", None)

    return scene


#: Words that only ever name an OPENING. Deliberately short: every one of
#: these is a thing you go through, and none of them has a second sense that
#: could name a solid surface. "Gate" and "arch" are in; "panel", "screen" and
#: "partition" are not, because each of those is as often the thing that stops
#: you as the thing that lets you past.
_OPENING_WORDS = re.compile(
    r"\b(?:door|doors|doorway|doorways|archway|arch|hatch|gate|gateway|"
    r"entrance|entry|exit|opening|threshold|stairs|staircase|stairway|"
    r"ladder|portal)\b", re.IGNORECASE)


def _barrier_against_its_own_name(barrier, name):
    """An edge named as an opening cannot be a wall.

    A `wall` is the most restrictive answer the vocabulary has -- nothing
    passes it, nothing sees through it -- and an edge that carries a NAME is
    already claiming to be something. Live (chat 74): the hotel elevator was
    minted with `{'to': lobby, 'barrier': 'wall', 'name': 'lobby doors'}` and
    a single open edge to the third floor, so the car was reachable from above
    and sealed from below. The player declared "you step into the elevator",
    the movement backstop correctly refused to walk her through a wall, and
    her companion -- whose position came from the resolve diff, which is not
    route-checked -- went in without her. They spent the next beat in
    different rooms, which is why nothing she did reached him.

    DOWNGRADED TO `closed_door`, NOT OPENED. The name is evidence that a way
    through exists; it is not evidence that the way is open. A closed door
    still blocks this beat, still has to be opened by an action the resolve
    owns, and still cannot be walked through by either the player or the
    backstop -- so this grants no passage. What it removes is the PERMANENT
    seal, and with it the class of map where a room can only be left in one
    direction.
    """
    if barrier != "wall":
        return barrier
    if not _OPENING_WORDS.search(str(name or "")):
        return barrier
    return "closed_door"


_PASSABLE_BARRIERS = {"open", "open_door", "membrane"}


#: The edges a REMEMBERING MIND records as routes: a way I could go through,
#: now or by opening it (docs/UNBUILT.md 1.6).
#:
#: Neither existing set answers that question. `_SIGHT_BARRIERS` means "can
#: be seen through" and includes glass and bars -- you can see through a
#: barred window and cannot walk through one, and a durable map that records
#: one as a doorway sends its owner marching at a pane of glass with a
#: SPECIFIC remembered distance (`_frontier_hops` renders "about 3 rooms down
#: that way") and no retraction path. `_PASSABLE_BARRIERS` means "passable
#: THIS BEAT" and excludes `closed_door`, which a body simply opens -- a map
#: that forgot every closed door would forget most of a house.
#:
#: So: the passable set plus `closed_door`. Two judgements folded in, on the
#: record:
#:
#: * A LOCKED door is remembered as a route. `normalize_barrier` already
#:   folds `locked_door`/`padlocked`/... to `closed_door`, so the vocabulary
#:   itself has ruled: locked is a state of a door, not a kind of wall, and a
#:   remembered route past a locked door is still a route if you expect to
#:   get the key. Movement stays governed by `_PASSABLE_BARRIERS`; this set
#:   only decides what a mind writes down.
#: * `unknown` is NOT a route. The movement backstop refuses to walk it
#:   (`barrier in ("wall", "unknown")` blocks), and a mind should not record
#:   as a way through what its body would not be allowed to cross; the next
#:   beat that resolves the barrier re-confirms or disproves it.
_ROUTE_MEMORY_BARRIERS = frozenset(_PASSABLE_BARRIERS) | {"closed_door"}


def route_memory_barrier(value) -> bool:
    """Is this edge a route a remembering mind should record?"""
    return normalize_barrier(value) in _ROUTE_MEMORY_BARRIERS


_AMBIENT_BARRIERS = {"open", "open_door", "bars"}


def neighbor_map(scene: dict, barriers=None, *, known_rooms_only=False,
                 directional=False) -> dict:
    """{room_id: {rooms one step away}}, undirected, over the edges a caller
    is willing to cross.

    Undirected because an edge declared from either side is real from both --
    asymmetric declarations happen, and every walk in this package had already
    decided independently to treat them that way (the `nearby_rooms`
    precedent).

    `barriers` is the allowlist of normalized barrier names an edge must be in
    to count. It is a PARAMETER and not a default because the four walks that
    use this genuinely disagree, and each is right: a body walks
    `_PASSABLE_BARRIERS`, sound walks `_SOUND_WALK_BARRIERS` (bars carry
    voices), an ambient bed walks `_AMBIENT_BARRIERS`, and payload trimming
    (`nearby_rooms`) walks every declared edge because it is asking about
    RELEVANCE and not about reachability. Passing `None` crosses everything.

    `known_rooms_only` drops an edge whose target the scene does not have a
    room record for. Only `ambient_scope` asks for that, because its answer is
    a connected component it then reads `parent_entity` off; the walks that
    only need ids tolerate a dangling edge.

    `directional` honours an edge's `passage_from` field, and the result is
    then a DIRECTED map: the walk that carries a body must refuse a chute
    against its fall, while sound and an ambient bed cross it both ways. Off
    by default, because "undirected" is right for three of the four walks and
    for every edge that names no direction. See `passage_direction`: the
    direction is a FIELD, and the absence of a reciprocal edge has never been
    one.
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
            if known_rooms_only and target not in rooms:
                continue
            if barriers is not None \
                    and normalize_barrier(edge.get("barrier")) not in barriers:
                continue
            if directional:
                if edge_crossable_from(edge, room_id):
                    neighbors.setdefault(room_id, set()).add(target)
                if edge_crossable_from(edge, target):
                    neighbors.setdefault(target, set()).add(room_id)
                neighbors.setdefault(room_id, set())
                neighbors.setdefault(target, set())
                continue
            neighbors.setdefault(room_id, set()).add(target)
            neighbors.setdefault(target, set()).add(room_id)
    return neighbors


def passage_direction(edge) -> str:
    """The room a directed edge may be crossed FROM, or "" when it is not
    directed at all.

    THE DIRECTION IS A FIELD, for the reason `sight_direction` already
    records for sight: an edge's direction cannot be carried by WHICH SIDE
    DECLARED IT, because writing adjacency from both sides is the universal
    habit and is correct for every symmetric barrier. A chute, a drop, a door
    that locks behind you are legitimate fiction, and the barrier vocabulary
    has no directed-passage value -- `one_way_window` is sight-only, and
    every member of `_PASSABLE_BARRIERS` is symmetric (docs/UNBUILT.md, "Interior
    passage is undirected").

    The absence of a reciprocal edge is NOT that fact and never was. Measured
    on the live corpus 2026-08-25: 117 of 374 room pairs (31.3%) are declared
    from one side only, 88 of them plain `open`/`open_door` doorways, and ZERO
    of the 16 `one_way_window` declarations. One-sidedness is how edges get
    written, not what a one-way passage looks like -- so a reader that treated
    silence as a seal would be reading a writing habit as world law, which is
    precisely the failure `sight_from` was built to end.

    So: `passage_from: "<room_id>"` on the edge, written from either end or
    both, naming the one room a body may cross from. Both declarations then
    AGREE instead of contradicting, exactly as `sight_from` made them agree.
    """
    if not isinstance(edge, dict):
        return ""
    return str(edge.get("passage_from") or "").strip()


def edge_crossable_from(edge, from_room) -> bool:
    """Does this edge's DIRECTION allow a body to cross it starting from
    `from_room`? Barrier-blind -- ask `edge_passable` for the whole question.

    An undirected edge (the overwhelming majority) is crossable from either
    end. A directed one is crossable only from the room it names.
    """
    named = passage_direction(edge)
    return not named or named == str(from_room)


def edge_passable(edge, from_room) -> bool:
    """May a body cross this edge, starting from `from_room`?

    The whole question in one place: the barrier lets a body through AND the
    edge is not declared one-way against this side. Callers that previously
    tested `normalize_barrier(...) in _PASSABLE_BARRIERS` were asking half of
    it, which was the entire question while a one-way passage had no spelling.
    """
    if not isinstance(edge, dict):
        return False
    return (normalize_barrier(edge.get("barrier")) in _PASSABLE_BARRIERS
            and edge_crossable_from(edge, from_room))


def effective_adjacent(scene: dict, room_id) -> list:
    """Every edge this room has, INCLUDING the ones only its neighbour
    declared -- the room's own list plus one reversed edge per far-side edge
    naming it.

    THE ROOM GRAPH IS UNDIRECTED, by this package's stated doctrine
    (`neighbor_map` above) and by the spatial specialist's own prompt, and
    ten readers honour it while five read `room["adjacent"]` alone and do not.
    The asymmetry they see is not a fact about the world: nothing writes a
    reciprocal edge and nothing drops one, so a room that never declared an
    edge of its own has none, however many doorways point at it. The room a
    story STARTS in is guaranteed to hit that -- at establish there is nothing
    to point at, and every later room is minted with a back-edge only -- and
    it is far from alone: 20 such rooms in the live corpus, 9 of them with
    bodies standing in them.

    What it cost, measured on the run-3 shape: `spatial_digest` `{}`,
    `sprint_reach` `[]`, `corridor_sightlines` `[]`, and `room_layout`
    reporting two doorways as anchors and no exits at all in the same payload.
    Worse, `_behind_rooms` is directed while `visible_adjacent_rooms` is not,
    so an observer standing with their back to a far-declared doorway kept
    receiving fresh sight of the room behind them -- an information EXPANSION
    that this closes by SUBTRACTING more.

    The derivation is the one `_onward_exits` and `effective_anchors` had each
    already written for themselves: the far side's bearing and verticality are
    reversed, because it is the same doorway seen from the opposite wall.
    Derived edges are marked `implicit: True` and are never written anywhere;
    the room's OWN declaration always wins a target it names, so a barrier
    change made from this side is not overruled by a stale far-side echo.

    A far-side `wall` is NOT derived. A wall is not a way through, and a
    non-relation nobody on this side declared names a room this side has no
    relation to -- deriving it would ADD information rather than restore a
    doorway. `normalize_barrier` folds every unreadable word to `wall` too, so
    this also declines to invent a doorway out of a word nothing could read.
    """
    rooms = (scene or {}).get("rooms") or {}
    room = rooms.get(room_id)
    own = [e for e in ((room or {}).get("adjacent") or [])
           if isinstance(e, dict) and e.get("to")]
    named = {str(e["to"]) for e in own}
    out = list(own)
    for other_id, other in rooms.items():
        if str(other_id) == str(room_id) or str(other_id) in named \
                or not isinstance(other, dict):
            continue
        for edge in other.get("adjacent") or []:
            if not isinstance(edge, dict) \
                    or str(edge.get("to")) != str(room_id):
                continue
            if normalize_barrier(edge.get("barrier")) == "wall":
                continue
            derived = {k: v for k, v in edge.items()
                       if k not in ("to", "dir", "vertical")}
            derived["to"] = other_id
            derived["implicit"] = True
            bearing = opposite_bearing(normalize_bearing(edge.get("dir")))
            if bearing:
                derived["dir"] = bearing
            vertical = opposite_vertical(
                normalize_vertical(edge.get("vertical")))
            if vertical:
                derived["vertical"] = vertical
            out.append(derived)
            named.add(str(other_id))
            break
    return out
