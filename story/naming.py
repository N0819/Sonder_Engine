"""The story's naming law -- where a minted person's name comes from.

The background-presence ledger keeps people the story never got around to
naming (an id-shaped string standing where a name should, a speaker harvested
from a channel that carried no name). Such a person is tracked, but nothing
can *call* them anything, no reader can recognise them on the next watch, and
promotion refuses to mint a sheet under a non-name. The generator here exists
to close that gap -- and it must sound like the story it serves, so there is
NO fixed default table anywhere in it. The law comes from the story's own
material, in authority order:

  1. **The authored profile** (the ``naming_profile`` world key): the
     author's explicit story-level law, in exactly the shape a Charter
     ``naming`` profile takes (`world/charter_identity.py` -- curated
     given/family pools, optional syllable parts, a name format).
  2. **The story's authored phonology** (`phonology` lore entries): the
     FRAGMENTS this story's names are built from. One entry is one lane,
     never blended, and every fragment is checked against the story's
     reserved names before it becomes material -- a pool is an author's
     deliberate list and is theirs, while a fragment set is material, and
     material cut out of somebody is not material.
  3. **The story's Charter naming laws**, which the lived-location generator
     derives from lore at generation time. Each Charter is a separate LANE:
     pools are never blended across laws, because a given name from one
     culture stitched to a family name from another belongs to neither.
  4. **Harvested evidence**: personal names the story already contains --
     the registered cast and the lorebook's entries about people -- split
     into given/family pools. Recombination stays inside the story's own
     vocabulary, so a minted name is made of parts the setting has already
     used.

A story that yields no law mints nothing. That is `charter_identity`'s
standing doctrine -- the engine never hands out names from a culture it
invented -- and the presence simply stays unnamed until the story names it.

THE PERMANENCE CONTRACT (the mint is a write, not a rendering) belongs to
the persistence layer: `minted_presence_name` is deterministic in
(chat, presence uid), and `persist/commit_background.py` writes the result
into the presence record exactly once. This module renders candidates and
stores nothing itself, which is what keeps a rolled-back commit, a reroll
and the eventual write all agreeing on the same name for the same person --
while a *different* person (a replacement taking a vacated post) carries a
different uid and therefore draws a different name.
"""

from __future__ import annotations

import hashlib
import re

from core.db import q, wget, wset
from world.charter_identity import (
    components_repeat, extension_profile, generated_name_parts,
    identity_reservation, name_is_reserved, normalize_naming_profile,
    refuse_reserved_fragments)

NAMING_PROFILE_KEY = "naming_profile"

#: How many deterministic candidates to try before conceding the pool is
#: exhausted. Mirrors `materialize_body_names`' floor; past this, staying
#: unnamed is more honest than a disambiguator bolted onto a person's name.
_MINT_ATTEMPTS = 32

#: Honorific/rank prefixes stripped from harvested EVIDENCE before its
#: tokens enter a pool -- "Dr. Elena Voss" contributes Elena/Voss, not
#: "Dr.". Deliberately separate from `persist.commit_background`'s roster
#: sets, which answer a different question (does this string denote someone
#: registered) at a different layer.
_EVIDENCE_TITLE_PREFIXES = frozenset({
    "dr", "mr", "mrs", "ms", "mister", "madam", "madame", "sir", "lord",
    "lady", "master", "professor", "doctor", "captain", "commander",
    "cmdr", "lieutenant", "lt", "ensign", "chief", "admiral", "general",
    "colonel", "major", "sergeant", "corporal", "private", "father",
    "mother", "sister", "brother", "reverend", "king", "queen", "prince",
    "princess", "saint", "st", "the", "a", "an",
})

#: A lore title often appends the person's role after a separator --
#: "Dr. Elena Voss — Resident Psychiatrist". The name is the first segment.
_EVIDENCE_CUT_RE = re.compile(r"\s+[—–-]\s+|[:(\[]")


def naming_law_exists(profile):
    """Does this profile actually generate? The same predicate
    `generated_name` applies: a given-name source is the law's floor (the
    syllable path needs both starts and ends to produce anything)."""
    profile = normalize_naming_profile(profile)
    return bool(profile["given"]
                or (profile["given_parts"]["starts"]
                    and profile["given_parts"]["ends"]))


def authored_naming_profile(chat_id):
    """The author's explicit story-level law, normalized. All-empty fields
    when the author has not written one."""
    return normalize_naming_profile(wget(chat_id, NAMING_PROFILE_KEY, {}) or {})


def set_authored_naming_profile(chat_id, value):
    """Store the authored law (normalized -- bounded and JSON-safe). An
    empty/blank value clears it, dropping the story back to its Charter and
    harvested sources."""
    profile = normalize_naming_profile(value)
    wset(chat_id, NAMING_PROFILE_KEY, profile)
    return profile


def _charter_naming_lanes(chat_id):
    """One lane per Charter that carries its own naming law, in charter-key
    order so lane indexing is deterministic. Reads the stored registry
    tolerantly (normalized shape or the bare authoring convenience) rather
    than paying full registry normalization for a profile read."""
    from world.charter_runtime import CHARTERS_KEY

    stored = wget(chat_id, CHARTERS_KEY, {}) or {}
    if not isinstance(stored, dict):
        return []
    items = stored.get("items")
    if not isinstance(items, dict):
        items = {key: value for key, value in stored.items()
                 if key not in {"version", "recent_events"}
                 and isinstance(value, dict)}
    lanes = []
    for key in sorted(items):
        raw = items[key] if isinstance(items[key], dict) else {}
        state = raw.get("state") if isinstance(raw.get("state"), dict) else raw
        profile = normalize_naming_profile(state.get("naming"))
        if naming_law_exists(profile):
            lanes.append(profile)
    return lanes


def _name_tokens(raw):
    """The personal-name tokens of one evidence string, or ``[]`` when the
    string is not shaped like a personal name.

    Class rules, no story noun in any of them: cut at the first role
    separator; strip leading honorifics; reject a digit-bearing token (keys
    and ids are not names); reject a phrase whose cased token is lowercase
    ("of", "the" -- descriptions, not names; case-blind scripts pass
    untouched); cap at four tokens (past that it is a sentence).
    """
    text = _EVIDENCE_CUT_RE.split(str(raw or "").replace("_", " "), 1)[0]
    words = text.split()
    while words and words[0].strip(".,").casefold() in _EVIDENCE_TITLE_PREFIXES:
        words = words[1:]
    if not 1 <= len(words) <= 4:
        return []
    tokens = []
    for word in words:
        word = word.strip(".,;:!?\"'()[]{}")
        if not word or any(ch.isdigit() for ch in word):
            return []
        first = word[:1]
        if first.isalpha() and first.islower():
            return []
        tokens.append(word)
    return tokens


def _person_name_evidence(chat_id):
    """Every personal-name string the story already contains: the registered
    cast, then the lorebook's entries about people (title first, the entry's
    first key as fallback). Read-only, deterministic order."""
    names = []
    for row in q(
            "SELECT ch.name AS name FROM chat_chars cc "
            "JOIN characters ch ON ch.id=cc.char_id "
            "WHERE cc.chat_id=? ORDER BY cc.char_id", (chat_id,)):
        name = str(row["name"] or "").strip()
        if name:
            names.append(name)
    try:
        from mind.memory import chat_lorebook_ids
        book_ids = list(chat_lorebook_ids(chat_id) or [])
    except Exception:
        book_ids = []
    if book_ids:
        from story.lore_structure import clean_title
        marks = ",".join("?" * len(book_ids))
        rows = q(
            "SELECT title, keys FROM lore_entries "
            "WHERE lorebook_id IN (%s) AND category=? ORDER BY id" % marks,
            (*book_ids, "character"))
        for row in rows:
            title = clean_title(row["title"]) if row["title"] else ""
            keys = [k.strip() for k in str(row["keys"] or "").split(",")
                    if k.strip()]
            if not title and keys:
                # Keys are lowercased snake identifiers; recover the
                # name shape they encode.
                title = " ".join(w.capitalize() for w in keys[0].split("_"))
            for candidate in ([title, _name_head_of(title)] if title else []):
                if candidate and candidate not in names:
                    names.append(candidate)
            # EVERY KEY, not only the first and not only as a fallback. The
            # keys of a `character` entry are the names that entry is FOUND
            # by, which for a person is the set of things they are called --
            # "Crusher", "Doctor Crusher", "Beverly Crusher" are one woman.
            # Measured 2026-08-28 on chat 95: Riker, Crusher, Troi and Soong
            # survived the pool subtraction reading titles alone, because
            # they are named in the entry's keys and in its prose and never
            # as a title of their own. A key that is not a personal name
            # ("the ship", a year) costs one reserved string nobody would
            # have been called anyway; a canon surname left in the pool costs
            # a stranger wearing it.
            for key in keys:
                spelled = " ".join(w.capitalize() for w in key.split("_"))
                if spelled and spelled not in names:
                    names.append(spelled)
    return names


def _name_head_of(title):
    """The personal name inside a lore entry's title, when the title carries a
    role beside it.

    An author writes the entry so a reader can find it -- "Miles O'Brien,
    transporter chief" -- and the appositive after the comma is a DESCRIPTION
    of the person, not part of what they are called. Measured 2026-08-28 on
    chat 95: four canon surnames (O'Brien, Ogawa, Barclay, Laren) survived the
    pool subtraction for exactly this reason, because component matching saw
    the whole string and the pool held the bare surname.

    Both spellings are reserved, never one instead of the other. A title may
    legitimately carry a comma inside the name itself -- a patronymic, "son
    of" -- and choosing between them would guess wrong half the time; keeping
    both costs two strings and guesses nothing.
    """
    text = str(title or "").strip()
    for sep in (",", " -- ", " -- ", " (", " [", " \u2014 ", " \u2013 "):
        if sep in text:
            text = text.split(sep, 1)[0]
    return text.strip(" -\u2013\u2014(),").strip()


def harvested_naming_profile(chat_id):
    """A naming law built from names the story has already used.

    Requires at least two distinct given names before it claims to be a law
    at all -- one name is a person, not a convention -- and returns the
    all-empty profile otherwise, so the caller's `naming_law_exists` check
    reads it as absent. Pools are sorted, decoupling generation from query
    and import order.
    """
    given, family = [], []
    given_seen, family_seen = set(), set()
    for raw in _person_name_evidence(chat_id):
        tokens = _name_tokens(raw)
        if not tokens:
            continue
        head = tokens[0]
        if head.casefold() not in given_seen:
            given_seen.add(head.casefold())
            given.append(head)
        if len(tokens) >= 2:
            tail = tokens[-1]
            if tail.casefold() not in family_seen:
                family_seen.add(tail.casefold())
                family.append(tail)
    if len(given) < 2:
        return normalize_naming_profile({})
    return normalize_naming_profile(
        {"given": sorted(given), "family": sorted(family)})


def story_naming_lanes(chat_id):
    """``(lanes, source)`` -- the story's effective naming law.

    ``lanes`` is a list of normalized profiles (empty when the story yields
    no law); ``source`` is ``"authored"``, ``"phonology"``, ``"charters"``,
    ``"harvested"`` or ``"none"``. Authority order is authored > phonology >
    charters > harvested: an author's explicit law silences the derived ones,
    and the harvest only speaks when nobody with more standing has.

    THE PHONOLOGY LANE OUTRANKS THE CHARTER LANE because it is the same
    material in the form a person can edit. A generated law is written back
    as a `phonology` lore entry (`world/charter_runtime._record_phonology`),
    so the two normally hold the same fragments -- and when they disagree it
    is because somebody opened the entry and changed it, which is the whole
    reason the artifact exists. An author who does not want to edit fragments
    writes a `naming_profile` instead and outranks both.
    """
    authored = authored_naming_profile(chat_id)
    if naming_law_exists(authored):
        return [authored], "authored"
    lanes = phonology_lanes(chat_id)
    if lanes:
        return lanes, "phonology"
    lanes = _charter_naming_lanes(chat_id)
    if lanes:
        return lanes, "charters"
    harvested = harvested_naming_profile(chat_id)
    if naming_law_exists(harvested):
        return [harvested], "harvested"
    return [], "none"


def registered_identity_names(chat_id):
    """Every name a REGISTERED mind in this story answers to: the player's
    persona and each attached character.

    THE SAME TWO WELLS `persist.commit_background._refuse_name_collision`
    trusts, read here so both minting paths ask one question. That guard has
    always refused to promote a presence onto a registered name -- "Names are
    how this engine tells minds apart" -- and it was wired to the promotion
    path alone, which is why a Charter generation could mint 42 bodies out of
    a pool holding the cast's own family names (chat 95, measured
    2026-08-27). A refusal that answers one of two minting paths is not a
    refusal.

    Order is deterministic (persona first, then attachment order) and the
    spellings are returned as authored; casefolding belongs to the caller
    that compares.
    """
    names = []
    chat_row = q("SELECT * FROM chats WHERE id=?", (chat_id,), one=True)
    if chat_row:
        from story.character_schema import persona_name
        from story.scene import persona_of
        player = str(persona_name(persona_of(dict(chat_row))) or "").strip()
        if player:
            names.append(player)
    for row in q(
            "SELECT ch.name AS name FROM chat_chars cc "
            "JOIN characters ch ON ch.id=cc.char_id "
            "WHERE cc.chat_id=? ORDER BY cc.char_id", (chat_id,)):
        name = str(row["name"] or "").strip()
        if name and name not in names:
            names.append(name)
    # AND EVERY INDIVIDUAL THE STORY NAMES, not only the ones with a mind
    # attached. A lore entry in the `character` category names a PERSON the
    # world contains; whether anybody has registered them yet is a fact about
    # this playthrough, not about whether the name is theirs.
    #
    # `_person_name_evidence` already gathers exactly this set -- it is what
    # the HARVEST lane reads to build a pool from. That asymmetry was the
    # defect: the same names were evidence for minting and invisible to the
    # refusal. Measured 2026-08-28 on a generated Star Trek institution, the
    # harvest built {given} x {family} pools out of the lorebook's canon cast
    # and the free cross-product issued "Jean-Luc Crusher", "Ro Vulcan" and
    # "Deanna Tellarite" to twenty strangers, and reconstituted a canon
    # character's full name verbatim. In an ORIGINAL setting the same thing
    # happens silently, because no reader knows the canon well enough to
    # catch it.
    for name in _person_name_evidence(chat_id):
        name = str(name or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def story_identity_reservation(chat_id, profile=None, extra=()):
    """The story's reserved identity forms, ready for the mint.

    ``profile`` is the law (or laws) the mint is about to draw from -- used
    only for its title vocabulary, so a registered name carrying a rank is
    still recognised as the person underneath it. ``extra`` carries names a
    caller knows about that no table does (a turn's extra players).
    """
    names = list(registered_identity_names(chat_id))
    names.extend(str(name or "").strip() for name in extra or ())
    if profile is None:
        profile = _charter_naming_lanes(chat_id) + [
            authored_naming_profile(chat_id)]
    return identity_reservation([n for n in names if n], profile)


def _lane_number(seed):
    raw = hashlib.blake2b(str(seed).encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(raw, "big")


def minted_presence_name(chat_id, uid, used=(), lanes=None, reservation=None):
    """One deterministic name for this presence, or ``""``.

    Deterministic in ``(chat_id, uid)``: rerolling a turn or replaying a
    rolled-back commit re-mints the SAME name for the same presence, while a
    different presence -- a replacement taking a vacated post -- carries a
    different uid and draws a different name. Each candidate is generated
    wholly inside one lane (one law), never stitched across lanes. ``used``
    is the casefolded no-fly list (cast, persona, every tracked presence's
    spellings); when every candidate is taken, or the story has no law, the
    answer is ``""`` and the presence stays honestly unnamed.

    ``reservation`` is the registered cast's identity FORMS, which is a
    stronger bar than ``used``: under a law that addresses people by family
    alone, a candidate no one has spelled out yet still arrives as an
    existing mind's address. Defaulted rather than required, because a mint
    that is safe only when the caller remembers is the wiring this fix
    exists to remove.
    """
    if lanes is None:
        lanes, _source = story_naming_lanes(chat_id)
    lanes = [normalize_naming_profile(p) for p in (lanes or [])]
    lanes = [p for p in lanes if naming_law_exists(p)]
    if not lanes:
        return ""
    if reservation is None:
        reservation = story_identity_reservation(chat_id, lanes)
    taken = {str(u or "").strip().casefold() for u in used}
    taken.discard("")
    scope = "chat:%s" % chat_id
    # The authored/derived pools first; once their combinations are spent,
    # each lane's extension (`extension_profile`: authored syllable parts,
    # or parts derived from the lane's own pool) widens the space in the
    # same phonology. A lane that does not extend simply offers no second
    # round, and a story with thin material still mints nothing.
    rounds = [("", lanes)]
    extended = [p for p in (extension_profile(lane) for lane in lanes) if p]
    if extended:
        rounds.append(("extension", extended))
    for label, round_lanes in rounds:
        for attempt in range(_MINT_ATTEMPTS):
            lane = round_lanes[_lane_number(
                "%s|%s|%s%s" % (scope, uid, label, attempt))
                % len(round_lanes)]
            candidate, given, family = generated_name_parts(
                scope, str(uid), lane, attempt)
            if not candidate or candidate.casefold() in taken:
                continue
            if components_repeat(given, family):
                continue
            if name_is_reserved(candidate, lane, reservation, given, family):
                continue
            return candidate
    return ""


# --- the phonology lane -----------------------------------------------------
#
# THE ONE SOURCE THE MINT IS ALLOWED. Everything above this point subtracts:
# it harvests whatever a law happens to carry and then removes the names it
# recognises. That is necessary as a backstop and provably insufficient as a
# mechanism -- measured 2026-08-28 on a generated Star Trek institution, two of
# the four surnames still reachable after every subtraction (`Soong`,
# `Pulaski`) appear in no lore entry anywhere. The planner supplied them from
# its own knowledge of the setting while writing the law, and no reservation
# can reach a name the story never wrote down.
#
# So the pool must stop containing people's names rather than be cleaned of
# them. A `phonology` entry holds FRAGMENTS -- the material a name is built
# from -- and by construction names nobody.

_PHONOLOGY_FIELDS = {
    "given_starts": ("given_parts", "starts"),
    "given_middles": ("given_parts", "middles"),
    "given_ends": ("given_parts", "ends"),
    "family_starts": ("family_parts", "starts"),
    "family_middles": ("family_parts", "middles"),
    "family_ends": ("family_parts", "ends"),
}


def phonology_entries(chat_id):
    """Every `phonology` lore entry this chat can see, oldest first."""
    try:
        from mind.memory import chat_lorebook_ids
        book_ids = list(chat_lorebook_ids(chat_id) or [])
    except Exception:
        book_ids = []
    if not book_ids:
        return []
    marks = ",".join("?" * len(book_ids))
    return list(q(
        "SELECT id, title, keys, content FROM lore_entries "
        "WHERE lorebook_id IN (%s) AND category=? ORDER BY id" % marks,
        (*book_ids, "phonology")))


def phonology_parts(chat_id):
    """The name material this story authored, as a naming profile's parts.

    An entry's content is read as `field: a, b, c` lines, one per fragment
    class, so an author edits a plain list rather than a schema. Unknown
    fields are ignored rather than guessed at -- an entry that says nothing
    this mint understands contributes nothing, which is the honest reading of
    a fragment set written for some other purpose.
    """
    parts = {"given_parts": {"starts": [], "middles": [], "ends": []},
             "family_parts": {"starts": [], "middles": [], "ends": []}}
    seen = set()
    for row in phonology_entries(chat_id):
        for group, buckets in _entry_parts(row).items():
            for bucket, fragments in buckets.items():
                for fragment in fragments:
                    key = (group, bucket, fragment.casefold())
                    if key in seen:
                        continue
                    seen.add(key)
                    parts[group][bucket].append(fragment)
    return parts


def _entry_parts(row):
    """One entry's fragments. An entry's content is read as ``field: a, b, c``
    lines, one per fragment class, so an author edits a plain list rather than
    a schema."""
    parts = {"given_parts": {"starts": [], "middles": [], "ends": []},
             "family_parts": {"starts": [], "middles": [], "ends": []}}
    seen = set()
    for line in str(row["content"] or "").splitlines():
        if ":" not in line:
            continue
        field, _, rest = line.partition(":")
        slot = _PHONOLOGY_FIELDS.get(field.strip().casefold()
                                     .replace(" ", "_").replace("-", "_"))
        if not slot:
            continue
        group, bucket = slot
        for fragment in rest.split(","):
            fragment = fragment.strip()
            key = (group, bucket, fragment.casefold())
            if fragment and key not in seen:
                seen.add(key)
                parts[group][bucket].append(fragment)
    return parts


def phonology_lanes(chat_id, reservation=None):
    """One lane per `phonology` entry, oldest first -- never blended.

    Pools are never blended across laws, and fragments are no different: two
    settings' sound systems stitched together belong to neither, and a story
    holding an institution from each would otherwise mint names from a third
    place that does not exist. One entry is one law.

    EVERY FRAGMENT IS CHECKED before it becomes material
    (`charter_identity.refuse_reserved_fragments`). The entry is written by
    the generator as well as by an author, so it can arrive carrying the
    pieces of people the generation was reading about; and unlike a pool --
    which is an author's deliberate list of names and is theirs -- a fragment
    set claims to name nobody. That claim is what is verified here.

    A lane whose material does not survive the check simply does not speak,
    and the next authority does.
    """
    rows = phonology_entries(chat_id)
    if not rows:
        return []
    if reservation is None:
        reservation = story_identity_reservation(chat_id)
    lanes = []
    for row in rows:
        profile = normalize_naming_profile(_entry_parts(row))
        profile = refuse_reserved_fragments(profile, reservation)
        if naming_law_exists(profile):
            lanes.append(profile)
    return lanes


def phonology_law_exists(chat_id):
    """True when this story authored any name material of its own."""
    parts = phonology_parts(chat_id)
    return any(bucket for group in parts.values() for bucket in group.values())
