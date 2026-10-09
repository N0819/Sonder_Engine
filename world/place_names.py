"""Names code deals into the slots a structure grammar opens.

THE ROOM WRITES THE FRAME; CODE FILLS THE SLOT IT LEFT. A structure grammar's
name may be a PATTERN -- "the {name} Row", "the {name} Stage" -- which says
how places of that kind are called in this story without naming any one of
them. Until 2026-10-08 nothing filled the slot: `structure.mint_frontier`
handed the pattern out as written, so chat 165's grammar would have minted a
stub called "the {name} Sheds" off its causeway for the axis "the mainland"
(the article matched), and the rooms the closure splits off a dwelling took
an ordinal instead ("the Back Row 2" .. "5").

A PLACE NAME CARRIES MEANING, so a slot is filled only where the Room opened
one for a kind the place was CHOSEN to be -- a frontier stub whose axis names
its rule's kind, and was drawn to it (`structure.mint_frontier`), and, on the
owner's ruling (`DEAL_SIBLING_NAMES`), a sibling of a dwelling whose name is
an instance of the pattern -- and only with the story's own name material
(`story.naming.story_naming_lanes`: the authored law, else the phonology the
town's naming laws were written back as, else the charters' laws). A dealt
word reads as a name in the setting's sound; it never names a person the
story has (`charter_identity.reconstructs_a_reserved_name`, the reserved
elements exactly, and `NAME_SIMILARITY_FLOOR`), never reads as one of the
town's own residents (a row called after a family that lives there claims
whose row it is, which is the Room's to say), and never reads as a place
word already standing. Where no slot is open, or nothing survives the
refusals, the ordinal or the axis label stays: those are the fallback, not
the defect.

DETERMINISTIC. A name is seeded by the structure key and the room's uid and
nothing that changes between rerolls, and no model is asked at the mint.

Design: `docs/design/DESIGN_CHARTER_PLACES.md` § 5.
"""

from __future__ import annotations

import hashlib
import re

from world.charter_identity import (
    NAME_PREFIX_FLOOR, NAME_SIMILARITY_FLOOR, _letters, generated_name_parts,
    jaro_winkler, normalize_naming_profile, reconstructs_a_reserved_name,
    reserved_name_elements)


#: The slot a grammar name leaves for a proper name.
SLOT = "{name}"

#: How many seeded candidates the dealer tries before conceding and leaving
#: the ordinal or the axis label in place. The same number the person mint
#: uses (`story.naming._MINT_ATTEMPTS`): past it, a story's material is too
#: thin or too close to its own people to name another place, and the
#: fallback is more honest than a name squeezed out of what is left.
PLACE_NAME_ATTEMPTS = 32

#: WHETHER THE ROOMS THE CLOSURE SPLITS OFF A DWELLING ARE DEALT NAMES IN
#: THEIR PARENT'S FRAME. ON, by the owner's ruling of 2026-10-08 ("deal
#: proper names", over the recommendation to keep the numbers): a sibling
#: whose parent's name is an instance of a grammar frame is dealt a word in
#: that frame -- chat 165's "the Back Row 2" .. "5" become four named rows --
#: which turns one planned row into several named ones, each name a proper
#: noun every mind that passes reads, and so each held apart from the town's
#: residents and the story's people like any dealt word. Off, a sibling
#: keeps the ordinal it always had ("the Back Row 2"). A frontier stretch
#: does not wait on this: a frame the axis asked for is the Room's own
#: statement of what lies that way (`structure.mint_frontier`).
DEAL_SIBLING_NAMES = True


def is_pattern(name) -> bool:
    """Is this grammar name a frame with a slot, rather than a name?"""
    return SLOT in str(name or "")


def name_patterns(rule) -> list:
    """The patterns among one grammar rule's names, in authored order."""
    rule = rule if isinstance(rule, dict) else {}
    return [str(n) for n in rule.get("names") or () if is_pattern(n)]


def _frame(pattern):
    """A pattern as an anchored, case-blind expression with its slot as the
    one group.

    THE SLOT IS WHOLE WORDS WHERE THE FRAME SPACES IT OFF. "the {name} Row"
    has a space either side of its slot, so a name is an instance only where
    the filler stands as words of its own: "the Back Row" is one and "the
    Sparrow" is not. The slot used to be joined to the frame's text by an
    OPTIONAL space, so the boundary could fall inside a word -- a boarding
    house called "the Sparrow" read as a row called "Spar" and its siblings
    were dealt row names, and chat 165's "the Causeway" put "Cause" among
    the place words standing in "the {name} Way" (review 2026-10-08, M3).
    Where a frame writes its slot against its text -- "{name}長屋", in a
    script that does not space its words, or "{name}ton" -- the filler abuts
    the text there, as the frame itself does.
    """
    pieces = str(pattern).split(SLOT)
    last = len(pieces) - 1
    parts = []
    for index, piece in enumerate(pieces):
        words = piece.split()
        # The space between the slot before this piece and its text.
        if index and piece[:1].isspace() and (words or index < last):
            parts.append(r"\s+")
        parts.append(r"\s+".join(re.escape(word) for word in words))
        if index < last:
            # The space between this piece's text and the slot after it.
            if words and piece[-1:].isspace():
                parts.append(r"\s+")
            parts.append(r"(.+?)")
    return re.compile(r"^\s*" + "".join(parts) + r"\s*$", re.IGNORECASE)


def pattern_filler(pattern, name):
    """What fills `pattern`'s slot in `name`, or None when `name` is not an
    instance of the pattern ("the {name} Row" and "the Back Row" -> "Back";
    "the Back Row 2" and "the Sparrow" are not instances)."""
    if not is_pattern(pattern) or not str(name or "").strip():
        return None
    match = _frame(pattern).match(" ".join(str(name).split()))
    if not match:
        return None
    filler = match.group(1).strip()
    return filler or None


def instance_of(grammar, name):
    """``(pattern, filler)`` for the first pattern of `grammar` that `name`
    instantiates, in rule order and then name order, or None."""
    for rule in grammar or ():
        for pattern in name_patterns(rule):
            filler = pattern_filler(pattern, name)
            if filler:
                return pattern, filler
    return None


def standing_fillers(grammar, names) -> list:
    """The words filling a slot in any of `names` -- the place words already
    standing in this grammar's frames, which a new one must not echo."""
    out = []
    for name in names or ():
        found = instance_of(grammar, name)
        if found and found[1] not in out:
            out.append(found[1])
    return out


def resident_name_words(bodies) -> list:
    """Every word of every name `bodies` carry -- a town's own people, each a
    charter body ``{"name": ...}`` -- sorted, once each. A row called after a
    family that lives there claims whose row it is, which is the Room's to
    say, so a dealt word is held apart from all of them."""
    out = set()
    for body in bodies or ():
        if isinstance(body, dict):
            out.update(word for word in str(body.get("name") or "").split()
                       if word)
    return sorted(out)


def spelling_key(text) -> str:
    """A spelling as the letters and digits it is written with, in any
    script, casefolded: two names with one key are one name to a reader.

    Not `normalize_room_id`, which keeps only ASCII and folds every name
    written in another script to the same empty id. Measured (review
    2026-10-08, H1): a story whose rooms are named in kana held every
    candidate already "taken", so the closure never dealt one, and a
    frontier stub dealt a kana name was re-keyed to the room uid ''."""
    return "".join(ch for ch in str(text or "").casefold() if ch.isalnum())


def fill(pattern, word) -> str:
    return " ".join(str(pattern).replace(SLOT, str(word)).split())


def _number(*parts) -> int:
    raw = hashlib.blake2b("|".join(str(p) for p in parts).encode("utf-8"),
                          digest_size=8).digest()
    return int.from_bytes(raw, "big")


def _opens_like(word, others) -> bool:
    """Does `word` open on the same `NAME_PREFIX_FLOOR` letters as one of
    `others` -- the shared-prefix veto ruled with the two floors (owner,
    2026-08-28), where recognisability lives?"""
    if len(word) < NAME_PREFIX_FLOOR:
        return False
    head = word[:NAME_PREFIX_FLOOR]
    return any(len(other) >= NAME_PREFIX_FLOOR
               and other[:NAME_PREFIX_FLOOR] == head for other in others)


def deal_place_name(pattern, *, scope, key, lanes, reservation=None,
                    residents=(), standing=(), taken=()) -> str:
    """One name for one place: `pattern` with its slot filled, or ``""``.

    `scope` is the structure key and `key` the room's uid, and they are the
    whole of the seed. `lanes` are the story's naming laws, never blended:
    each candidate is drawn wholly from one. A candidate WORD is refused
    when it:

    * is, reconstructs, or reads as (`NAME_SIMILARITY_FLOOR`) an element of
      a name `reservation` holds -- a person the story has;
    * is, or reads as, a word of one of `residents`' names -- the town's own
      people (review 2026-10-08, M1: "the Marlaburn Row" was dealt to the
      room the Marleyburns sleep in, at Jaro-Winkler 0.94);
    * is, reads as, or opens on the same `NAME_PREFIX_FLOOR` letters as a
      place word already filling a slot (`standing`): "the Drayelburn Row"
      beside "the Drayamere Row" is one row misheard (L6);

    and the NAME it makes is refused when a room already answers to it.
    `taken` is every spelling a room answers to -- uids, names, aliases, as
    written -- compared by `spelling_key`, which reads any script, and by
    the room fold the engine resolves a spelling with (`normalize_room_id`),
    so a name in a script the fold drops is still compared, and one whose
    fold lands on a room already standing is not dealt.
    """
    if not is_pattern(pattern):
        return ""
    from world.spatial import normalize_room_id

    lanes = [normalize_naming_profile(lane) for lane in lanes or ()
             if isinstance(lane, dict)]
    lanes = [lane for lane in lanes
             if lane["given"] or (lane["given_parts"]["starts"]
                                  and lane["given_parts"]["ends"])]
    if not lanes:
        return ""
    elements = reserved_name_elements(reservation)
    residents = {_letters(word) for word in residents or () if _letters(word)}
    standing = {_letters(word) for word in standing or () if _letters(word)}
    near = elements | residents | standing
    spellings, folds = set(), set()
    for spelling in taken or ():
        spellings.add(spelling_key(spelling))
        folds.add(normalize_room_id(str(spelling)))
    spellings.discard("")
    folds.discard("")
    for attempt in range(PLACE_NAME_ATTEMPTS):
        lane = lanes[_number(scope, key, attempt) % len(lanes)]
        _name, given, family = generated_name_parts(
            str(scope), "place:%s" % key, lane, attempt)
        word = " ".join(str(family or given or "").split())
        folded = _letters(word)
        if len(folded) < 2 or folded in near:
            continue
        if reconstructs_a_reserved_name(word, reservation):
            continue
        if any(jaro_winkler(folded, other) >= NAME_SIMILARITY_FLOOR
               for other in near):
            continue
        if _opens_like(folded, standing):
            continue
        name = fill(pattern, word)
        fold = normalize_room_id(name)
        if spelling_key(name) in spellings or (fold and fold in folds):
            continue
        return name
    return ""


__all__ = [
    "DEAL_SIBLING_NAMES", "PLACE_NAME_ATTEMPTS", "SLOT", "deal_place_name",
    "fill", "instance_of", "is_pattern", "name_patterns", "pattern_filler",
    "resident_name_words", "spelling_key", "standing_fillers",
]
