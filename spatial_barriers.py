# spatial_barriers.py
"""Barrier vocabulary: normalising model-written barrier names into engine
vocabulary, and the class sets saying what a barrier passes."""

import re


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
    "one-way window": "one_way_window",
    "one_way_mirror": "one_way_window",
    "one-way mirror": "one_way_window",
    "one way mirror": "one_way_window",
    "two_way_mirror": "one_way_window",
    "two-way mirror": "one_way_window",
    "two way mirror": "one_way_window",
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
_SCENT_BARRIERS = {"open", "open_door", "bars", "membrane", "closed_door"}


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
            edge["barrier"] = _barrier_against_its_own_name(
                normalize_barrier(edge.get("barrier")), edge.get("name"))

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


_AMBIENT_BARRIERS = {"open", "open_door", "bars"}
