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
  2. **The story's Charter naming laws**, which the lived-location generator
     derives from lore at generation time. Each Charter is a separate LANE:
     pools are never blended across laws, because a given name from one
     culture stitched to a family name from another belongs to neither.
  3. **Harvested evidence**: personal names the story already contains --
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
from world.charter_identity import generated_name, normalize_naming_profile

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
            if not title:
                keys = [k.strip() for k in str(row["keys"] or "").split(",")
                        if k.strip()]
                if keys:
                    # Keys are lowercased snake identifiers; recover the
                    # name shape they encode.
                    title = " ".join(
                        w.capitalize() for w in keys[0].split("_"))
            if title:
                names.append(title)
    return names


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
    no law); ``source`` is ``"authored"``, ``"charters"``, ``"harvested"``
    or ``"none"``. Authority order is authored > charters > harvested: an
    author's explicit law silences the derived ones, and the harvest only
    speaks when nobody with more standing has.
    """
    authored = authored_naming_profile(chat_id)
    if naming_law_exists(authored):
        return [authored], "authored"
    lanes = _charter_naming_lanes(chat_id)
    if lanes:
        return lanes, "charters"
    harvested = harvested_naming_profile(chat_id)
    if naming_law_exists(harvested):
        return [harvested], "harvested"
    return [], "none"


def _lane_number(seed):
    raw = hashlib.blake2b(str(seed).encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(raw, "big")


def minted_presence_name(chat_id, uid, used=(), lanes=None):
    """One deterministic name for this presence, or ``""``.

    Deterministic in ``(chat_id, uid)``: rerolling a turn or replaying a
    rolled-back commit re-mints the SAME name for the same presence, while a
    different presence -- a replacement taking a vacated post -- carries a
    different uid and draws a different name. Each candidate is generated
    wholly inside one lane (one law), never stitched across lanes. ``used``
    is the casefolded no-fly list (cast, persona, every tracked presence's
    spellings); when every candidate is taken, or the story has no law, the
    answer is ``""`` and the presence stays honestly unnamed.
    """
    if lanes is None:
        lanes, _source = story_naming_lanes(chat_id)
    lanes = [normalize_naming_profile(p) for p in (lanes or [])]
    lanes = [p for p in lanes if naming_law_exists(p)]
    if not lanes:
        return ""
    taken = {str(u or "").strip().casefold() for u in used}
    taken.discard("")
    scope = "chat:%s" % chat_id
    for attempt in range(_MINT_ATTEMPTS):
        lane = lanes[_lane_number(
            "%s|%s|%s" % (scope, uid, attempt)) % len(lanes)]
        candidate = generated_name(scope, str(uid), lane, attempt)
        if candidate and candidate.casefold() not in taken:
            return candidate
    return ""
