"""Stable, author-controlled identities for Charter bodies.

Charter may hold thousands of bodies, so identity creation cannot be an LLM
call and a display name cannot become the key other systems use.  The body
dict key remains the permanent identity.  This module only materialises the
human-facing name and presentation attached to that key.

Authors opt in with a small cultural ``naming`` profile.  Curated given and
family pools form a deterministic Cartesian name space; syllable parts --
authored, or derived from the pools' own words (`derived_name_parts`) --
extend that space when the population outgrows it, so a pool sized for a
cast decides what a large population SOUNDS like rather than how much of a
name space it gets.  A generated name is written into the body once.
Existing names therefore survive changes to the profile, insertion of new
bodies, checkpoint restore and promotion.
"""

from __future__ import annotations

import hashlib
import re


_FORMAT_FIELDS = {"given", "family", "name", "title", "rank"}


def _strings(value):
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item).strip() for item in value if str(item or "").strip()]


def _parts(value):
    value = value if isinstance(value, dict) else {}
    return {
        "starts": _strings(value.get("starts")),
        "middles": _strings(value.get("middles")),
        "ends": _strings(value.get("ends")),
    }


def _safe_format(value, fallback):
    """A name format, or the fallback. A format with NO fields is neither.

    The guard checked only that every field it found was one this profile
    knows, and `set() <= anything` is true -- so a law writing "given family"
    instead of "{given} {family}" passed, `str.format` had nothing to
    substitute, and every body in the world came out called `given family`.

    Found in play, and it mutes a population rather than erroring: a market
    town generated with 300 bodies had all 300 named "given family" plus a
    body key. The narrator will not speak a name like that, so it rendered
    everyone anonymously; nothing could resolve an address to them; and the
    player stopped a woman in the square, asked her a direct question, and got
    `no eligible respondent` from a room holding 120 people. A name pool of
    real names sat unused in the same law.

    So a format must NAME AT LEAST ONE FIELD to be a format. Absent fields are
    the failure the unknown-field check was already refusing, arriving the
    other way round.
    """
    text = str(value or fallback).strip() or fallback
    fields = set(re.findall(r"\{([^{}]+)\}", text))
    if not fields or not fields <= _FORMAT_FIELDS:
        return fallback
    return text


def normalize_naming_profile(value):
    """Return the bounded, JSON-safe naming profile Charter understands.

    No implicit English profile exists.  Core is genre agnostic: an author
    who supplies no naming law keeps the historical body-key fallback rather
    than receiving names from a culture the engine invented.
    """
    value = value if isinstance(value, dict) else {}
    titles = value.get("titles") if isinstance(value.get("titles"), dict) else {}
    return {
        "seed": str(value.get("seed") or ""),
        "given": _strings(value.get("given")),
        "family": _strings(value.get("family")),
        "given_parts": _parts(value.get("given_parts")),
        "family_parts": _parts(value.get("family_parts")),
        "name_format": _safe_format(value.get("name_format"),
                                    "{given} {family}"),
        "formal_format": _safe_format(value.get("formal_format"),
                                      "{title} {name}"),
        "titles": {
            "posts": {str(k): str(v).strip()
                      for k, v in (titles.get("posts") or {}).items()
                      if str(v or "").strip()},
            "ranks": {str(k): str(v).strip()
                      for k, v in (titles.get("ranks") or {}).items()
                      if str(v or "").strip()},
        },
    }


def _number(seed, lane=0):
    raw = hashlib.blake2b(
        f"{seed}|{lane}".encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(raw, "big")


def _syllable_name(parts, seed):
    starts, middles, ends = (
        parts.get("starts") or [], parts.get("middles") or [],
        parts.get("ends") or [])
    if not starts or not ends:
        return ""
    start = starts[_number(seed, 0) % len(starts)]
    middle = ""
    if middles:
        middle = middles[_number(seed, 1) % len(middles)]
    end = ends[_number(seed, 2) % len(ends)]
    assembled = f"{start}{middle}{end}"
    # A FRAGMENT IS SOUND; A NAME IS A PROPER NOUN. The law's parts are
    # syllables a model wrote in lower case ("hal", "in", "ham"), and joined
    # as written they reached play as "halinham nookfeller" on every body of a
    # generated town (Harrowmere playtest, 2026-09-02). A pool word keeps its
    # author's spelling; an assembled component has no author's spelling to
    # keep, so it takes the one thing every proper noun has -- a capital at
    # the front. `upper()` is a no-op on a script without case, so a law
    # written in kana is left exactly as assembled.
    return assembled[:1].upper() + assembled[1:]


def _component(pool, parts, seed, lane):
    if pool:
        return pool[_number(seed, lane) % len(pool)]
    return _syllable_name(parts, f"{seed}|{lane}")


#: One run of letters -- derivation reads a pool word as its letter runs, so
#: a hyphen or an apostrophe splits rather than entering a syllable.
_LETTER_RUN_RE = re.compile(r"[^\W\d_]+", re.UNICODE)

#: The vowel letters the syllable splitter understands (matched
#: case-insensitively). A script whose vowel structure this class cannot see
#: derives nothing: the engine extends a law only where it can follow the
#: law's own phonology, never by inventing one.
_VOWEL_CLASS = "aeiouyàáâäåæèéêëìíîïòóôöøùúûüāēīōū"
_SYLLABLE_RE = re.compile(
    "[^%s]*[%s]+" % (_VOWEL_CLASS, _VOWEL_CLASS), re.IGNORECASE)


def _syllable_chunks(run):
    """One letter run split at its vowel groups; trailing consonants join
    the final chunk. Every chunk but possibly the last ends in a vowel,
    which is what makes a first chunk join cleanly onto a later word's
    remainder. Empty for a run with no recognised vowel."""
    chunks = _SYLLABLE_RE.findall(run)
    if not chunks:
        return []
    tail = run[sum(len(chunk) for chunk in chunks):]
    if tail:
        chunks[-1] += tail
    return chunks


def derived_name_parts(pool):
    """Syllable parts learned from an authored pool's own words.

    The extension lane for a population larger than its authored name
    space: recombining the pool's own openings and endings yields new names
    inside the law's phonology, so the engine never invents a culture --
    an empty pool, or one whose vowel structure the splitter cannot read,
    derives nothing and the caller's law simply does not extend.

    Only a word that splits contributes: its first chunk (vowel-final by
    construction, original casing kept) becomes an opening, the rest its
    ending. A single-chunk word offers nothing, because gluing two whole
    names together is a collision wearing a hyphen's clothes, and fewer
    than two distinct openings recombine into nothing the pool did not
    already say.
    """
    starts, ends = {}, {}
    for word in _strings(pool):
        for run in _LETTER_RUN_RE.findall(word):
            chunks = _syllable_chunks(run)
            if len(chunks) < 2:
                continue
            starts.setdefault(chunks[0].casefold(), chunks[0])
            tail = "".join(chunks[1:]).lower()
            ends.setdefault(tail.casefold(), tail)
    if len(starts) < 2 or not ends:
        return {"starts": [], "middles": [], "ends": []}
    return {
        "starts": [starts[key] for key in sorted(starts)],
        "middles": [],
        "ends": [ends[key] for key in sorted(ends)],
    }


def spread_components(profile):
    """Which name components an allocator spreads breadth-first.

    Two class reasons a shared component ASSERTS something a mint has no
    business asserting: kinship -- a family name recurring inside one
    generated population reads as a household the fiction never authored
    (measured: 42 bodies drawn from a twelve-family pool held four
    same-surname clusters, each implying relatives of a registered
    character) -- and address, where `address_components` finds the law
    calling people by one element alone. Given names spread freely; two
    people sharing one is ordinary. Spreading is preference, not refusal:
    exhaustion of the whole name space still permits reuse, unlike the hard
    bar `name_is_reserved` holds for registered minds.
    """
    return frozenset({"family"}) | address_components(profile)


def components_repeat(given, family):
    """A name that repeats its own component is an allocator artifact, not
    a name -- one word sitting in both pools should never become both
    halves of one person (measured: a body named by doubling a single pool
    word reached play as `lieutenant <word> <word>`, chat 95)."""
    given = " ".join(str(given or "").split()).casefold()
    family = " ".join(str(family or "").split()).casefold()
    return bool(given) and given == family


def extension_profile(profile):
    """The same law with each spread component moved onto syllable parts,
    or ``None`` when nothing extends.

    Authored parts are the author's own extension and are used as written;
    parts derived from the pool serve only where the author supplied none.
    A field whose pool is already empty gains nothing (the base law draws
    it from parts already), and fields the law does not spread keep their
    pools, so an extended family name still pairs with an authored given.
    """
    base = normalize_naming_profile(profile)
    out = None
    for field in spread_components(base):
        if field not in ("given", "family"):
            continue
        pool = base[field]
        if not pool:
            continue
        parts = base[field + "_parts"]
        if not (parts["starts"] and parts["ends"]):
            parts = derived_name_parts(pool)
        if not (parts["starts"] and parts["ends"]):
            continue
        if out is None:
            out = dict(base)
        out[field] = []
        out[field + "_parts"] = parts
    return out


def generated_name_parts(charter_key, body_key, profile, attempt=0):
    """``(name, given, family)`` for one deterministic candidate.

    The components are returned rather than re-derived from the rendered
    string because only the generator knows which pool each half came from:
    a law that writes ``{family} {given}`` puts the family FIRST, and any
    reader that guesses from word order gets that culture backwards.
    """
    profile = normalize_naming_profile(profile)
    if not (profile["given"] or profile["given_parts"]["starts"]):
        return "", "", ""
    seed = "%s|%s|%s|%s" % (
        profile.get("seed") or charter_key, charter_key, body_key, attempt)
    given = _component(profile["given"], profile["given_parts"], seed, 0)
    family = _component(profile["family"], profile["family_parts"], seed, 1)
    if not given:
        return "", "", ""
    values = {"given": given, "family": family, "name": "",
              "title": "", "rank": ""}
    name = " ".join(profile["name_format"].format(**values).split()).strip()
    return name, given, family


def generated_name(charter_key, body_key, profile, attempt=0):
    """One deterministic candidate, or ``""`` when the profile has no law."""
    return generated_name_parts(charter_key, body_key, profile, attempt)[0]


def _stored_name_components(body, profile):
    """Recover format fields without mistaking a display title for identity.

    New generated bodies store their components directly. Older registries
    predate those fields, so the two common authored formats receive a narrow
    compatibility parse. Any unfamiliar cultural format falls back to the
    full stored name instead of rendering a title with a blank identity.
    """
    body = body if isinstance(body, dict) else {}
    profile = normalize_naming_profile(profile)
    name = str(body.get("name") or body.get("key") or "").strip()
    given = str(body.get("given_name") or "").strip()
    family = str(body.get("family_name") or "").strip()
    parts = name.split()
    if parts and not (given and family):
        if profile["name_format"] == "{given} {family}":
            given = given or " ".join(parts[:-1]) or parts[0]
            family = family or parts[-1]
        elif profile["name_format"] == "{family} {given}":
            family = family or parts[0]
            given = given or " ".join(parts[1:]) or parts[-1]
    # A custom format may not expose separable components. Repeating the full
    # identity is imperfect but never collapses "Dr. Sarah Moon" to "Dr.".
    return given or name, family or name


def address_components(profile):
    """Which single name component this law addresses a person BY, alone.

    A name element is identity only where the law lets it stand for the whole
    person. Under ``{given} {family}`` the pair is the address and neither
    half is, so two people may share a family the way two people do; under
    ``{rank} {family}`` or ``Dr. {family}`` the family alone IS how everyone
    is called, so sharing one is sharing an address.

    A format that renders ``{name}`` carries the whole identity already and
    exposes nothing on its own.
    """
    profile = normalize_naming_profile(profile)
    out = set()
    for fmt in (profile["name_format"], profile["formal_format"]):
        fields = set(re.findall(r"\{([^{}]+)\}", fmt))
        if "name" in fields:
            continue
        alone = fields & {"given", "family"}
        if len(alone) == 1:
            out |= alone
    return frozenset(out)


def _tokens(text):
    return tuple(word for word in str(text or "").casefold().split() if word)


def _title_terms(profile):
    """Token tuples these laws use as titles: every authored rank/post title,
    plus the literal words a formal format itself carries (``Dr.``). Used only
    to see PAST a title into the identity underneath it, so a registered
    ``Lieutenant Commander Geordi La Forge`` is recognised as being called
    ``La Forge``. Accepts one law or several -- a story's laws are separate
    lanes, but a title is a title in all of them."""
    profiles = ([profile] if isinstance(profile, dict) or profile is None
                else list(profile))
    terms = set()
    for raw in profiles:
        law = normalize_naming_profile(raw)
        for table in ("ranks", "posts"):
            for value in law["titles"][table].values():
                tokens = _tokens(value)
                if tokens:
                    terms.add(tokens)
        literal = re.sub(r"\{[^{}]*\}", " ", law["formal_format"])
        for word in literal.split():
            tokens = _tokens(word)
            if tokens:
                terms.add(tokens)
    return terms


def _untitled(tokens, terms):
    """Drop leading title runs until what is left is the person's own name."""
    changed = True
    while changed and tokens:
        changed = False
        for term in terms:
            if len(tokens) > len(term) and tokens[:len(term)] == term:
                tokens = tokens[len(term):]
                changed = True
                break
    return tokens


def identity_reservation(names, profile=None):
    """The identity forms already spoken for in this story, as the mint reads
    them: whole names, and the token runs each name is built from.

    ``names`` are the names REGISTERED minds answer to -- the player's persona
    and every attached character. This structure is deliberately profile-light
    (only the title vocabulary is used, and only to look past a title): the
    same reservation serves every lane of the story's law, including lanes
    that write names in a different order.
    """
    terms = _title_terms(profile)
    whole, runs = set(), set()
    for name in names or ():
        text = " ".join(str(name or "").split())
        if not text:
            continue
        whole.add(text.casefold())
        tokens = _untitled(_tokens(text), terms)
        if tokens:
            runs.add(tokens)
    return {"whole": frozenset(whole), "runs": frozenset(runs)}


def _reserves_component(reservation, component):
    """Does a registered mind's name start or end with this element?

    Anchored at either end, because which end a family name sits on is the
    culture's business and both orders are in play. The middle is excluded:
    a token buried inside a longer name is not what anyone is called.
    """
    part = _tokens(component)
    if not part:
        return False
    for run in (reservation or {}).get("runs") or ():
        if len(run) >= len(part) and (run[:len(part)] == part
                                      or run[-len(part):] == part):
            return True
    return False


#: THE NOVELTY FLOOR, AND IT IS NOT A DISTANCE. Owner ruling 2026-08-28:
#: longest common substring 4, shared-prefix veto 4. Both are mid-band of what
#: the record-linkage literature supports and both are named here rather than
#: buried, per the standing rule about caps.
#:
#: Edit distance CANNOT detect a mashup, which is why this is a substring test.
#: A distance measures closeness to the nearest SINGLE reserved name, and a
#: mashup is recognisable precisely because it is close to TWO at once:
#: `Crulaski` sits far enough from `Pulaski` to pass any published threshold
#: while being unmistakably made of it. Measured on this engine's own
#: extension lane, 78.5% of reachable surnames shared a run of four or more
#: characters with a real person's surname, and the lane regenerated one canon
#: surname verbatim.
#:
#: Four characters because that is where a fragment stops being phonology and
#: starts being recognisable, and because the prefix is where recognisability
#: lives -- a shared opening carries a name further than a shared tail.
NAME_RUN_FLOOR = 4
NAME_PREFIX_FLOOR = 4


def _longest_shared_run(left, right):
    """Length of the longest substring these two share. Small strings only."""
    if not left or not right:
        return 0
    previous = [0] * (len(right) + 1)
    best = 0
    for i in range(1, len(left) + 1):
        current = [0] * (len(right) + 1)
        for j in range(1, len(right) + 1):
            if left[i - 1] == right[j - 1]:
                current[j] = previous[j - 1] + 1
                if current[j] > best:
                    best = current[j]
        previous = current
    return best


def reconstructs_a_reserved_name(text, reservation):
    """Is this candidate assembled out of somebody's name?

    Asked of ONE component at a time, against the reserved token runs. A
    candidate that merely shares a short cluster with a reserved name is
    ordinary phonology and passes; one carrying four characters of somebody
    else's name in order, or opening on their first four, does not.
    """
    folded = "".join(ch for ch in str(text or "").casefold() if ch.isalpha())
    if len(folded) < NAME_RUN_FLOOR:
        return False
    for run in (reservation or {}).get("runs") or ():
        spelled = " ".join(run) if isinstance(run, (tuple, list)) else str(run)
        # Each TOKEN separately: a run is a name's token sequence, and it is
        # the tokens that carry recognisability, not the space between them.
        for token in spelled.split():
            other = "".join(ch for ch in token.casefold() if ch.isalpha())
            if len(other) < NAME_RUN_FLOOR:
                continue
            if folded == other:
                # AN EXACT SHARE IS NOT A RECONSTRUCTION, and the guards above
                # already decide it under their own rules. This repo permits
                # sharing on purpose -- "a registered `Beverly Crusher` does
                # not reserve every `Beverly` in the story; that would be an
                # expansion, and shared given names are ordinary" -- and a
                # near-miss is the opposite case: nobody shares `Crushen`
                # with anybody, it was assembled out of somebody. Refusing
                # exact matches here turned that documented permission off
                # and failed five tests that exist to pin it.
                continue
            if _longest_shared_run(folded, other) >= NAME_RUN_FLOOR:
                return True
            if folded[:NAME_PREFIX_FLOOR] == other[:NAME_PREFIX_FLOOR]:
                return True
    return False


def name_is_reserved(name, profile, reservation, given="", family=""):
    """Would minting this name take an identity a registered mind already has?

    Two subtractions, never an expansion: the whole name is refused always,
    and a component is refused when `address_components` says the law calls
    people by that component alone. Measured case (chat 95, 42 generated
    bodies against a five-name cast): a family pool harvested from the same
    lore as the cast, under ``{rank} {family}``, minted `B'Elanna Crusher`
    beside registered `Beverly Crusher` and `Taurik Picard` beside
    `Jean-Luc Picard` -- one story holding a captain and an ensign whom
    everybody addresses by the same word.
    """
    reservation = reservation or {}
    text = " ".join(str(name or "").split())
    if not text:
        return False
    if text.casefold() in (reservation.get("whole") or frozenset()):
        return True
    # A COMPONENT THAT IS SOMEBODY'S WHOLE NAME IS REFUSED WHATEVER THE LAW
    # ADDRESSES PEOPLE BY.
    #
    # The address-component test below asks "would people call these two the
    # same word", which is the right question for a SHARED SURNAME and the
    # wrong one for a registered mind whose entire name turns up as somebody
    # else's given name. Measured, chat 95 second pass, after the surname half
    # of this guard was landed and working: a law of `{rank} {family}` reports
    # only `family` as an address component, so `Worf Yar`, `Data O'Brien`,
    # `Geordi Ogawa`, `Beverly Pulaski` and `Jean-Luc Pulaski` all passed --
    # five bodies carrying a registered character's identity in the half of
    # the name nobody was checking. The surnames were clean; the collision had
    # simply moved to the other axis.
    #
    # `whole` rather than `runs` for this test, deliberately. A registered
    # `Beverly Crusher` does not reserve every `Beverly` in the story -- that
    # would be an expansion, and shared given names are ordinary. What it
    # reserves is a body whose component IS the whole identity somebody
    # already answers to, which is what a one-word name like `Worf` or `Data`
    # makes possible.
    # Compared against the UNTITLED runs, not the stored whole names. A cast
    # member registered as "Lieutenant Commander Data" holds the bare identity
    # `data` -- the rank is how the story addresses him, not part of who he is
    # -- and `identity_reservation` already strips titles into `runs` for
    # exactly this reason. Measured: checking `whole` alone let `Data Picard`,
    # `Data Soong`, `Data Ogawa` and `Geordi Picard` through in one generation,
    # because "data" is not "lieutenant commander data" as a string.
    bare = {" ".join(run) for run in (reservation.get("runs") or ())}
    bare |= set(reservation.get("whole") or ())
    for value in (given, family):
        folded = " ".join(str(value or "").split()).casefold()
        if folded and folded in bare:
            return True
    fields = address_components(profile)
    for field, value in (("given", given), ("family", family)):
        if field in fields and _reserves_component(reservation, value):
            return True
    # AND THE NAME THAT WAS ASSEMBLED OUT OF SOMEBODY. Every test above
    # refuses a name the mint RECOGNISES; this one refuses a name it built
    # from recognisable pieces, which is the failure no reservation can reach.
    # See `reconstructs_a_reserved_name`: 78.5% of the surnames this engine's
    # extension lane could reach shared four or more characters in order with
    # a real person's surname, and it regenerated one verbatim.
    for value in (given, family):
        if reconstructs_a_reserved_name(value, reservation):
            return True
    return False


#: WHERE A LETTER STOPS BEING A LETTER AND STARTS BEING A PIECE OF SOMEBODY.
#: Owner-named per the standing rule about caps, and it is the shortest floor
#: this test can have: the relation below is anchored containment between a
#: fragment and a name the story gives to somebody, so a ONE-letter fragment
#: matches every name that happens to begin with it and refusing it would take
#: the alphabet away from the law. Two letters that open or close somebody's
#: name are a piece of that name.
#:
#: Deliberately lower than `NAME_RUN_FLOOR`. That floor asks whether an
#: ASSEMBLED name is recognisable as somebody, where four characters is where
#: recognisability starts. This one asks whether a fragment IS somebody's, and
#: a two-letter opening of a name is theirs whether or not anyone would
#: recognise the result -- it is the difference between "does this look like
#: them" and "was this cut out of them".
NAME_ELEMENT_FLOOR = 2


def _letters(text):
    """One casefolded run of letters, punctuation and spacing dropped -- so an
    apostrophe or a hyphen inside a name does not hide it from comparison."""
    return "".join(ch for ch in str(text or "").casefold() if ch.isalpha())


def reserved_name_elements(reservation):
    """Every TOKEN of every reserved name, letters only.

    A fragment is a piece of a word, so the comparison has to be against
    words: the reservation's runs are token sequences and it is the individual
    tokens a fragment could have been cut from. Titled spellings are excluded
    -- `identity_reservation` already strips titles into `runs`, and a rank is
    how a story addresses somebody rather than part of who they are, so a law
    may build names out of ordinary words that happen to appear in one.
    """
    out = set()
    for run in (reservation or {}).get("runs") or ():
        spelled = " ".join(run) if isinstance(run, (tuple, list)) else str(run)
        for token in spelled.split():
            folded = _letters(token)
            if len(folded) >= NAME_ELEMENT_FLOOR:
                out.add(folded)
    return frozenset(out)


def fragment_is_name_element(fragment, elements):
    """Is this fragment a piece of a name the story gives to somebody?

    ANCHORED, and in both directions: the fragment opens or closes one of the
    reserved tokens, or a reserved token opens or closes the fragment. The
    middle is excluded for the reason `_reserves_component` already excludes
    it -- what a person is called by is the head and the tail of their name,
    and a run buried inside a longer word is ordinary phonology.

    This is the predicate the whole partition rests on. A pool is a list of
    names and is refused wholesale; a fragment set is MATERIAL, and material
    that was cut out of somebody is not material. The distinction is not
    about how well any model knows any setting: it is about whether the
    engine can say, deterministically, that this piece belongs to a person
    the story already has.
    """
    folded = _letters(fragment)
    if len(folded) < NAME_ELEMENT_FLOOR:
        return False
    for other in elements or ():
        if len(other) < NAME_ELEMENT_FLOOR:
            continue
        if (folded.startswith(other) or folded.endswith(other)
                or other.startswith(folded) or other.endswith(folded)):
            return True
    return False


def refuse_reserved_fragments(profile, reservation):
    """The same law with every fragment that is an element of a reserved name
    removed. Pools are untouched here -- `refuse_harvested_material` owns
    that decision, and `strip_reserved_pools` owns it for a stored law."""
    profile = normalize_naming_profile(profile)
    elements = reserved_name_elements(reservation)
    if not elements:
        return profile
    for field in ("given_parts", "family_parts"):
        for bucket in ("starts", "middles", "ends"):
            profile[field][bucket] = [
                value for value in profile[field][bucket]
                if not fragment_is_name_element(value, elements)]
    return profile


def vocabulary_name_parts(words, reservation=None):
    """Syllable material learned from words that name PLACES AND THINGS.

    The setting's rooms, institutions and structures belong to its sound
    system and belong to nobody: a place is not a person, so cutting one up
    cannot issue anybody's name. This is the material of last resort, reached
    only where refusal left a field with nothing -- a law that still has its
    own openings keeps them, because a law's own phonology is closer to it
    than its architecture is.

    Reserved elements are refused here too, because an author may perfectly
    well name a room after a person, and one syllable of provenance does not
    stop being provenance for having a building in front of it.

    `derived_name_parts`' own two-opening floor is not applied: it guards an
    EXTENSION of a law that already works, where one opening recombines into
    nothing new. Here the alternative is an empty field, and one opening is
    a law where none is a failure.
    """
    parts = derived_name_parts(_strings(words))
    elements = reserved_name_elements(reservation)
    if elements:
        for bucket in ("starts", "middles", "ends"):
            parts[bucket] = [value for value in parts[bucket]
                             if not fragment_is_name_element(value, elements)]
    if not (parts["starts"] and parts["ends"]):
        return {"starts": [], "middles": [], "ends": []}
    return parts


def naming_material_exists(profile):
    """Does this law carry syllable material a mint can actually assemble?

    Narrower than `story.naming.naming_law_exists`, which also accepts a
    pool. This asks the question the partition cares about: is there material
    that names nobody, so the pool never has to be reached for.
    """
    profile = normalize_naming_profile(profile)
    parts = profile["given_parts"]
    return bool(parts["starts"] and parts["ends"])


def _fill_empty_material(profile, vocabulary=(), reservation=None):
    """REFUSAL MAY EMPTY A FIELD; IT MAY NOT LEAVE ONE EMPTY.

    A guard that turns a naming defect into a generation failure is not an
    improvement, and the refusal above is capable of taking a law's entire
    family opening list -- measured, one generation of an institution whose
    lore carried a large named cast supplied nine family openings and every
    one of them was the opening of a cast surname.

    Two replacements, both from material the story already has:

      1. **The law's own other field.** A start is a start: a field that
         lost its openings borrows the openings the same law still holds
         elsewhere, which stays inside one law's phonology and invents
         nothing. Both directions, in a fixed order, so the result is
         deterministic.
      2. **The setting's non-personal vocabulary** (`vocabulary_name_parts`).

    Nothing else. No default table exists anywhere in this engine and none is
    added here: a law with neither of these has no material, and the caller
    is left to say so.
    """
    for field, other in (("given_parts", "family_parts"),
                         ("family_parts", "given_parts")):
        for bucket in ("starts", "ends"):
            if not profile[field][bucket] and profile[other][bucket]:
                profile[field][bucket] = list(profile[other][bucket])
    derived = None
    for field in ("given_parts", "family_parts"):
        for bucket in ("starts", "ends"):
            if profile[field][bucket]:
                continue
            if derived is None:
                derived = vocabulary_name_parts(vocabulary, reservation)
            if derived[bucket]:
                profile[field][bucket] = list(derived[bucket])
    return profile


def refuse_harvested_material(profile, reservation=None, vocabulary=()):
    """A generated law loses its name lists AND the pieces of people in its
    fragments, and is handed material to replace them.

    A POOL is a list of whole name elements. Where a law was written by a
    model reading a story's lore, those elements are the names of people the
    story contains -- which is what a pool is FOR, and exactly what it must
    not be. Measured 2026-08-28 on a generated institution: the planner
    emitted `given` and `family` pools built out of a lorebook's cast and the
    `{given} {family}` cross product handed twenty strangers names like
    "Jean-Luc Crusher", reconstituting one canon character's full name
    verbatim. Two of the elements it supplied (`Soong`, `Pulaski`) appear in
    no lore entry at all -- the model wrote them from its own knowledge of the
    setting -- so no reservation, however complete, can reach them. The pool
    has to stop existing rather than be cleaned.

    THE FRAGMENTS ARE NOT INNOCENT EITHER, and that was this function's
    standing premise until it was measured. It read: "a fragment names nobody
    however well a model knows a canon". Across three consecutive generations
    of one institution, two of the three supplied `family_parts.starts` that
    were, entry for entry, the openings of the cast's own surnames; the third
    supplied ordinary fragments touching nobody. So it is variance in what a
    model volunteers, not a constant -- which is exactly why the guard cannot
    be the model. Nothing reconstructed a whole name, the novelty floor held,
    and the material was still the cast, cut up: one body came out wearing a
    registered person's surname exactly, assembled from a three-letter opening
    and a two-letter ending that each passed every test the engine had.

    So the same rule runs at the fragment: material that was cut out of
    somebody is not material (`fragment_is_name_element`). And because that
    refusal is capable of taking a whole field, it is paired with the material
    that replaces it (`_fill_empty_material`) rather than left to surface as
    "generated lived location did not provide a usable naming law".

    ``vocabulary`` is the setting's words for PLACES AND INSTITUTIONS -- read
    only when refusal left a field empty, and only after the law's own
    surviving openings have been offered.

    THE POOL REMAINS THE LAST RESORT, unchanged from before this refusal
    existed: a law left with no assemblable material at all keeps its pools,
    subtracted, exactly as it did when there was no other answer. A story
    that generated before this change and would now fail is a worse outcome
    than the defect, and this branch is the promise that there is no such
    story. It is unreachable for any law carrying material of its own or
    generated beside a setting whose place words split -- both measured
    generations reach it never.

    NOT APPLIED TO AN AUTHORED LAW. `story/naming.py` ranks a story's own
    naming law above a generated one, and an author who writes a list gets
    exactly that list (52d2ef5) -- their list is a deliberate artifact, not a
    roster harvested behind their back. This answers the generator only.
    """
    pooled = normalize_naming_profile(profile)
    refused = refuse_reserved_fragments(pooled, reservation)
    refused["given"] = []
    refused["family"] = []
    _fill_empty_material(refused, vocabulary, reservation)
    if naming_material_exists(refused):
        return refused
    refused["given"] = list(pooled["given"])
    refused["family"] = list(pooled["family"])
    return refused


def strip_reserved_pools(profile, reservation):
    """The same law with every reserved element removed from the pools it
    draws addresses from.

    The refusal at the mint answers one candidate; this answers the POOL, so
    a law persisted with a registered mind's element in it stops offering
    that element to every later reader (`story/naming.py` reads a stored
    Charter law as one of its lanes). Pools only -- syllable parts are not
    elements anyone is called by, and the mint's refusal covers what they
    assemble.
    """
    profile = normalize_naming_profile(profile)
    if not (reservation or {}).get("runs"):
        return profile
    # NOT GATED ON `address_components`, which was the defect. That helper
    # answers "which fields is somebody ADDRESSED by", and it returns empty
    # under the commonest format of all -- `{given} {family}` -- so this
    # whole function was a no-op for most laws and only ever fired where a
    # law happened to also carry a title format (measured 2026-08-28, chat
    # 95).
    #
    # They are different questions. Two people SHARING a family name is
    # ordinary, because sharing arises. A pool that CONTAINS a named
    # individual's family name is the engine issuing that individual's name
    # to strangers, which is not sharing. So the predicate here is the plain
    # one: no pool element may be a component of a name the story has
    # already given to somebody.
    #
    # Pools only -- syllable parts are not elements anyone is called by, and
    # the mint's own refusal covers what they assemble.
    for field in ("given", "family"):
        profile[field] = [value for value in profile[field]
                          if not _reserves_component(reservation, value)]
    return profile


def _lane_spaces(lane, spread):
    """Per spread field, the casefolded value space this lane can draw, or
    ``None`` when the space is too large to enumerate cheaply. A field the
    lane has no source for is omitted -- it yields the empty component and
    constrains nothing."""
    spaces = {}
    for field in spread:
        pool = lane[field]
        if pool:
            spaces[field] = frozenset(value.casefold() for value in pool)
            continue
        parts = lane[field + "_parts"]
        starts, middles, ends = (
            parts["starts"], parts["middles"] or [""], parts["ends"])
        if not starts or not ends:
            continue
        if len(starts) * len(middles) * len(ends) > 1024:
            spaces[field] = None
            continue
        spaces[field] = frozenset(
            (start + middle + end).casefold()
            for start in starts for middle in middles for end in ends)
    return spaces


def _components_fresh(used_spread, given, family):
    for field, taken in used_spread.items():
        value = given if field == "given" else family
        folded = " ".join(str(value or "").split()).casefold()
        if folded and folded in taken:
            return False
    return True


def materialize_body_names(charter_key, raw_bodies, profile, reservation=None):
    """Copy ``raw_bodies`` and give every unnamed body one stable name.

    Collision resolution is deterministic on the first materialisation.
    Once the normalised registry is persisted, generated names are ordinary
    stored names and never enter this allocator again.

    ``reservation`` (from `identity_reservation`) is the registered cast's
    identity forms. A body that ALREADY carries a name keeps it untouched --
    a featured resident is placed here under the registered character's own
    name on purpose -- so the refusal only ever applies to what this
    allocator itself mints.

    Allocation is CAPACITY-AWARE: each `spread_components` element is
    handed out breadth-first, authored pool values before values built on
    the extension lane (`extension_profile` -- authored syllable parts, or
    parts derived from the pool's own words), and reuse is permitted only
    once that whole space is spent. A pool sized for a cast does not decide
    how large a population may be; it decides what the population sounds
    like. A candidate that doubles its own component is refused everywhere
    (`components_repeat`).
    """
    raw_bodies = raw_bodies if isinstance(raw_bodies, dict) else {}
    out = {str(key): dict(value) if isinstance(value, dict) else {}
           for key, value in raw_bodies.items()}
    profile = normalize_naming_profile(profile)
    spread = {field for field in spread_components(profile)
              if field in ("given", "family")}
    used = set()
    used_spread = {field: set() for field in spread}

    def note(name, given, family):
        used.add(str(name).casefold())
        for field, value in (("given", given), ("family", family)):
            folded = " ".join(str(value or "").split()).casefold()
            if field in used_spread and folded:
                used_spread[field].add(folded)

    for body in out.values():
        name = str(body.get("name") or "").strip()
        if not name:
            continue
        given, family = _stored_name_components(body, profile)
        note(name, given, family)
    lanes = [(profile, _lane_spaces(profile, spread), True)]
    extended = extension_profile(profile)
    if extended is not None:
        lanes.append((extended, _lane_spaces(extended, spread), True))
    lanes.append((profile, {}, False))
    attempts = max(32, len(out) * 2)
    for body_key in sorted(out):
        body = out[body_key]
        if str(body.get("name") or "").strip():
            continue
        chosen = chosen_given = chosen_family = ""
        for lane, spaces, fresh in lanes:
            if fresh and any(
                    space is not None and space <= used_spread[field]
                    for field, space in spaces.items()):
                continue  # every value this lane offers is already carried
            # An unenumerable space cannot be declared spent, so its lane's
            # search is bounded instead of exhaustive; the relaxed lane
            # below still guarantees a name.
            lane_attempts = attempts
            if fresh and any(space is None for space in spaces.values()):
                lane_attempts = min(attempts, 64)
            for attempt in range(lane_attempts):
                candidate, given, family = generated_name_parts(
                    charter_key, body_key, lane, attempt)
                if not candidate:
                    break
                if candidate.casefold() in used:
                    continue
                if components_repeat(given, family):
                    continue
                if name_is_reserved(
                        candidate, lane, reservation, given, family):
                    continue
                if fresh and not _components_fresh(
                        used_spread, given, family):
                    continue
                chosen, chosen_given, chosen_family = candidate, given, family
                break
            if chosen:
                break
        # A very small authored pool may genuinely be exhausted.  A stable
        # disambiguator is better than silently merging two people, and it is
        # only reached after every authored combination/part attempt failed.
        if not chosen:
            base = given = family = ""
            for attempt in range(32):
                base, given, family = generated_name_parts(
                    charter_key, body_key, profile, attempt)
                # The disambiguator inherits every candidate rule the lanes
                # enforce except uniqueness (the body key supplies that);
                # a doubled component is no more a name here than above.
                if not base or not components_repeat(given, family):
                    break
            candidate = f"{base} {body_key}".strip() if base else body_key
            # Never past the reservation, even here: a body left unnamed is
            # caught loudly by the generator's own unnamed check, while a
            # disambiguated collision is a second person under a registered
            # mind's address and is caught by nothing.
            if base and name_is_reserved(
                    candidate, profile, reservation, given, family):
                continue
            chosen, chosen_given, chosen_family = candidate, given, family
        body["name"] = chosen
        given, family = _stored_name_components(body, profile)
        if chosen_given:
            given = chosen_given
        if chosen_family:
            family = chosen_family
        if given:
            body.setdefault("given_name", given)
        if family:
            body.setdefault("family_name", family)
        note(chosen, given, family)
    return out


def title_for(body, roles=(), profile=None):
    """The authored/rank/post title currently presented for this body."""
    body = body if isinstance(body, dict) else {}
    explicit = str(body.get("title") or "").strip()
    if explicit:
        return explicit
    profile = normalize_naming_profile(profile)
    rank = str(body.get("rank") or "").strip()
    if rank and rank in profile["titles"]["ranks"]:
        return profile["titles"]["ranks"][rank]
    for role in roles or ():
        title = profile["titles"]["posts"].get(str(role))
        if title:
            return title
    return ""


def display_name(body, roles=(), profile=None):
    """Formal scene-facing name; the underlying body key remains identity."""
    body = body if isinstance(body, dict) else {}
    name = str(body.get("name") or body.get("key") or "").strip()
    title = title_for(body, roles, profile)
    if not title or name.casefold().startswith(title.casefold() + " "):
        return name
    fmt = normalize_naming_profile(profile)["formal_format"]
    given, family = _stored_name_components(body, profile)
    values = {"given": given,
              "family": family,
              "name": name, "title": title,
              "rank": str(body.get("rank") or "")}
    return " ".join(fmt.format(**values).split()).strip()


def identity_aliases(body, roles=(), profile=None):
    """Every authored formal form that may refer to this same body.

    Personal names are materialized and permanent; rank and post titles are
    presentation that may legitimately change.  Keeping the bounded authored
    title variants as aliases lets recognition and historical transcript
    colour survive that presentation change without treating the display
    string as identity.
    """
    body = body if isinstance(body, dict) else {}
    profile = normalize_naming_profile(profile)
    name = str(body.get("name") or body.get("key") or "").strip()
    if not name:
        return []
    titles = [str(body.get("title") or "").strip()]
    titles.extend(profile["titles"]["ranks"].values())
    titles.extend(profile["titles"]["posts"].values())
    current = title_for(body, roles, profile)
    titles.append(current)
    given, family = _stored_name_components(body, profile)
    values = {
        "given": given,
        "family": family,
        "name": name,
        "rank": str(body.get("rank") or ""),
    }
    aliases = [name]
    for title in titles:
        title = str(title or "").strip()
        if not title:
            continue
        formal = " ".join(profile["formal_format"].format(
            **{**values, "title": title}).split()).strip()
        if formal:
            aliases.append(formal)
    shown = display_name(body, roles, profile)
    aliases.append(shown)
    return list(dict.fromkeys(alias for alias in aliases if alias))


def identity_seed(charter_key, body_key):
    """Stable render seed shared by background dialogue and promotion."""
    return f"charter:{charter_key}:{body_key}"
