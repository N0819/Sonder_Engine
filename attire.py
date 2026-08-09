"""Clothing by body region, and the fact that taking it off takes time.

Before this module, what someone was wearing was a flat list of garments plus
one free-text sentence of state:

    {"wearing": ["travelling clothes", "flowing robes", "a dress and shawl"],
     "state":   ["sash untied and front parted, exposing breasts and belly"]}

That is a real transcript, and it shows both problems at once. Three complete
outfits are worn simultaneously, because nothing says a garment OCCUPIES
anywhere and so nothing stops two robes being the outer layer. And the entire
progress of undressing is compressed into one sentence, because there is
nowhere else for it to live -- so "partially undressed" exists only in prose,
and prose has no memory. The next beat re-reads a list that still says three
outfits and resolves the ambiguity however it likes.

Two ideas fix it.

**A garment occupies a REGION.** Head, torso, arms, hands, waist, legs, feet:
coarse on purpose, because the point is to make layering and exposure
representable, not to model tailoring. Garments in a region are ordered
outermost-first, so removing one has a defined consequence -- this region,
previously covered by that, now shows what was under it.

**Taking it off is a sequence, not a switch.** A garment moves
worn -> loosened -> open -> removed, and ONE STEP PER BEAT unless the player
says otherwise. This is the whole reason the module exists: told in as many
words that a character was "still fully clothed, not quite undressed yet", the
engine had her bare in the same paragraph, because there was no state between
dressed and undressed for it to stop at.

What is under a garment is authored per region where an author cares to, and
falls back to the body's own description where they do not -- nobody should
have to fill seven fields before they can play. Whether those descriptions are
SHOWN is a separate per-story choice, and off by default.
"""

from __future__ import annotations

import re

# Coarse and closed. Finer regions (chest vs. belly, thigh vs. calf) buy detail
# that no part of the engine acts on, at the cost of an authoring burden nobody
# would carry.
#
# `waist` and `groin` are separate for one reason, and it is not fastidiousness.
# The waist is the belt line: a sash, an obi, a belt. The groin is the private
# parts. Conflated, a body wearing nothing but an obi reports its groin as
# COVERED -- and a dress whose span stopped at the waist reports it as BARE.
# Both are wrong in the way that matters most, and in opposite directions, so
# no single region can be right.
REGIONS = ("head", "torso", "arms", "hands", "waist", "groin", "legs", "feet")

# Ordered. A garment moves DOWN this list, one rung at a time, and never skips
# unless something says so explicitly.
GARMENT_STATES = ("worn", "loosened", "open", "removed")

# Where a garment goes when nothing says. Torso, because it is what most
# unclassifiable clothing ("robes", "a coat", "rags") actually covers, and
# because putting it in the wrong region is more recoverable than dropping it.
DEFAULT_REGION = "torso"

# Words that place a garment, checked longest-first so "overcoat" is a coat and
# "headscarf" is not a scarf around the waist.
_REGION_CUES = (
    ("head", ("hat", "cap", "hood", "helm", "helmet", "headscarf", "veil",
              "crown", "circlet", "mask", "goggles", "spectacles", "glasses",
              # Ornaments still need a PLACE, even though they cover nothing:
              # a ribbon is in the hair, an earring at the ear.
              "ribbon", "hairpin", "hair pin", "kanzashi", "comb", "clip",
              "barrette", "headband", "diadem", "tiara", "earring",
              "monocle", "eyepatch")),
    ("feet", ("boot", "shoe", "sandal", "slipper", "sock", "stocking",
              "greave", "anklet")),
    ("hands", ("glove", "gauntlet", "mitten", "bracer", "ring", "watch")),
    ("legs", ("trouser", "trousers", "pants", "breeches", "leggings", "hose",
              "skirt", "kilt", "shorts", "hakama", "trews", "jeans",
              "pantaloons", "culottes")),
    ("waist", ("belt", "sash", "girdle", "obi", "cord", "cincture", "apron")),
    ("groin", ("underwear", "undergarment", "undergarments", "smallclothes",
               "briefs", "boxers", "panties", "knickers", "drawers", "thong",
               "loincloth", "breechcloth", "breechclout", "fundoshi",
               "codpiece", "girdle-cloth")),
    ("arms", ("sleeve", "armband", "vambrace", "bangle", "bracelet")),
    ("torso", ("shirt", "tunic", "blouse", "coat", "cloak", "robe", "jacket",
               "vest", "waistcoat", "dress", "gown", "shift", "chemise",
               "nightgown", "nightdress", "negligee", "slip", "haori", "kimono",
               "yukata", "toga", "chiton", "sari", "saree", "qipao",
               "cheongsam", "abaya", "thawb", "thobe", "kaftan", "caftan",
               "cassock", "jumpsuit", "coverall", "coveralls", "overalls",
               "catsuit", "wetsuit", "cardigan", "sweater", "jumper",
               "hoodie", "shawl", "corset", "bodice", "armour", "armor",
               "mail", "breastplate", "cuirass", "scarf", "poncho", "wrap",
               "necklace", "pendant", "choker", "torc", "locket", "amulet",
               "talisman", "brooch", "badge", "medal", "insignia")),
)

# Garments that are not ONE body part. A kimono is not a torso garment that
# happens to be long -- it is sleeves and skirts and a torso at once, and
# opening it uncovers all of them. Listed anchor-first; the anchor is what
# `region_of` returns, and the rest is what the garment also covers.
#
# The waist is in every span: anything that hangs from the shoulders past the
# hips passes it, it is where a kimono is closed and a toga gathered, and a
# sash over an open robe has to know the robe is there.
#
# Deliberately conservative. A garment that is only SOMETIMES full-length (a
# tunic, a shirt with sleeves or without) is left as one region, because a
# wrong span is harder to notice than a missing one and the region editor is
# where an author says otherwise.
_SPANNING_CUES = (
    # Wrapped or one-piece: the whole body, or nearly.
    (("kimono", "yukata", "toga", "chiton", "abaya", "thawb", "thobe",
      "cassock", "kaftan", "caftan", "jumpsuit", "coverall", "coveralls",
      "overalls", "catsuit", "wetsuit"),
     ("torso", "arms", "waist", "groin", "legs")),
    # Reaches past the waist, but leaves the arms.
    (("dress", "gown", "sari", "saree", "qipao", "cheongsam", "robe",
      "shift", "chemise", "nightgown", "nightdress", "negligee", "slip"),
     ("torso", "waist", "groin", "legs")),
    # Legwear. Trousers and skirts alike cover what is between the legs; a
    # body in trousers whose groin reads as bare is the failure this split
    # exists to prevent.
    (("trouser", "trousers", "pants", "jeans", "breeches", "leggings", "hose",
      "hakama", "trews", "pantaloons", "culottes", "skirt", "kilt", "shorts"),
     ("legs", "groin")),
    # Has sleeves, stops at the waist or thereabouts.
    (("coat", "cloak", "jacket", "haori", "cardigan", "sweater", "jumper",
      "hoodie", "mail", "armour", "armor"),
     ("torso", "arms", "waist")),
)


# Things worn AT a place without covering it. A ribbon is in the hair, a
# necklace is at the throat, a ring is on a hand -- all present, all visible,
# none of them clothing that place. Without the distinction, a woman in nothing
# but a hair ribbon has a covered head, and taking the ribbon off "uncovers"
# one.
_ATTACH_CUES = (
    "ribbon", "hairpin", "hair pin", "kanzashi", "comb", "clip", "barrette",
    "tie", "band", "headband", "circlet", "diadem", "tiara", "crown",
    "necklace", "pendant", "choker", "torc", "locket", "amulet", "talisman",
    "earring", "earrings", "brooch", "pin", "badge", "medal", "insignia",
    "bracelet", "bangle", "anklet", "ring", "chain", "cord", "charm",
    "spectacles", "glasses", "monocle", "eyepatch", "watch",
)


def attaches_only(garment):
    """Is this worn AT a region rather than over it? Never fails."""
    text = str(garment or "").casefold()
    return any(re.search(r"\b%ss?\b" % re.escape(cue), text)
               for cue in _ATTACH_CUES)


def regions_covered(garment):
    """Every region a garment name covers, anchor first.

    One entry for most things. A kimono covers three, and must, or opening it
    uncovers a torso while the legs stay mysteriously dressed.
    """
    text = str(garment or "").casefold()
    anchor = region_of(garment)
    for cues, regions in _SPANNING_CUES:
        for cue in cues:
            if re.search(r"\b%ss?\b" % re.escape(cue), text):
                # The anchor stays whatever region_of decided -- a skirt is
                # legs-anchored and a dress torso-anchored, and both are right.
                return (anchor,) + tuple(r for r in regions if r != anchor)
    return (anchor,)


def region_of(garment):
    """Which region a garment name belongs to. Never fails; see DEFAULT_REGION."""
    text = str(garment or "").casefold()
    if not text.strip():
        return DEFAULT_REGION
    best, best_at = DEFAULT_REGION, None
    for region, cues in _REGION_CUES:
        for cue in cues:
            match = re.search(r"\b%ss?\b" % re.escape(cue), text)
            if not match:
                continue
            # The LAST cue in the phrase wins: English puts the noun at the end,
            # so "leather riding boots" is boots and "boot-black apron" is an
            # apron.
            if best_at is None or match.start() > best_at:
                best, best_at = region, match.start()
    return best


# One region's worth of body description. Bounded because every one of these
# is rendered into a prompt on every beat that uncovers it, and seven unbounded
# fields on a card is an unbounded context; generous because the thing being
# bounded is prose a person wrote or asked for, and a description that stops
# mid-sentence reads as a bug to whoever meets it.
BENEATH_LIMIT = 400
# A NAME, not a description: "a ceremonial kimono", not the paragraph about its
# brocade. Short because it is also the matching key -- the Director says
# "remove the kimono", `decisive_targets` looks for the head noun, and both of
# those work on a handle rather than on a hundred words. What the garment
# actually looks like goes in `description`, which is why this can stay tight.
GARMENT_NAME_LIMIT = 120
DESCRIPTION_LIMIT = 400
# What has happened TO a garment -- stained, torn, soaked, scorched. Short by
# nature: it is a clause about one thing, not a description of it.
CONDITION_LIMIT = 160


# How a model writes a garment when given one field for it: the handle, a
# dash, and then everything else. Splitting there recovers both halves instead
# of cutting the sentence off at the name limit.
_NAME_SPLIT = re.compile(r"\s*(?:\u2014|\u2013|--|\s-\s|:)\s*")
# The longest a head can be and still read as a name rather than as the first
# clause of a sentence that happens to contain a dash.
_NAME_HEAD = 60


def split_garment_name(text, description=""):
    """A garment's (name, description), however the two arrived joined.

    Generators reliably write "Ceremonial kimono - deep vermillion silk
    brocade, gold-thread motifs woven through the fabric" as a single name.
    Truncating that at the name limit threw the description away and left the
    sentence cut mid-clause; keeping it whole made a hundred-word matching key
    whose "head noun" was whatever adjective happened to land last.

    Split whenever the shape is there, not only when the name is too long: a
    100-character name is under the limit and still a bad matching key. The
    head has to look like a name, though -- short, and left of the separator --
    so a hyphenated garment ("split-toed socks") stays one thing.
    """
    text = " ".join(str(text or "").split())
    description = " ".join(str(description or "").split())
    parts = _NAME_SPLIT.split(text, 1)
    if len(parts) == 2 and parts[0] and len(parts[0]) <= _NAME_HEAD:
        return parts[0], description or parts[1]
    return text, description


def _clean(text, limit=BENEATH_LIMIT):
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    cut = text[:limit]
    # Cut on a word boundary. Slicing a string at a byte count lands mid-word
    # roughly every time, and "old scars across the ri" is worse than the
    # sentence it replaced. Only honour the boundary if it is not so far back
    # that obeying it would throw away most of the field.
    space = cut.rfind(" ")
    if space > limit * 0.6:
        cut = cut[:space]
    return cut.rstrip(" ,;:-—")


def normalize_regions(outfit):
    """Any outfit shape -- old flat list or new regions -- as regions.

    Backwards compatibility is not optional here: every card and every live
    story predates this, and a character whose clothes vanished on upgrade
    would be worse than no feature at all. A flat `wearing` list is sorted into
    regions by name; anything unrecognisable lands on the torso rather than
    being dropped.
    """
    outfit = outfit if isinstance(outfit, dict) else {}
    out = {}
    spanning = {}
    authored = outfit.get("regions")
    if isinstance(authored, dict):
        for region, entry in authored.items():
            region = str(region or "").strip().casefold()
            if region not in REGIONS or not isinstance(entry, dict):
                continue
            garments = []
            for item in entry.get("garments") or []:
                if isinstance(item, str):
                    item = {"name": item}
                if not isinstance(item, dict):
                    continue
                name, description = split_garment_name(
                    item.get("name"), item.get("description"))
                name = _clean(name, GARMENT_NAME_LIMIT)
                if not name:
                    continue
                # Nobody wears "removed". A note whose whole text was a state
                # used to be read as naming a garment, so two live bodies ended
                # up carrying `{"name": "removed", "state": "worn"}` and
                # `{"name": "worn", ...}` in their regions -- and therefore in
                # the `wearing` list the character reads about itself. The note
                # path no longer mints these; dropping them here is what heals
                # the stories already holding one, on the next beat that
                # touches the ledger, without a migration.
                if is_bare_garment_state(name):
                    continue
                state = str(item.get("state") or "worn").strip().casefold()
                attaches = item.get("attaches")
                garment = {
                    "name": name,
                    # Worn AT this region rather than over it -- see
                    # _ATTACH_CUES. Authored wins; the cue table is the guess.
                    "attaches": (bool(attaches) if attaches is not None
                                 else attaches_only(name)),
                    # What it LOOKS like. Separate from the name because the
                    # name is a matching key -- see split_garment_name.
                    "description": _clean(description, DESCRIPTION_LIMIT),
                    "state": state if state in GARMENT_STATES else "worn",
                    # What has HAPPENED to this garment -- stained, torn, wet,
                    # scorched. Distinct from `state`, which is only how far
                    # off the body it is. A shirt can be soaked and still worn.
                    "condition": _clean(item.get("condition"), CONDITION_LIMIT),
                }
                garments.append(garment)
                # A dress covers torso and legs; a coat, torso and arms. The
                # garment is recorded in every region it covers, and the sync
                # pass below keeps those copies one garment.
                #
                # `auto` is the editor's "work it out from the name" choice:
                # resolved HERE rather than in the browser, so the cue table
                # has exactly one implementation.
                extras = list(item.get("covers") or [])
                if item.get("auto"):
                    extras = list(regions_covered(name))
                for extra in extras:
                    extra = str(extra or "").strip().casefold()
                    if extra in REGIONS and extra != region:
                        spanning.setdefault(extra, []).append(dict(garment))
            beneath = _clean(entry.get("beneath"))
            if garments or beneath:
                out[region] = {"garments": garments, "beneath": beneath}
    # The legacy list, folded in under whatever the authored regions did not
    # already say. Additive: an author who wrote regions is not overruled by
    # the flat list their card also carries.
    #
    # Placed is checked across ALL regions, not just the one `region_of` picks.
    # An author who deliberately put a sash on the torso has a card whose flat
    # list still says "silk sash", and the cue table says waist -- so a
    # per-region check would file a second copy of the same garment on a second
    # body part, which is the three-outfits bug this module exists to end.
    placed = [g["name"] for entry in out.values() for g in entry["garments"]]
    for name in outfit.get("wearing") or []:
        name, description = split_garment_name(name)
        name = _clean(name, GARMENT_NAME_LIMIT)
        # Resolved, not compared. A flat list still naming the garment by the
        # spelling it had before a region edit renamed it would otherwise file
        # a SECOND copy of it -- the three-outfits bug, arriving by the one
        # door the exact-match check left open.
        # Same guard as the authored branch above: nobody wears "removed".
        # This is the door the phantom actually came back through -- dropping
        # it from the regions is undone one loop later if the flat `wearing`
        # list still names it, because that list is where it also landed.
        if not name or is_bare_garment_state(name):
            continue
        if resolve_garment(name, placed, allow_head_noun=False):
            continue
        attaches = attaches_only(name)
        # Every region it covers, not just its anchor. A kimono placed on the
        # torso alone reports legs and groin as bare while it is still on. An
        # ornament is only ever at ONE place: a necklace is at the throat, not
        # across the shoulders it hangs near.
        for region in ((region_of(name),) if attaches else regions_covered(name)):
            entry = out.setdefault(region, {"garments": [], "beneath": ""})
            entry["garments"].append(
                {"name": name, "description": _clean(description, DESCRIPTION_LIMIT),
                 "attaches": attaches, "state": "worn", "condition": ""})
        placed.append(name)
    for region, garments in spanning.items():
        entry = out.setdefault(region, {"garments": [], "beneath": ""})
        for garment in garments:
            if not any(g["name"].casefold() == garment["name"].casefold()
                       for g in entry["garments"]):
                entry["garments"].append(garment)
    return _sync_spanning_garments(dedupe_regions(out))


def authored_entry(wearing=None, state=None, regions=None):
    """One body's authored starting clothes as a live attire-ledger entry.

    The card keeps its two representations apart -- a flat list plus whatever
    the author placed by region -- and this is the single place they become the
    one thing the story runs on. Both the scene seed and the opening turn's
    restore-over-model-output go through here, because two spellings of this
    merge would eventually disagree about the same body.
    """
    merged = normalize_regions({"wearing": wearing, "regions": regions})
    return {
        "wearing": flat_wearing(merged) or [n for n in (wearing or []) if n],
        "state": [str(s).strip() for s in (state or []) if str(s or "").strip()],
        "regions": merged,
    }


def _sync_spanning_garments(regions):
    """A garment covering several regions is ONE garment, not several.

    Without this, loosening a kimono at the torso leaves its sleeves and skirts
    fastened -- and a stain on one copy is invisible on the others. So after
    any change, every copy of a name takes the FURTHEST state any copy reached
    (if part of it is off, it is off) and the condition any copy carries.

    `covers` is written back onto each copy so the editor and the prompts can
    say what a garment actually is, rather than showing it as several unrelated
    things that happen to share a name.
    """
    regions = regions or {}
    furthest, marks, descriptions, spans = {}, {}, {}, {}
    for region in REGIONS:
        for garment in (regions.get(region) or {}).get("garments") or []:
            key = garment.get("name", "").casefold()
            furthest[key] = max(furthest.get(key, 0),
                                _rung(garment.get("state", "worn")))
            if garment.get("condition") and not marks.get(key):
                marks[key] = garment["condition"]
            if garment.get("description") and not descriptions.get(key):
                descriptions[key] = garment["description"]
            spans.setdefault(key, []).append(region)
    for region in REGIONS:
        for garment in (regions.get(region) or {}).get("garments") or []:
            key = garment.get("name", "").casefold()
            garment["state"] = GARMENT_STATES[furthest[key]]
            if marks.get(key):
                garment["condition"] = marks[key]
            if descriptions.get(key):
                garment["description"] = descriptions[key]
            garment["covers"] = (list(spans[key]) if len(spans[key]) > 1
                                 else [])
    return regions


def covered_regions(regions):
    """Which regions still have something on them."""
    # Anatomical order, not alphabetical: "torso, waist, groin, legs" is a
    # body, and "groin, legs, torso, waist" is a word list.
    return [
        region for region in REGIONS
        if any(g.get("state") != "removed" and not g.get("attaches")
               for g in ((regions or {}).get(region) or {}).get("garments") or [])
    ]


def exposed_regions(regions):
    """Which regions have nothing left covering them.

    A region with no garments at all counts as exposed -- bare hands are bare,
    not unmodelled. A region nobody ever mentioned is simply absent from
    `regions` and so appears in neither list.
    """
    return [
        region for region in REGIONS
        if region in (regions or {})
        and not any(g.get("state") != "removed" and not g.get("attaches")
                    for g in ((regions or {}).get(region) or {}).get("garments") or [])
    ]


def _rung(state):
    try:
        return GARMENT_STATES.index(state)
    except ValueError:
        return 0


# Ways a player can say "yes, all the way, now" -- which is the one thing that
# lifts the one-step-per-beat rule. Deliberately about INTENT rather than
# vocabulary: "she tears it off" is decisive, "she works at the buttons" is not.
_DECISIVE = re.compile(
    r"\b(strips?|stripped|stripping|tears?|tore|tearing|rips?|ripped|ripping"
    r"|yanks?|yanked|yanking|wrenche?s?|wrenched|wrenching"
    r"|throws? off|threw off|throwing off|hurls? (?:it |them )?(?:aside|away)"
    r"|pulls? (?:it |them )?off|pulled (?:it |them )?off|pulling (?:it |them )?off"
    r"|shrugs? out of|shrugged out of|shrugging out of"
    r"|kicks? off|kicked off|kicking off|casts? (?:it |them )?aside"
    r"|flings? (?:it |them )?(?:aside|away|off)|flung (?:it |them )?(?:aside|away|off)"
    r"|cuts? (?:it |them )?(?:off|away)|slices? (?:it |them )?(?:off|away)"
    r"|in one motion|in a single motion|all at once"
    r"|fully undress\w*|completely undress\w*|naked|nude|bare(?:s|d)? (?:her|him|them)self)\b",
    re.IGNORECASE)

_SENTENCE = re.compile(r"[^.!?\n]+")


def decisive_intent(text):
    """Did somebody ask for the whole thing at once?"""
    return bool(_DECISIVE.search(str(text or "")))


_ARTICLE = re.compile(r"^(?:a|an|the|his|her|their|its|my|your)\s+", re.I)
_FIRST_PERSON = re.compile(r"\b(i|me|my|mine|myself)\b", re.I)


def _garment_keys(name):
    """A garment as (full phrase, head noun), both casefolded.

    The phrase is what a card wrote ("a silk sash"); prose says "the sash".
    English puts the noun last, so the last word is the handle a sentence is
    most likely to use.
    """
    text = _ARTICLE.sub("", " ".join(str(name or "").split())).casefold()
    if not text:
        return "", ""
    return text, text.split()[-1]


# How short a phrase may be before containment stops being evidence of
# identity. "robe" is inside "wardrobe"; "silk" is inside half a wardrobe.
_CONTAINMENT_FLOOR_WORDS = 2
_CONTAINMENT_FLOOR_CHARS = 8


def resolve_garment(name, worn_names, allow_head_noun=True):
    """Which garment already on this body a handle refers to, or None.

    The disease this cures: the ledger keyed garments on `name.casefold()`, and
    the Director writes the name fresh every beat. Measured live -- turn 0
    registered "sheer obsidian silk robe that parts with every movement", a
    later beat said "sheer obsidian silk robe", and the body ended up wearing
    two robes, one of them duplicated across four regions.

    So the garment IN the ledger is canonical and every incoming handle is
    resolved against it. Four tiers, narrowing:

      1. exact,
      2. article-stripped phrase equality ("the robe" is "robe"),
      3. phrase containment, in either direction -- this is the measured case,
      4. head noun ("robe", "sash") appearing anywhere in the worn phrase, but
         only when exactly ONE worn garment carries it. Two robes make the
         handle ambiguous, and an ambiguous handle must resolve to nothing
         rather than to a coin flip.

    Tier 4 does not compare head noun to head noun, because `_garment_keys`
    reads the LAST word as the noun and the names models write are not always
    shaped that way: the live "sheer obsidian silk robe that parts with every
    movement" has a head noun of "movement". Uniqueness is what makes the
    looser match safe, not position.

    Containment is floored at `_CONTAINMENT_FLOOR_*` so a bare adjective
    cannot swallow a wardrobe, and tier 4 is optional because the caller that
    MERGES garments must be stricter than the caller that merely routes a note
    at one: merging "silk robe" into "cotton robe" destroys a garment, while
    routing a note at the wrong robe is a wrong sentence.
    """
    handle, head = _garment_keys(name)
    if not handle:
        return None
    # Deduped first. A spanning garment is recorded once per region it covers,
    # so a robe across torso/waist/groin/legs arrives here four times -- and
    # tier 4's uniqueness guard would read those four copies as four different
    # robes and refuse to resolve anything.
    worn, seen = [], set()
    for name_ in (worn_names or []):
        text = str(name_ or "").strip()
        if text and text.casefold() not in seen:
            seen.add(text.casefold())
            worn.append(text)
    keyed = [(n, *_garment_keys(n)) for n in worn]

    for original in worn:                                       # 1
        if original.casefold() == str(name).casefold():
            return original
    for original, phrase, _ in keyed:                           # 2
        if phrase and phrase == handle:
            return original
    for original, phrase, _ in keyed:                           # 3
        if not phrase:
            continue
        short, long = sorted((phrase, handle), key=len)
        if len(short.split()) < _CONTAINMENT_FLOOR_WORDS \
                and len(short) < _CONTAINMENT_FLOOR_CHARS:
            continue
        if re.search(r"\b%s\b" % re.escape(short), long):
            return original
    if not allow_head_noun or len(head) <= 3:                   # 4
        return None
    noun = re.compile(r"\b%s\b" % re.escape(head))
    hits = [original for original, phrase, worn_head in keyed
            if worn_head == head or (phrase and noun.search(phrase))]
    return hits[0] if len(hits) == 1 else None


def dedupe_regions(regions):
    """Collapse two records of ONE garment back into one, on read.

    A redescription forked the garment; this is where the fork heals, and it
    runs on every read (`normalize_regions`) so that the ~49 scenes already
    carrying a forked wardrobe repair themselves lazily rather than through a
    migration that would rewrite stories mid-play. Idempotent, because a
    checkpoint restore must not be able to make it oscillate.

    Strictly tier 1-3: a bare head noun never merges, so "silk robe" and
    "cotton robe" stay two robes. What survives the merge is the FURTHEST
    state (consistent with `_sync_spanning_garments` -- if part of it is off,
    it is off), every distinct condition, the longest description, and the
    first-registered name as the handle. The discarded name's surplus wording
    is folded into the description rather than dropped: the redescription was
    the author saying something, and this heals the fork without losing it.
    """
    regions = regions or {}
    canonical = []            # first-registered name order, across all regions
    merged = {}               # canonical key -> accumulated garment facts
    for region in REGIONS:
        for garment in (regions.get(region) or {}).get("garments") or []:
            name = garment.get("name", "")
            if not name:
                continue
            target = resolve_garment(name, canonical, allow_head_noun=False)
            if target is None:
                canonical.append(name)
                target = name
            key = target.casefold()
            record = merged.setdefault(
                key, {"name": target, "rung": 0, "conditions": [],
                      "description": "", "surplus": []})
            record["rung"] = max(record["rung"], _rung(garment.get("state", "worn")))
            mark = str(garment.get("condition") or "").strip()
            if mark and mark not in record["conditions"]:
                record["conditions"].append(mark)
            description = str(garment.get("description") or "").strip()
            if len(description) > len(record["description"]):
                record["description"] = description
            if name.casefold() != key:
                record["surplus"].append(name)

    if not any(record["surplus"] for record in merged.values()):
        return regions   # nothing forked: leave every object untouched

    for record in merged.values():
        # The longer of the two spellings usually carries the detail the
        # shorter one dropped. Keep it where descriptions live.
        for surplus in record["surplus"]:
            phrase, _ = _garment_keys(surplus)
            handle, _ = _garment_keys(record["name"])
            extra = phrase.replace(handle, " ").strip(" ,;-")
            if extra and extra not in record["description"].casefold():
                record["description"] = _clean(
                    ("%s %s" % (record["description"], extra)).strip(),
                    DESCRIPTION_LIMIT)

    out = {}
    for region in REGIONS:
        entry = regions.get(region)
        if not isinstance(entry, dict):
            continue
        garments, kept = [], set()
        for garment in entry.get("garments") or []:
            name = garment.get("name", "")
            target = resolve_garment(name, canonical, allow_head_noun=False) or name
            key = target.casefold()
            if not key or key in kept:
                continue      # both forks landed in this region: one survives
            kept.add(key)
            record = merged.get(key) or {}
            garments.append(dict(
                garment,
                name=record.get("name", name),
                state=GARMENT_STATES[record.get("rung", 0)],
                condition=_clean("; ".join(record.get("conditions") or []),
                                 CONDITION_LIMIT),
                description=record.get("description") or garment.get("description", ""),
            ))
        out[region] = {"garments": garments, "beneath": entry.get("beneath") or ""}
    return out


# Attire-diff keys that name the wardrobe as a whole rather than one garment.
_GENERIC_WARDROBE_KEYS = frozenset({
    "clothing", "clothes", "outfit", "attire", "garments", "dress", "wear",
})

# Values that assert nothing changed. Kept small and closed on purpose: a
# note this engine cannot read is kept, not guessed at.
_NO_CHANGE_NOTES = frozenset({
    "undisturbed", "unchanged", "intact", "as before", "same", "no change",
    "none", "unaffected", "untouched", "still on", "as is",
})

_DIFF_KNOWN_KEYS = ("wearing", "add", "remove", "replace", "state",
                    "conditions", "regions", "notes")


def is_no_change_note(text):
    """Does this note say, in as many words, that nothing happened?"""
    return str(text or "").strip().casefold().strip(".") in _NO_CHANGE_NOTES


# Words that describe what happened TO a garment rather than naming one. A note
# whose whole text is one of these ("removed", "worn") is a state, and reading
# it as a garment name mints clothing called "removed" -- which is exactly what
# chat 52 was carrying on two bodies. Kept to the closed `GARMENT_STATES`
# vocabulary plus the handful of plain synonyms a Director actually writes; a
# word not on this list is still treated as a garment, because inventing one is
# recoverable and dropping real clothing is not.
_BARE_STATE_WORDS = frozenset(GARMENT_STATES) | frozenset({
    "on", "off", "shed", "gone", "gone now", "gone entirely", "taken off",
    "put on", "gone from her", "discarded", "gone completely",
})
_REMOVAL_STATE_WORDS = frozenset({
    "removed", "off", "shed", "gone", "gone now", "gone entirely", "taken off",
    "discarded", "gone from her", "gone completely",
})


def is_bare_garment_state(text):
    """Is this note's whole text a state, with no garment named in it?"""
    return str(text or "").strip().casefold().strip(".") in _BARE_STATE_WORDS


def is_removal_state(text):
    """Of the bare states, does this one mean the garment came OFF?"""
    return str(text or "").strip().casefold().strip(".") in _REMOVAL_STATE_WORDS


def coerce_diff_shape(diff):
    """One body's attire diff, canonicalized -- so an off-schema one is READ
    rather than silently discarded.

    `StateDiff.attire` was `dict[str, dict]` with an untyped inner dict, and
    commit's loop handles exactly `wearing` / `add` / `remove` / `replace` /
    `state` / `conditions`. Anything else validated cleanly as a dict and then
    fell through the loop doing nothing at all. Two of the six attire diffs in
    the measured story were silent no-ops:

        {"Elyndra": {"robe": "sheer, parted"}, "Hinami": {"clothing": "undisturbed"}}
        {"Hinami": {"shift": "linen shift, hem rucked up where her hand slipped beneath"}}

    That second one is specific authored detail about a garment the ledger had
    never heard of, thrown away -- which is why the story's narration could say
    "the hem of your shift" and "the waistband of your shorts" in one
    paragraph. So unknown keys are not dropped: they become `notes`
    {handle: text}, and commit resolves each handle against the wardrobe.

    Also canonicalized here: `state` written as a garment-keyed DICT, which is
    the `conditions` field spelled differently (one live beat used `state` for
    it and a later beat used `conditions` for the same sentence). Idempotent,
    and pure, because commit must run it too -- rerun-from-stage replays diffs
    stored before this existed.
    """
    if not isinstance(diff, dict):
        return {}
    out, notes = {}, {}
    for key, value in diff.items():
        name = str(key or "").strip()
        if not name:
            continue
        if name == "notes":
            if isinstance(value, dict):
                for handle, text in value.items():
                    handle = str(handle or "").strip()
                    if handle:
                        notes[handle] = _flatten_note(text)
            continue
        if name == "state":
            if isinstance(value, dict):
                # A garment-keyed dict is `conditions`, whatever it is called.
                marks = dict(out.get("conditions") or {})
                for handle, text in value.items():
                    handle = str(handle or "").strip()
                    if handle:
                        marks.setdefault(handle, _flatten_note(text))
                out["conditions"] = marks
            elif value is not None:
                out["state"] = [str(s) for s in _as_list(value)
                                if str(s or "").strip()]
            continue
        if name == "conditions":
            if isinstance(value, dict):
                marks = dict(out.get("conditions") or {})
                for handle, text in value.items():
                    handle = str(handle or "").strip()
                    if handle:
                        marks[handle] = _flatten_note(text)
                out["conditions"] = marks
            continue
        if name in ("wearing", "add", "remove", "replace"):
            if value is None:
                continue
            out[name] = [str(s).strip() for s in _as_list(value)
                         if str(s or "").strip()]
            continue
        if name == "regions":
            # Authored clothing by region -- the opening turn's shape. Passed
            # through untouched; normalize_regions is what reads it.
            if isinstance(value, dict):
                out["regions"] = value
            continue
        notes[name] = _flatten_note(value)
    if notes:
        out["notes"] = notes
    return out


def _as_list(value):
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _flatten_note(value):
    """A note's text, whatever container it arrived in."""
    if isinstance(value, str):
        return " ".join(value.split())
    if isinstance(value, dict):
        return "; ".join("%s %s" % (k, _flatten_note(v)) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return "; ".join(_flatten_note(v) for v in value)
    return "" if value is None else str(value)


# A third-person possessive that is NOT reflexive: "her clothes", "his shirt".
# Its presence means the sentence acts on somebody other than the body it
# names, which is the difference between "Corin strips her clothes off" and
# "Corin strips off".
_OTHERS_POSSESSIVE = re.compile(r"\b(?:her|his|their|its)\b(?!\s*self)",
                                re.IGNORECASE)
_REFLEXIVE = re.compile(r"\b(?:herself|himself|themselves|itself|myself)\b",
                        re.IGNORECASE)


def decisive_targets(player_text, other_texts, wardrobe, player_name=None):
    """WHOSE clothes this beat's words tore off, rather than merely whether.

    A character can be as decisive as the player -- "she rips his shirt open"
    is not a beat spent working at buttons, and the rule exists to stop the
    engine being slower than the fiction, not to make the player the only
    person allowed to hurry. So every voice in the beat is read.

    Scoped PER BODY, because one flag for the whole beat meant the player
    yanking their own coat off undressing everyone standing near them.
    Attribution, in order, because the ACTOR is not the target -- "Corin tears
    the sash from her waist" is Mira being undressed:

      1. the garment. Whoever is wearing what the sentence names, by full
         phrase, or by its head noun when exactly one body is wearing one.
      2. first person, but only in the player's own input, where "I" is a
         subject the sentence never spells out.
      3. a name, when the sentence names exactly one body and no garment.

    Sentence matching is a heuristic, deliberately. It decides how FAST an
    undressing the fiction already asked for happens, never who may know what,
    so it is not load-bearing for the information firewall -- see
    docs/UNBUILT.md §3.1 on why prose matching is not allowed to be a boundary.
    """
    wardrobe = wardrobe if isinstance(wardrobe, dict) else {}
    keys = {name: [_garment_keys(g) for g in (garments or [])]
            for name, garments in wardrobe.items()}
    sources = [(str(player_text or ""), True)]
    for text in (other_texts if isinstance(other_texts, (list, tuple))
                 else [other_texts]):
        sources.append((str(text or ""), False))

    hits = set()
    for text, is_player in sources:
        for sentence in _SENTENCE.findall(text):
            if not _DECISIVE.search(sentence):
                continue
            folded = sentence.casefold()
            words = set(re.findall(r"[a-z0-9\-\u2019\']+", folded))

            by_phrase = {name for name, entries in keys.items()
                         if any(phrase and phrase in folded
                                for phrase, _noun in entries)}
            if by_phrase:
                hits |= by_phrase
                continue
            by_noun = {name for name, entries in keys.items()
                       if any(noun and len(noun) > 3 and noun in words
                              for _phrase, noun in entries)}
            if len(by_noun) == 1:
                hits |= by_noun
                continue
            if is_player and player_name in wardrobe and _FIRST_PERSON.search(sentence):
                hits.add(player_name)
                continue
            named = {name for name in wardrobe
                     if str(name or "").strip() and re.search(
                         r"\b%s\b" % re.escape(str(name).casefold()), folded)}
            if len(named) == 1:
                # THE ACTOR IS NOT THE TARGET, and this fallback used to make
                # them one. "Corin strips her clothes off in one motion" names
                # no garment the wardrobe knows -- "clothes" is not a garment
                # -- so it fell to here, found exactly one name, and marked
                # CORIN as the one being undressed. The person actually losing
                # the shift stayed clamped to one rung, which is the reported
                # symptom: a motion that plainly takes clothing off only
                # reaching `loosened`.
                #
                # A non-reflexive third-person possessive is the tell. With
                # one, the sentence acts on somebody else, so the named body is
                # the wrong answer: attribute to the only OTHER dressed body if
                # there is exactly one, and otherwise to nobody. Undressing the
                # wrong person faster is a worse error than undressing the
                # right one slowly.
                if (_OTHERS_POSSESSIVE.search(sentence)
                        and not _REFLEXIVE.search(sentence)):
                    others = {name for name in wardrobe if name not in named
                              and (wardrobe.get(name) or [])}
                    if len(others) == 1:
                        hits |= others
                    continue
                hits |= named
                continue
            # Nobody identifiable, or several equally plausible. The player's
            # own words default to the player; ambiguous prose from anywhere
            # else undresses no one faster than the ordinary rung.
            if is_player and not named and not by_noun and player_name in wardrobe:
                hits.add(player_name)
    return hits


def advance(previous, proposed, decisive=False):
    """Reconcile a proposed set of regions against what was true before.

    The rule: a garment may move ONE rung down `GARMENT_STATES` per beat.
    Putting something back on, or getting further dressed, is unrestricted --
    the asymmetry is deliberate, because it is undressing that the engine kept
    doing instantly and it is undressing that has a dramatic middle worth
    staying in.

    `decisive` lifts the limit for this beat, for a player who said so.

    Returns the reconciled regions. Anything the proposal invented (a new
    garment, a new region) is kept; this clamps a transition, it does not
    police the wardrobe.
    """
    previous = previous if isinstance(previous, dict) else {}
    proposed = proposed if isinstance(proposed, dict) else {}
    out = {}
    for region, entry in proposed.items():
        was = {g.get("name", "").casefold(): g
               for g in ((previous.get(region) or {}).get("garments") or [])}
        garments = []
        for garment in entry.get("garments") or []:
            name = garment.get("name", "")
            before = was.get(name.casefold())
            state = garment.get("state", "worn")
            if before and not decisive:
                gap = _rung(state) - _rung(before.get("state", "worn"))
                if gap > 1:
                    # Two rungs in one beat: hold it at the next one. This is
                    # the line that keeps "begins to untie her sash" from
                    # arriving at bare in the same paragraph.
                    state = GARMENT_STATES[_rung(before.get("state", "worn")) + 1]
            # Condition survives a rung change on its own terms: a proposal
            # that says nothing about it must not launder the garment, and a
            # proposal that DOES say something is this beat's news.
            condition = _clean(garment.get("condition"), CONDITION_LIMIT)
            if not condition and before:
                condition = before.get("condition") or ""
            description = _clean(garment.get("description"), DESCRIPTION_LIMIT)
            if not description and before:
                description = before.get("description") or ""
            garments.append({"name": name, "description": description,
                             "attaches": bool(garment.get("attaches")
                                              if garment.get("attaches") is not None
                                              else (before or {}).get("attaches")),
                             "state": state, "condition": condition})
        out[region] = {"garments": garments,
                       "beneath": entry.get("beneath")
                       or (previous.get(region) or {}).get("beneath") or ""}
    # A region the proposal simply did not mention is unchanged, not undressed.
    for region, entry in previous.items():
        out.setdefault(region, entry)
    # One garment across several regions moves as one thing -- otherwise
    # loosening a kimono at the torso leaves its sleeves fastened.
    return _sync_spanning_garments(out)


def _garment_text(garment):
    """One garment as a phrase: what it is, how far off, what has happened.

    Both qualifiers go in one bracket rather than two, because "a linen shirt
    (open) (wine-stained down the front)" reads like a bug and "a linen shirt
    (open, wine-stained down the front)" reads like a sentence.
    """
    notes = []
    if garment.get("state") not in (None, "worn"):
        notes.append(garment["state"])
    if garment.get("condition"):
        notes.append(garment["condition"])
    if not notes:
        return garment["name"]
    return "%s (%s)" % (garment["name"], ", ".join(notes))


def describe(regions, beneath_visible=False, body=""):
    """One readable line per region, for a prompt or a panel.

    `beneath_visible` is the per-story choice about whether what is UNDER the
    clothing is spelled out. With it off, an exposed region says only that it
    is exposed; the body's own description is what fills the gap, which is
    where it lived before this module existed.
    """
    lines = []
    for region in REGIONS:
        entry = (regions or {}).get(region)
        if not entry:
            continue
        worn = [g for g in entry.get("garments") or [] if g.get("state") != "removed"]
        if worn:
            pieces = []
            outer_seen = False
            for garment in worn:
                text = _garment_text(garment)
                if garment.get("attaches"):
                    text += " [worn at, covers nothing]"
                elif outer_seen:
                    # Layering. An under-kimono beneath a kimono is not on
                    # show, and telling the Director it is invites prose
                    # describing clothes nobody can see.
                    text += " [under the above]"
                else:
                    outer_seen = True
                # Said once, on the first region it covers, so a reader can
                # tell one kimono across five regions from five garments --
                # and so its description is not repeated five times.
                covers = garment.get("covers") or []
                anchored = not covers or covers[0] == region
                if covers and anchored:
                    text += " [one garment, covering %s]" % ", ".join(covers)
                if anchored and garment.get("description"):
                    text += " — %s" % garment["description"]
                pieces.append(text)
            lines.append("%s: %s" % (region, ", ".join(pieces)))
            continue
        if beneath_visible:
            beneath = entry.get("beneath") or _clean(body)
            lines.append("%s: bare%s" % (region, " — %s" % beneath if beneath else ""))
        else:
            lines.append("%s: bare" % region)
    return lines


def apply_flat_change(previous, wanted, decisive=False, conditions=None):
    """Reconcile a flat "what they are wearing now" list against the regions.

    The Director speaks in whole garments -- add these, remove those -- because
    that is the shape a model reliably produces. Removing one therefore means
    "gone", which is precisely the instant undress this module exists to stop.
    So a removal is read as a PROPOSAL to reach `removed`, and the one-rung
    rule decides how far it actually gets this beat.

    `conditions` maps a garment name to what has just happened to it -- spilled
    wine, a tear, soaking. It belongs to the GARMENT rather than to the body,
    so that taking the shirt off leaves the stain on the shirt.

    Returns the reconciled regions. Deriving the flat list back out of them is
    `flat_wearing`, and the two must be written together or the ledger says two
    different things about the same body.
    """
    previous = previous if isinstance(previous, dict) else {}
    # Every handle the caller supplied is resolved against the garments this
    # body is ALREADY wearing before it is matched. Without it, a beat naming
    # the robe by a shorter phrase read as "the robe is not in the wanted list"
    # (so: start removing it) AND "this wanted garment is not worn" (so: add
    # it) at the same time -- which is exactly how one robe became two, one of
    # them halfway off.
    worn_names = [g.get("name", "")
                  for entry in previous.values()
                  for g in (entry.get("garments") or [])
                  if g.get("name")]
    marks = {}
    for handle, text in (conditions or {}).items():
        if not str(text or "").strip():
            continue
        resolved = resolve_garment(handle, worn_names) or str(handle)
        marks[resolved.casefold()] = _clean(text, CONDITION_LIMIT)
    wanted_keys = {}
    for name in (wanted or []):
        resolved = resolve_garment(name, worn_names, allow_head_noun=False) or str(name)
        wanted_keys[resolved.casefold()] = resolved
    proposed = {}
    seen = set()
    for region, entry in previous.items():
        garments = []
        for garment in entry.get("garments") or []:
            key = garment.get("name", "").casefold()
            seen.add(key)
            garment = dict(garment)
            if key in marks:
                garment["condition"] = marks[key]
            still_listed = key in wanted_keys
            if still_listed:
                # Named as still worn: hold whatever partial state it had
                # rather than snapping it back to pristine, or a beat that
                # mentions the robe would silently re-fasten it.
                garments.append(dict(garment))
            else:
                garments.append(dict(garment, state="removed"))
        proposed[region] = {"garments": garments,
                            "beneath": entry.get("beneath") or ""}
    for key, name in wanted_keys.items():
        if key in seen:
            continue
        for region in regions_covered(name):
            entry = proposed.setdefault(region, {"garments": [], "beneath": ""})
            entry["garments"].append({"name": name, "state": "worn",
                                      "condition": marks.get(key, "")})
    return advance(previous, proposed, decisive)


def condition_of(regions, garment_name):
    """What has happened to one named garment. Empty when nothing has."""
    key = str(garment_name or "").casefold()
    for entry in (regions or {}).values():
        for garment in entry.get("garments") or []:
            if garment.get("name", "").casefold() == key:
                return garment.get("condition") or ""
    return ""


def newly_removed(previous, reconciled):
    """Garments that came off THIS beat: [(region, name), ...].

    A garment that leaves a body does not stop existing. It is on the floor,
    over a chair, in someone's hand -- findable, takeable, and something the
    story can refer to later. The commit path turns each of these into a real
    object in the room; this module only reports which ones crossed the line,
    because reaching into the scene from here would make a pure model into a
    world writer.
    """
    was = {}
    for region, entry in (previous or {}).items():
        for garment in entry.get("garments") or []:
            was[(region, garment.get("name", "").casefold())] = garment.get("state")
    out, reported = [], set()
    for region in REGIONS:
        for garment in ((reconciled or {}).get(region) or {}).get("garments") or []:
            name = garment.get("name", "")
            key = (region, name.casefold())
            if garment.get("state") != "removed" or was.get(key) == "removed":
                continue
            # ONCE per garment, not once per region it covered. A kimono is one
            # thing; four copies of it on the floor is not what came off.
            if name.casefold() in reported:
                continue
            reported.add(name.casefold())
            out.append((region, name))
    return out


def flat_wearing(regions):
    """The garments still on the body, for everything that reads the old shape.

    A garment that is loosened or hanging open is STILL BEING WORN -- dropping
    it from this list the moment it was touched is how a half-undone robe
    became no robe at all.
    """
    out = []
    for region in REGIONS:
        for garment in ((regions or {}).get(region) or {}).get("garments") or []:
            if garment.get("state") != "removed" and garment["name"] not in out:
                out.append(garment["name"])
    return out


def flat_state(regions):
    """Short human-readable notes for anything not simply worn or gone.

    This is what the old free-text `state` list was carrying badly: it is now
    derived from the regions rather than being the only place partial undress
    could live.
    """
    notes, reported = [], set()
    for region in REGIONS:
        entry = (regions or {}).get(region) or {}
        for garment in entry.get("garments") or []:
            # ONCE per garment, not once per region it spans -- the same rule
            # `flat_wearing` and `newly_removed` already keep. A robe covering
            # torso, waist, groin and legs was reporting itself loosened four
            # times, and the duplicate notes were what the narrator read.
            key = garment.get("name", "").casefold()
            if garment.get("state") in ("loosened", "open") and key not in reported:
                reported.add(key)
                notes.append("%s %s" % (garment["name"], garment["state"]))
    bare = exposed_regions(regions)
    if bare:
        notes.append("bare at the %s" % ", ".join(bare))
    return notes


def is_derived_state_note(note):
    """Did `flat_state` write this note, on this beat or an earlier one?

    It emits exactly two shapes -- "bare at the <regions>" and
    "<garment> loosened"/"<garment> open" -- so recognising them is closed and
    cheap. Anything else is prose somebody chose, and is kept.
    """
    text = " ".join(str(note or "").split()).casefold().strip(".")
    if not text:
        return False
    if text.startswith("bare at the "):
        return True
    return any(text.endswith(" " + state) for state in ("loosened", "open"))


def rederive_entry(entry):
    """One attire ledger entry with its three representations agreeing again.

    `wearing`, `state` and `regions` are the same wardrobe said three ways, and
    only the commit path was keeping them in step -- the attire EDITOR
    (app.attire_put) stored whatever the browser sent, verbatim. That is where
    the measured fork actually began: a garment renamed by hand in the region
    editor left `wearing` still naming the old spelling, and the next beat's
    reconciliation dutifully treated the two spellings as two garments, adding
    one back while it took the other off.

    Authored prose in `state` survives -- only the DERIVED notes are rebuilt.
    """
    entry = entry if isinstance(entry, dict) else {}
    regions = normalize_regions(entry)
    derived = flat_state(regions)
    # "Not currently derived" is not the same as "authored". A note this
    # function emitted on an EARLIER beat stops matching the moment the body
    # changes, and was then preserved as though a human had written it -- so
    # every successive undress left its predecessor behind. Chat 52 carried
    # three of them at once on one body:
    #
    #   "bare at the head, arms, waist, groin, legs, feet"
    #   "bare at the head, groin, legs"
    #   "bare at the groin"
    #
    # all true at different moments and mutually contradictory as a set, which
    # is what a character reading `state` had to work with. A derived-shaped
    # note is always ours to rebuild, whether or not it is current.
    authored = [str(note) for note in (entry.get("state") or [])
                if isinstance(note, str) and note.strip() and note not in derived
                and not is_derived_state_note(note)]
    return {**entry, "regions": regions,
            "wearing": flat_wearing(regions), "state": derived + authored}
