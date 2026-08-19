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

# A coarse region may have a small, closed set of independently coverable
# surfaces where play actually needs the distinction.  This is deliberately
# not a second anatomy: contacts, injury, position and facing continue to use
# REGIONS.  Zones answer one narrower question -- can a still-worn garment
# expose part of this region? -- without making a condition string such as
# "hem rucked up" executable state.
REGION_ZONES = {
    "torso": ("chest", "midriff"),
}


def zones_of(region):
    """Every region is coverable-or-not; the torso is finer.

    DISPLACEMENT — a still-worn garment no longer covering a place it
    normally covers (a jacket pushed off the shoulders, a skirt hiked to the
    waist, trousers around the ankles) — is a third axis beside the ladder
    (progress toward removal) and the condition (what happened to the
    fabric). It lives in the per-garment `covered_zones` override at REGION
    grain: an unzoned region is its own single zone, so `{waist: []}` means
    "worn, but not covering the waist" and supplying the full list clears it.
    Measured before generalizing (design_notes/17-garment-displacement.md):
    models already wrote region-grain coverage 4 times in the stored corpus
    (`{"sheer silk robe": {"torso": [], "groin": []}}`) and the torso-only
    validator silently dropped every one, while 37% of stored condition
    notes carried displacement language the engine could not read.
    """
    return REGION_ZONES.get(region, (region,))

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


#: Where a garment name stops describing the garment and starts describing
#: where it sits. Not `of`, which is part of the noun phrase ("a ring of
#: keys", "a length of cord").
_PLACEMENT_PHRASE = re.compile(
    r"\b(?:on|at|over|under|underneath|beneath|around|across|through|from"
    r"|with|in|against)\b")


def _last_cue_at(text, cues):
    """Where the LAST of these cues starts in `text`, or None for no match.

    The same rule `region_of` runs on: English puts the noun at the end, so
    the cue furthest into the phrase is the one naming the garment.
    """
    best = None
    for cue in cues:
        for match in re.finditer(r"\b%ss?\b" % re.escape(cue), text):
            if best is None or match.start() > best:
                best = match.start()
    return best


def attaches_only(garment):
    """Is this worn AT a region rather than over it? Never fails.

    THE HEAD NOUN DECIDES, not any ornament word anywhere in the phrase. A
    cord belt is a belt: `cord` sits in the attach table and in the waist cue
    list, and asking whether an attach cue appears ANYWHERE made one
    describing word turn a garment into something that covers nothing --
    which is invisible, because the garment is still worn, still listed,
    still at the right region, and merely conceals it not at all.

    A tie stays attaching, since a word in both tables (`necklace`, `ring`,
    `anklet`) is the same word matching itself: only a covering cue STRICTLY
    later in the phrase -- a noun the ornament word was describing -- turns
    the verdict over.

    And only in the phrase naming the GARMENT. "A key ring on a belt" ends in
    a covering noun that is not what the thing is; the preposition is the
    boundary between what it is and where it hangs. `region_of` deliberately
    keeps reading the whole phrase, because where it hangs is exactly the
    question it answers -- the two functions ask different things about the
    same words.
    """
    text = str(garment or "").casefold()
    head = _PLACEMENT_PHRASE.split(text, 1)[0]
    attach_at = _last_cue_at(head, _ATTACH_CUES)
    if attach_at is None:
        return False
    covering_at = _last_cue_at(
        head, [cue for _region, cues in _REGION_CUES for cue in cues
               if cue not in _ATTACH_CUES])
    return covering_at is None or covering_at <= attach_at


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
    best, best_at, best_len = DEFAULT_REGION, None, 0
    for region, cues in _REGION_CUES:
        for cue in cues:
            match = re.search(r"\b%ss?\b" % re.escape(cue), text)
            if not match:
                continue
            # The LAST cue in the phrase wins: English puts the noun at the end,
            # so "leather riding boots" is boots and "boot-black apron" is an
            # apron.
            #
            # AND ON A TIE, THE LONGER CUE. Two cues can match one string at
            # one offset only when one is a longer spelling of the other, and
            # the longer one is then the more specific description of the same
            # garment -- `girdle-cloth` against `girdle`. Resolving that by
            # table order instead made the specific entry unreachable from the
            # moment it was written, with nothing to notice: the table has an
            # entry for the garment, and the garment lands somewhere else.
            length = match.end() - match.start()
            if best_at is None or (match.start(), length) > (best_at, best_len):
                best, best_at, best_len = region, match.start(), length
    return best


def span_is_a_guess(garment):
    """True when the region tables do not recognise this garment at all.

    `region_of` never fails -- it falls to `DEFAULT_REGION` -- and that is the
    right behaviour, because a garment on the torso is recoverable and a
    garment nowhere is not. What was missing is that the fallback was SILENT
    (docs/UNBUILT.md §2.14): a qipao, a thawb, a sari the table has not learnt
    lands on the torso alone, and nothing says so, so the wrong span is
    discovered when something undresses oddly and the legs turn out to have
    been bare for twenty beats.

    Distinguishing "the table matched torso" from "the table matched nothing
    and torso is the floor" is the whole trick, and it is exactly the state
    `region_of` already computes and discards. Cheap: no model, no lookup
    beyond the regex pass the placement already runs.
    """
    text = str(garment or "").casefold()
    if not text.strip():
        return False
    if attaches_only(text):
        return False   # ornaments are single-place by nature, not by guess
    for _region, cues in _REGION_CUES:
        for cue in cues:
            if re.search(r"\b%ss?\b" % re.escape(cue), text):
                return False
    return True


def guessed_spans(regions):
    """Garments in this ledger whose coverage nothing actually knew.

    Returns the garment names, once each. UNWIRED -- no production caller,
    only tests, and `docs/UNBUILT.md` §2.14 is the register entry. The seam it
    was written for is the commit path handing these to the Director, which
    CAN say what a garment covers and is the only stage with the fiction in
    front of it; that hand-off does not exist, and this docstring described it
    in the present tense, so a reader met a closed feedback loop that is open.
    Measured while it was open: 110 of 560 live worn garment records carry a
    span the cue tables guessed, twenty of them a nagajuban -- a full-length
    under-kimono -- sitting on the torso alone, so those bodies report legs
    and groin bare while wearing one.

    Authored coverage is never re-guessed and so never reported: setting it by
    hand is the escape hatch, and nagging about a choice somebody already made
    is how a warning teaches people to stop reading warnings.
    """
    out, seen = [], set()
    for region in REGIONS:
        for garment in ((regions or {}).get(region) or {}).get("garments") or []:
            name = garment.get("name") or ""
            key = name.casefold()
            if not name or key in seen or garment.get("state") == "removed":
                continue
            if garment.get("placed") or garment.get("covered_zones"):
                continue          # somebody said where this goes
            if span_is_a_guess(name):
                seen.add(key)
                out.append(name)
    return out


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


def _clean_beneath_zones(region, value):
    """Validated authored body descriptions for one region's zones."""
    allowed = REGION_ZONES.get(region) or ()
    if not allowed or not isinstance(value, dict):
        return {}
    out = {}
    for zone in allowed:
        text = _clean(value.get(zone), BENEATH_LIMIT)
        if text:
            out[zone] = text
    return out


def _clean_covered_zones(value):
    """Canonical garment coverage overrides: {region: [zones still covered]}.

    Absence means the garment covers every zone of every region it occupies.
    An empty list is meaningful: the garment remains worn at that region but
    has been displaced enough to cover none of its zones — for an unzoned
    region, "displaced off it" outright.

    THE INVERT GUARD: a non-empty list in which nothing validates (measured
    live: `{"head": ["hair"]}`) is a garment asserted to still cover
    something this vocabulary cannot read. Reading that as [] would flip its
    meaning from "partly covered" to "covers nothing" — so it is skipped,
    keeping whatever was true before. Only an explicitly empty list means
    displaced-off. (The weather `_SYNONYMS` rule: an unreadable term keeps
    what was there, because every default here is the mildest reading.)
    """
    if not isinstance(value, dict):
        return {}
    out = {}
    for region in REGIONS:
        if region not in value:
            continue
        allowed = zones_of(region)
        raw = value.get(region)
        raw = raw if isinstance(raw, (list, tuple, set)) else [raw]
        supplied = [str(zone or "").strip().casefold()
                    for zone in raw if str(zone or "").strip()]
        selected = {zone for zone in supplied if zone in allowed}
        if supplied and not selected:
            continue  # unreadable assertion of coverage: keep the default
        picked = [zone for zone in allowed if zone in selected]
        # Full coverage is the default and needs no stored override.
        if tuple(picked) != tuple(allowed):
            out[region] = picked
    return out


def covered_zones_for(garment, region):
    """The zones of ``region`` this garment currently covers."""
    zones = zones_of(region)
    overrides = garment.get("covered_zones")
    if not isinstance(overrides, dict) or region not in overrides:
        return zones
    selected = set(overrides.get(region) or [])
    return tuple(zone for zone in zones if zone in selected)


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
                covered_zones = _clean_covered_zones(
                    item.get("covered_zones"))
                if covered_zones:
                    garment["covered_zones"] = covered_zones
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
            beneath_zones = _clean_beneath_zones(
                region, entry.get("beneath_zones"))
            if garments or beneath or beneath_zones:
                out[region] = {"garments": garments, "beneath": beneath}
                if beneath_zones:
                    out[region]["beneath_zones"] = beneath_zones
                # A FACT ABOUT THE REGION, not about the garment that left.
                # `beneath` surfaces only where something came off, and that
                # used to be read off a `removed` garment still sitting in the
                # region -- which is precisely the seat a removed garment no
                # longer keeps (`release_removed_garments`). The body records
                # that it was uncovered; the garment carries nothing.
                if entry.get("uncovered"):
                    out[region]["uncovered"] = True
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
    furthest, marks, descriptions, spans, displaced = {}, {}, {}, {}, {}
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
            # Displacement is a fact about the ONE garment, so every copy
            # must agree — a jacket pushed off the torso whose waist copy
            # still claimed full coverage would answer "is the waist covered"
            # two ways. Region-keyed union: any copy's override for a region
            # is the garment's override for it.
            overrides = garment.get("covered_zones")
            if isinstance(overrides, dict) and overrides:
                merged = displaced.setdefault(key, {})
                for changed_region, picked in overrides.items():
                    merged.setdefault(changed_region, picked)
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
            if displaced.get(key) and garment.get("state") != "removed":
                garment["covered_zones"] = dict(displaced[key])
    return regions


def concealing_garments(regions):
    """Per region, WHAT still covers it: {region: [garment name, ...]}.

    The attribution `covered_regions` computes and then throws away. Region
    visibility is a per-observer question ("which regions are concealed from
    this observer, and by what"), and the garment half of "by what" is decided
    here, in the pure coverage model, so the scene-side derivation never has to
    re-state the covering predicate -- two spellings of "does this garment
    cover" would drift exactly the way `wearing`/`state`/`regions` did.

    The predicate is `covered_regions`'s own: a removed garment no longer
    conceals, and a garment that only ATTACHES never did -- a hair clip is
    present without covering, which is the whole reason `attaches` exists. A
    spanning garment is named under every region it covers, because that is
    what covering several regions means. A qualifying garment with no name is
    still a covering ("?", matching `compact_line`), since losing the covered
    fact over a missing label would undress the region.
    """
    out = {}
    for region in REGIONS:
        names = []
        for garment in ((regions or {}).get(region) or {}).get("garments") or []:
            if garment.get("state") == "removed" or garment.get("attaches"):
                continue
            if not covered_zones_for(garment, region):
                continue
            name = " ".join(str(garment.get("name") or "").split()) or "?"
            if name not in names:
                names.append(name)
        if names:
            out[region] = names
    return out


def zone_concealing_garments(regions):
    """Per coverable zone, the garments whose surface still occupies it.

    Regions without a finer zone axis are intentionally absent.  Their
    existing all-or-nothing answer remains ``concealing_garments``.
    """
    out = {}
    for region, zones in REGION_ZONES.items():
        if region not in (regions or {}):
            continue
        by_zone = {zone: [] for zone in zones}
        for garment in ((regions.get(region) or {}).get("garments") or []):
            if garment.get("state") == "removed" or garment.get("attaches"):
                continue
            name = " ".join(str(garment.get("name") or "").split()) or "?"
            for zone in covered_zones_for(garment, region):
                if name not in by_zone[zone]:
                    by_zone[zone].append(name)
        out[region] = by_zone
    return out


def partially_exposed_regions(regions):
    """{region: [bare zones]} where other zones remain garment-covered."""
    out = {}
    for region, by_zone in zone_concealing_garments(regions).items():
        bare = [zone for zone in REGION_ZONES[region] if not by_zone[zone]]
        if bare and len(bare) < len(REGION_ZONES[region]):
            out[region] = bare
    return out


def apply_coverage_changes(regions, changes):
    """Apply structured partial-garment coverage to normalized regions.

    Shape: ``{garment_handle: {region: [zones still covered]}}``.  Handles
    resolve against the current wardrobe exactly like remove/conditions.  A
    malformed or ambiguous entry is ignored and reported; the caller can pass
    those messages to the Director without risking an information leak.
    """
    if not isinstance(changes, dict):
        return regions, []
    regions = normalize_regions({"regions": regions})
    worn = flat_wearing(regions)
    notes = []
    for handle, region_changes in changes.items():
        target = resolve_garment(handle, worn)
        if not target or not isinstance(region_changes, dict):
            notes.append(
                f"attire: ignored coverage for {handle!r}; it did not resolve "
                "uniquely against the worn garments.")
            continue
        valid = {}
        for region, raw_zones in region_changes.items():
            region = str(region or "").strip().casefold()
            if region not in REGIONS:
                # Not a region at all — measured live, a coverage entry
                # carrying `{"state": "loosened"}`: a rung move written into
                # the coverage channel. Say so; the ladder is not this field.
                notes.append(
                    f"attire: coverage for {handle!r} named {region!r}, "
                    "which is not a body region; the garment ladder moves "
                    "through remove/decisive acts, never through coverage.")
                continue
            allowed = zones_of(region)
            raw_zones = (raw_zones if isinstance(raw_zones, (list, tuple, set))
                         else [raw_zones])
            supplied = [str(zone or "").strip().casefold()
                        for zone in raw_zones if str(zone or "").strip()]
            selected = {zone for zone in supplied if zone in allowed}
            if supplied and not selected:
                # The invert guard (see _clean_covered_zones): an assertion
                # of coverage in a vocabulary we cannot read must not become
                # "covers nothing".
                notes.append(
                    f"attire: ignored coverage for {handle!r} at {region}; "
                    f"none of {supplied!r} is a known zone there. An empty "
                    "list is how a garment is displaced off a region.")
                continue
            picked = [zone for zone in allowed if zone in selected]
            valid[region] = picked
        if not valid:
            notes.append(
                f"attire: ignored coverage for {handle!r}; no known region "
                "zones were supplied.")
            continue
        found = False
        for region, entry in regions.items():
            for garment in entry.get("garments") or []:
                if garment.get("name", "").casefold() != target.casefold():
                    continue
                found = True
                overrides = dict(garment.get("covered_zones") or {})
                for changed_region, picked in valid.items():
                    allowed = zones_of(changed_region)
                    if tuple(picked) == tuple(allowed):
                        overrides.pop(changed_region, None)
                    else:
                        overrides[changed_region] = picked
                if overrides:
                    garment["covered_zones"] = overrides
                else:
                    garment.pop("covered_zones", None)
        if not found:
            notes.append(
                f"attire: ignored coverage for {handle!r}; the resolved "
                "garment had no region records.")
    return _sync_spanning_garments(regions), notes


def covered_regions(regions):
    """Which regions still have something on them."""
    # Anatomical order, not alphabetical: "torso, waist, groin, legs" is a
    # body, and "groin, legs, torso, waist" is a word list. (REGIONS order,
    # which concealing_garments already walks.)
    return list(concealing_garments(regions))


def exposed_regions(regions):
    """Which regions have nothing left covering them.

    A region with no garments at all counts as exposed -- bare hands are bare,
    not unmodelled. A region nobody ever mentioned is simply absent from
    `regions` and so appears in neither list.
    """
    cover = concealing_garments(regions)
    return [
        region for region in REGIONS
        if region in (regions or {}) and region not in cover
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

# Places a garment is pushed OFF while staying on the body. "Off her
# shoulders" is a displacement; "off her back" is a removal; and the
# distinction is exactly the word after "off". This closed list serves BOTH
# directions of the removal/displacement boundary: it keeps the gap-tolerant
# removal vocabulary below from firing on "the robe slips off one shoulder",
# and it keeps the steal guard (`removal_directed_at`) from reading a shove
# as the removal it is not.
_DISPLACEMENT_ANCHORS = (
    "shoulders", "shoulder", "hips", "hip", "waist", "knees", "knee",
    "thighs", "thigh", "ankles", "ankle", "arms", "arm", "forearms",
    "forearm", "wrists", "wrist", "elbows", "elbow", "face", "hair",
)

# The commonest English removal shape puts the GARMENT between the verb and
# "off" — "she pulls the tank top off" — and the fixed-phrase vocabulary
# above cannot see it. Measured live (chat 68 t8, design note 17): a beat
# whose diff said `remove: ["tank top"]` for an act the player asked to be
# one motion was clamped to `loosened` because decisive_intent returned
# False on exactly that sentence, and with the fiction already believing the
# top off, no later beat ever proposed the removal again. Up to four words
# of gap; "off" followed by a displacement anchor is a shove, not a removal,
# and does not qualify.
_DECISIVE_GAP_OFF = re.compile(
    r"\b(?:pulls?|pulled|pulling|yanks?|yanked|yanking|tugs?|tugged|tugging"
    r"|drags?|dragged|dragging|hauls?|hauled|hauling|takes?|took|taking"
    r"|slips?|slipped|slipping|lifts?|lifted|lifting|peels?|peeled|peeling"
    r"|tears?|tore|tearing|rips?|ripped|ripping|wrenche?s?|wrenched"
    r"|wrenching|shrugs?|shrugged|shrugging|works?|worked|working"
    r"|eases?|eased|easing|shakes?|shook|shaking|slides?|slid|sliding"
    r"|shimm(?:y|ies|ied|ying)|wriggles?|wriggled|wriggling"
    r"|kicks?|kicked|kicking)"
    r"\s+(?:[\w'’-]+\s+){0,4}?off\b"
    r"(?!\s+(?:(?:her|his|their|my|your|its|one|both|the)\s+)?(?:%s)\b)"
    % "|".join(_DISPLACEMENT_ANCHORS),
    re.IGNORECASE)

# The removal ladder's clamp, INVERTED (design note 17, second incident).
# Twice now a wrong ledger's root cause was the completion vocabulary missing
# one more way English says a garment came off — "pulls the tank top off",
# then "shrugs the jacket off", a live reroll clamped to `loosened` while the
# narration had the jacket on the floor. Enumerating completions is unwinnable.
# What IS a small, stable, closed set is the ways prose marks an act as STILL
# IN PROGRESS — inchoatives, conatives ("tugs AT", where tugging OFF is the
# completion), and explicit partiality — so the clamp now fires on process
# language and otherwise honours the Director's resolved removal. The failure
# direction flips to safe: an unrecognised process phrase merely lets a
# removal land that the stage owning objective causality asserted anyway,
# instead of silently forking the ledger from the fiction.
_PROCESS = re.compile(
    r"\b(?:begins?|beginning|began|starts?|starting|started"
    r"|sets? about|setting about|set about"
    r"|goes? to work on|went to work on|going to work on"
    r"|works? at|worked at|working at|fumbl\w+|struggl\w+|fiddl\w+"
    r"|picks? at|picked at|picking at|tugs? at|tugged at|tugging at"
    r"|pulls? at|pulled at|pulling at|plucks? at|plucking at"
    r"|tries to|trying to|tried to|attempts? to|attempting to"
    r"|halfway|half[- ]off|half out of|partway|part[- ]way"
    r"|inch by inch|one \w+ at a time|not (?:yet|quite) off)\b",
    re.IGNORECASE)


# What `_PROCESS` cannot say on its own (design note 17, THIRD incident).
# `_DECISIVE` is intrinsically about clothing -- "strips", "tears off" are
# not sentences about anything else -- so its attribution may fall back to
# "exactly one body is named here". `_PROCESS` is not: "begins", "starts",
# "works at", "tries to" are generic English about ANY ongoing act. It says
# something is in progress; it never says the something is an undressing.
#
# Measured live (chat 70 t9): the Director resolved `remove: ["fitted tank
# top"]` and narrated it thrown across the room, and the ledger held it at
# `loosened` because a LATER sentence about hands -- "both palms press flat
# against Hinami's bare skin ... and BEGIN to drag slowly downward" -- named
# no garment, fell to the one-body-named tier, and clamped her.
#
# So a process reading now requires the sentence to be about clothing at
# all. This list is enumerated where `_DECISIVE`'s completions deliberately
# are not, because its failure direction is the safe one the inversion was
# built for: a garment word missing here merely lets a removal land that the
# Director asserted anyway. Promiscuous general-English words are left OUT
# ("hook", as in fingers hooking under a hem; bare "tie"; "slip"; "shift"),
# since a false positive is what this fixes. "top" carries a lookahead
# because "the top of her thigh" is not a garment.
_CLOTHING_CONTEXT = re.compile(
    r"\b(?:clothes|clothing|garments?|outfits?|attire|dress(?:es)?|robes?"
    r"|gowns?|skirts?|trousers|pants|jeans|shorts|leggings|tights"
    r"|jackets?|coats?|cloaks?|capes?|corsets?|bodices?|blouses?|shirts?"
    r"|tunics?|vests?|waistcoats?|sweaters?|jumpers?|hoodies?|kimonos?"
    r"|saris?|togas?|aprons?|overalls|uniforms?|armou?r|breastplates?"
    r"|greaves|gauntlets?|bracers?|tops?(?!\s+of\b)"
    r"|underwear|undergarments?|panties|knickers|briefs|boxers|bras?"
    r"|brassieres?|chemises?|camisoles?|negligees?|lingerie|stockings"
    r"|socks|garters?|sashes?|sash|belts?|girdles?|scar(?:f|ves)|shawls?"
    r"|veils?|hoods?|gloves?|boots?|shoes?|sandals?|slippers?"
    r"|hems?|sleeves?|collars?|cuffs?|lapels?|waistbands?|necklines?"
    r"|straps?|laces?|buttons?|buckles?|zips?|zippers?|clasps?|knots?"
    r"|fastenings?|drawstrings?|ribbons?|seams?|plackets?"
    r"|undress\w*|disrob\w*|unbutton\w*|unlac\w*|unzip\w*|unhook\w*"
    r"|unfasten\w*|unbuckl\w*|unti\w*|unclasp\w*)\b",
    re.IGNORECASE)


def _process_sentence(sentence, garment_phrases=()):
    """Does this sentence mark an UNDRESSING as still in progress?

    Three conditions, and the third is the one this used to be missing:

    1. process language is present;
    2. no completion shape shares the sentence -- "she stops fumbling and
       just rips it off" ends the process it names, so the decisive reading
       wins inside one sentence;
    3. the sentence is about clothing at all -- a garment this body is
       actually wearing, or a generic clothing word. Without this, every
       "begins to", "starts to" and "tries to" in a beat was evidence about
       somebody's clothes.

    `garment_phrases` is the wardrobe's own spellings, matched whole exactly
    as the attribution ladder's first tier matches them. Head nouns are NOT
    used here: `_garment_keys` reads the last word, and the live wardrobe
    holds "sheer obsidian silk robe that parts with every movement", whose
    head noun is "movement".
    """
    if not _PROCESS.search(sentence) or _decisive_sentence(sentence):
        return False
    if _CLOTHING_CONTEXT.search(sentence):
        return True
    folded = sentence.casefold()
    return any(phrase and phrase in folded for phrase in garment_phrases)


def _decisive_sentence(sentence):
    """One sentence's answer to "was this asked for all at once?"."""
    return bool(_DECISIVE.search(sentence)
                or _DECISIVE_GAP_OFF.search(sentence))


def decisive_intent(text):
    """Did somebody ask for the whole thing at once?"""
    return any(_decisive_sentence(sentence)
               for sentence in _SENTENCE.findall(str(text or "")))


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


def recover_shed_entity_changes(scene, diff):
    """Promote an explicitly shed clothing entity back into the attire diff.

    A model can encode one physical fact in two adjacent fields: create an
    object whose state says ``{clothing:true, shed:true, worn_by:<body>}``, yet
    omit the matching attire removal and the object's floor position.  Keeping
    the object while leaving the same garment on the body is not leniency; it
    is two contradictory outcomes for one act.

    The entity already supplies every fact needed to recover conservatively:
    this is clothing, it has been shed, it names its former wearer, and its
    name must resolve uniquely against that body's live wardrobe.  No prose is
    parsed and no new garment is invented.  The supplied ``diff`` is mutated
    so resolve reconciliation, perception preview, and commit can all consume
    the same recovered encoding.  Returns short records describing what was
    recovered, for engine notes/tests.
    """
    if not isinstance(scene, dict) or not isinstance(diff, dict):
        return []
    incoming_entities = diff.get("entities")
    if not isinstance(incoming_entities, dict):
        return []

    ledger = scene.get("attire") or {}
    if not isinstance(ledger, dict):
        return []
    owner_keys = {
        str(key).strip().casefold(): key
        for key, value in ledger.items() if isinstance(value, dict)
    }
    attire_diff = diff.setdefault("attire", {})
    if not isinstance(attire_diff, dict):
        attire_diff = diff["attire"] = {}
    positions_diff = diff.setdefault("positions", {})
    if not isinstance(positions_diff, dict):
        positions_diff = diff["positions"] = {}

    recovered = []
    scene_entities = scene.get("entities") or {}
    scene_positions = scene.get("positions") or {}
    for entity_id, incoming in incoming_entities.items():
        if not isinstance(incoming, dict):
            continue
        existing = (scene_entities.get(entity_id)
                    if isinstance(scene_entities, dict) else None) or {}
        old_state = existing.get("state") if isinstance(existing, dict) else {}
        new_state = incoming.get("state")
        state = dict(old_state) if isinstance(old_state, dict) else {}
        if isinstance(new_state, dict):
            state.update(new_state)
        if not state.get("clothing") or not state.get("shed"):
            continue
        owner_raw = str(state.get("worn_by") or "").strip()
        owner = owner_keys.get(owner_raw.casefold())
        if not owner:
            continue

        entry = ledger.get(owner) or {}
        worn = flat_wearing(normalize_regions(entry))
        names = [incoming.get("name"), existing.get("name")]
        names.extend(incoming.get("aliases") or [])
        names.extend(existing.get("aliases") or [])
        target = next(
            (resolved for candidate in names
             if candidate
             for resolved in [resolve_garment(candidate, worn)]
             if resolved),
            None,
        )
        if target:
            change = coerce_diff_shape(attire_diff.get(owner) or {})
            removals = change.setdefault("remove", [])
            if target not in removals:
                removals.append(target)
            attire_diff[owner] = change

        placed = entity_id in positions_diff or entity_id in scene_positions
        where = scene_positions.get(owner)
        if not placed and where:
            positions_diff[entity_id] = where

        if target or (not placed and where):
            recovered.append({
                "entity_id": str(entity_id), "owner": str(owner),
                "garment": target, "position": positions_diff.get(entity_id),
            })
    return recovered


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
        out[region] = {"garments": garments,
                       "beneath": entry.get("beneath") or ""}
        beneath_zones = _clean_beneath_zones(
            region, entry.get("beneath_zones"))
        if beneath_zones:
            out[region]["beneath_zones"] = beneath_zones
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

#: Every attire-diff key `coerce_diff_shape` HANDLES, as opposed to files as
#: a garment note. A hand-maintained mirror of that function's dispatch chain
#: with nothing to keep the two in step -- and the drift is silent in the
#: worst direction: a key the chain learns to handle but this list forgets
#: reads as unknown to any caller consulting the list, while a key this list
#: claims and the chain drops becomes a note about a garment named
#: "coverage". Bound by
#: `test_every_known_diff_key_is_handled_rather_than_filed_as_a_note`.
_DIFF_KNOWN_KEYS = ("wearing", "add", "remove", "replace", "state",
                    "conditions", "coverage", "regions", "notes", "placement")


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
        if name == "coverage":
            # {garment handle: {region: [zones still covered]}}. Keep the
            # structure intact; apply_coverage_changes validates zones and
            # resolves the handle against the live wardrobe.
            if isinstance(value, dict):
                out["coverage"] = value
            continue
        if name in ("wearing", "add", "remove", "replace"):
            if value is None:
                continue
            # WHERE A GARMENT IS WORN IS A FACT ABOUT THE WEARING, NOT ABOUT
            # THE NAME. The region tables answer the ordinary case and cannot
            # answer any other: underwear on the head, a belt across the
            # chest, a flowerpot as a hat, a shirt worn as trousers, trousers
            # pulled onto the arms. The variation is unbounded and no word
            # list reaches the end of it, so the DECLARATION gets to say.
            #
            # Either spelling is accepted -- a bare name for the ordinary
            # case, or {name, covers:[regions]} when the wearing is not what
            # the name implies. The list itself stays strings, because every
            # consumer downstream reads names; the placement rides beside it
            # in `placement` and is applied where the tables would otherwise
            # have guessed.
            items, placed = [], {}
            for entry in _as_list(value):
                if isinstance(entry, dict):
                    text = str(entry.get("name") or entry.get("garment")
                               or "").strip()
                    covers = [str(r or "").strip().casefold()
                              for r in _as_list(entry.get("covers"))
                              if str(r or "").strip().casefold() in REGIONS]
                    if text and covers:
                        placed[text] = covers
                else:
                    text = str(entry).strip()
                if text:
                    items.append(text)
            out[name] = items
            if placed:
                out.setdefault("placement", {}).update(placed)
            continue
        if name == "placement":
            # Declared directly, for a beat that moves a garment somewhere
            # unusual without re-adding it.
            if isinstance(value, dict):
                for garment, covers in value.items():
                    covers = [str(r or "").strip().casefold()
                              for r in _as_list(covers)
                              if str(r or "").strip().casefold() in REGIONS]
                    if str(garment or "").strip() and covers:
                        out.setdefault("placement", {})[
                            str(garment).strip()] = covers
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
    Attribution runs the ladder in `_attributed_targets`, which both readings
    of a beat share, because the ACTOR is not the target -- "Corin tears the
    sash from her waist" is Mira being undressed. In its real order, which
    this docstring used to give as three tiers in a different arrangement:

      1. the garment, by FULL PHRASE. Whoever is wearing what the sentence
         names outright.
      2. the genitive owner -- "<Name>'s tank top" -- which says whose even
         where the phrase is abbreviated past recognition and a second cast
         name shares the sentence.
      3. the garment by HEAD NOUN, when exactly one body is wearing one.
      4. first person, but only in the player's own input, where "I" is a
         subject the sentence never spells out.
      5. a name, when the sentence names exactly one body. A non-reflexive
         third-person possessive re-attributes away from that body -- it acts
         on somebody ELSE -- to the only other dressed body, or to nobody.
      6. the player, for their own ambiguous prose and no one else's.

    Sentence matching is a heuristic, deliberately. It decides how FAST an
    undressing the fiction already asked for happens, never who may know what,
    so it is not load-bearing for the information firewall -- see
    docs/UNBUILT.md §3.1 on why prose matching is not allowed to be a boundary.
    """
    return _attributed_targets(player_text, other_texts, wardrobe,
                               player_name, _decisive_sentence)


def process_targets(player_text, other_texts, wardrobe, player_name=None):
    """WHOSE undressing this beat's words leave still in progress.

    The clamp's trigger, inverted (see `_PROCESS`): same per-body
    attribution as `decisive_targets`, because "Corin fumbles with the knots
    of her sash" is Mira's sash staying on, not Corin's. A body named here
    has its removal proposals held one rung; everyone else's resolved
    removals land as resolved.

    Unlike the decisive reading, a sentence must first BE about clothing to
    count at all (see `_process_sentence`) -- process language is generic
    English, and reading it as evidence about somebody's clothes is how a
    resolved removal got clamped by a sentence about hands.
    """
    phrases = {phrase
               for garments in (wardrobe if isinstance(wardrobe, dict)
                                else {}).values()
               for phrase, _noun in (_garment_keys(g) for g in garments or [])
               if phrase}
    return _attributed_targets(
        player_text, other_texts, wardrobe, player_name,
        lambda sentence: _process_sentence(sentence, phrases))


def _attributed_targets(player_text, other_texts, wardrobe, player_name,
                        sentence_hit):
    """The shared attribution ladder behind decisive_targets and
    process_targets — one implementation of "whose clothes is this sentence
    about", so the two readings of a beat cannot drift."""
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
            if not sentence_hit(sentence):
                continue
            folded = sentence.casefold()
            words = set(re.findall(r"[a-z0-9\-\u2019\']+", folded))

            by_phrase = {name for name, entries in keys.items()
                         if any(phrase and phrase in folded
                                for phrase, _noun in entries)}
            if by_phrase:
                hits |= by_phrase
                continue
            # "<Name>'s tank top" is explicit attribution even when the
            # garment phrase is abbreviated past recognition and a second
            # cast name shares the sentence — the genitive says whose.
            by_owner = set()
            for owner, entries in keys.items():
                if not str(owner or "").strip():
                    continue
                if not re.search(r"\b%s[’']s\b"
                                 % re.escape(str(owner).casefold()), folded):
                    continue
                for phrase, noun in entries:
                    tokens = [t for t in re.findall(r"[a-z0-9\-’\']+",
                                                    phrase or "") if t]
                    if (noun and noun in words) or any(
                            t in words for t in tokens):
                        by_owner.add(owner)
                        break
            if by_owner:
                hits |= by_owner
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


# Displacement said as prose. Mined from the stored corpus (design note 17):
# of 38 stored condition notes, 14 carried language like these — "pushed back
# off shoulders", "hem dragged to midriff", "parted fully open, no longer
# covering torso, waist, groin or legs" — while the structured coverage field
# went unwritten. This regex DETECTS; it never executes: a condition string
# is not state (the module's standing rule), so a hit produces a warning and
# a tell_director line naming the real channel, not a derived coverage
# change.
_DISPLACEMENT_LANGUAGE = re.compile(
    r"\b(?:pushed (?:back |down |up )?(?:off|from)|hiked|hitched|rucked"
    r"|bunched|shoved (?:up|down|aside)|slipped (?:off|down|from)"
    r"|slid (?:off|down)|off (?:her |his |their |one |both )?shoulders?"
    r"|around (?:her |his |their )?(?:ankles|knees|thighs)"
    r"|pulled (?:up|down|aside|open)|tugged (?:up|down|aside)|dragged"
    r"|hauled (?:up|upward|down)|fall(?:s|en)? open|hanging open|gapes?"
    r"|parts? at|parted|untucked|drawn aside|swept aside|pushed to one side"
    r"|hem (?:up|raised|lifted)|gathered (?:up|at)"
    r"|no longer cover(?:s|ing))\b", re.IGNORECASE)

# Ladder words inside condition prose. Chat 68 t7 wrote "…bunched under
# arms — loosened, still worn" INTO the condition field: a rung move, a
# displacement and a wornness assertion through the one field that accepts a
# sentence. A rung word in prose moves nothing, and saying so is the floor.
_RUNG_LANGUAGE = re.compile(
    r"\b(loosened|removed|taken off|comes? off|came off)\b", re.IGNORECASE)


def displacement_language(text):
    """Does this condition prose describe a coverage change?"""
    return bool(_DISPLACEMENT_LANGUAGE.search(str(text or "")))


def rung_language(text):
    """The first garment-ladder word this condition prose tries to move."""
    match = _RUNG_LANGUAGE.search(str(text or ""))
    return match.group(1).casefold() if match else ""


# The fixed phrases whose direction is unambiguously OFF THE BODY. A strict
# subset of `_DECISIVE` on purpose: bare "yanks"/"rips"/"in one motion" are
# decisive about SPEED while saying nothing about direction — "yanks her
# skirt up in one motion" is a shove, and reading it as a removal is the
# steal this guard exists to prevent, pointed the other way.
_REMOVAL_PHRASE = re.compile(
    r"\b(?:strips?|stripped|stripping|throws? off|threw off|throwing off"
    r"|shrugs? out of|shrugged out of|shrugging out of"
    r"|steps? out of|stepped out of|stepping out of"
    r"|kicks? off|kicked off|kicking off"
    r"|casts? (?:it |them )?aside|flings? (?:it |them )?(?:aside|away|off)"
    r"|flung (?:it |them )?(?:aside|away|off)"
    r"|cuts? (?:it |them )?(?:off|away)|slices? (?:it |them )?(?:off|away)"
    r"|fully undress\w*|completely undress\w*|naked|nude"
    r"|bare(?:s|d)? (?:her|him|them)self)\b",
    re.IGNORECASE)


def _removal_directed(sentence):
    """A decisive phrase whose direction is OFF THE BODY, not off a place on
    it — the gap-tolerant verb…off shape (displacement anchors excluded) or
    a fixed phrase that can only mean removal."""
    return bool(_DECISIVE_GAP_OFF.search(sentence)
                or _REMOVAL_PHRASE.search(sentence))


def removal_directed_at(texts, garment_names, worn_names=()):
    """Do this beat's words decisively take THIS garment off the body?

    The steal guard's question (design note 17 §3): a `coverage` entry that
    empties every region a garment covers is either a shove (trousers to the
    ankles — honour it) or a removal the model filed on the wrong axis ("she
    yanks her shirt off" recorded as displacement — escalate it). Only a
    sentence that names the garment AND carries a removal-directed decisive
    phrase distinguishes them, and the default on silence is the shove:
    wrongly keeping a garment on the body is recoverable next beat, wrongly
    removing it destroys ledger state and mints a floor object.

    `garment_names` carries every spelling in play — the ledger's canonical
    name AND the diff's own handle — because the sentence usually uses the
    handle's shorter phrase ("tank top" for "fitted tank top"), and the
    head-noun tier alone cannot see it ("top" is under the four-character
    floor the noun rule keeps).
    """
    names = (garment_names if isinstance(garment_names, (list, tuple, set))
             else [garment_names])
    keys = [_garment_keys(str(n or "")) for n in names if str(n or "").strip()]
    primary = str(next(iter(names), "") or "")
    for text in (texts if isinstance(texts, (list, tuple)) else [texts]):
        for sentence in _SENTENCE.findall(str(text or "")):
            if not _removal_directed(sentence):
                continue
            folded = sentence.casefold()
            words = set(re.findall(r"[a-z0-9\-’\']+", folded))
            for phrase, noun in keys:
                if phrase and phrase in folded:
                    return True
                if noun and len(noun) > 3 and noun in words:
                    # The head noun alone only counts when it is unambiguous
                    # among the worn garments, exactly as resolve_garment
                    # scopes it.
                    others = [w for w in (worn_names or [])
                              if w and w.casefold() != primary.casefold()
                              and _garment_keys(w)[1] == noun]
                    if not others:
                        return True
    return False


def coverage_removal_escalations(texts, coverage, regions):
    """Coverage claims that are removals filed on the wrong axis.

    Returns the coverage HANDLES to escalate: entries that (a) resolve to a
    worn garment, (b) would leave it covering nothing anywhere it covers,
    and (c) are named by a removal-directed decisive phrase in this beat's
    words. Anything less specific keeps its displacement reading.
    """
    if not isinstance(coverage, dict):
        return []
    worn = flat_wearing(regions)
    out = []
    for handle, region_changes in coverage.items():
        if not isinstance(region_changes, dict):
            continue
        target = resolve_garment(handle, worn)
        if not target:
            continue
        covers = set()
        for region, entry in (regions or {}).items():
            for garment in entry.get("garments") or []:
                if (garment.get("name", "").casefold() == target.casefold()
                        and garment.get("state") != "removed"
                        and not garment.get("attaches")):
                    covers.add(region)
        if not covers:
            continue
        emptied = set()
        for region, raw_zones in region_changes.items():
            region = str(region or "").strip().casefold()
            if region not in REGIONS:
                continue
            raw = (raw_zones if isinstance(raw_zones, (list, tuple, set))
                   else [raw_zones])
            supplied = [str(z or "").strip().casefold()
                        for z in raw if str(z or "").strip()]
            if not supplied:
                emptied.add(region)
        if not covers <= emptied:
            continue
        if removal_directed_at(texts, [target, handle], worn):
            out.append(handle)
    return out


def worn_conditions_dropped(previous, reconciled):
    """Conditions dropped because the garment stopped being on a body.

    Same lesson as `removals_held`, pointed the other way: the drop is right
    and the SILENCE would be the defect. A Director that wrote "hanging loose
    from the other shoulder" and finds it gone next beat should be told the
    garment left the body, so it can restate any lasting damage on the object
    rather than assume the note was ignored.

    Returns [(garment name, the condition that was dropped)].
    """
    was = {}
    for entry in (previous or {}).values():
        for garment in entry.get("garments") or []:
            name = garment.get("name") or ""
            if name and garment.get("condition"):
                was.setdefault(name.casefold(),
                               (name, garment["condition"]))
    dropped, seen = [], set()
    for entry in (reconciled or {}).values():
        for garment in entry.get("garments") or []:
            key = (garment.get("name") or "").casefold()
            if (garment.get("state") != "removed" or key in seen
                    or key not in was or garment.get("condition")):
                continue
            name, condition = was[key]
            if displacement_language(condition):
                seen.add(key)
                dropped.append((name, condition))
    return dropped


def removals_held(previous, reconciled, wanted):
    """Removal proposals the ladder held short of `removed` this beat.

    The chat-68 failure mode (design note 17): a removal clamped to
    `loosened` while the fiction moved on believing the garment off — and
    nothing said so, so no later beat ever proposed it again and the ledger
    diverged from the story for good. The clamp is right; the silence was
    the defect. Returns [(garment name, state it was held at)], for the
    commit seam to feed back through tell_director.
    """
    worn_names = [g.get("name", "")
                  for entry in (previous or {}).values()
                  for g in (entry.get("garments") or [])
                  if g.get("name")]
    wanted_keys = set()
    for name in (wanted or []):
        resolved = resolve_garment(name, worn_names,
                                   allow_head_noun=False) or str(name)
        wanted_keys.add(resolved.casefold())
    held, seen = [], set()
    for entry in (previous or {}).values():
        for garment in entry.get("garments") or []:
            key = garment.get("name", "").casefold()
            if (not key or key in seen or key in wanted_keys
                    or garment.get("state") == "removed"):
                continue
            seen.add(key)
            after = None
            for r_entry in (reconciled or {}).values():
                for g in r_entry.get("garments") or []:
                    if g.get("name", "").casefold() == key:
                        after = g.get("state")
                        break
                if after:
                    break
            if after and after != "removed":
                held.append((garment.get("name", ""), after))
    return held


def advance(previous, proposed, decisive=False, process=False):
    """Reconcile a proposed set of regions against what was true before.

    THE CLAMP IS INVERTED (design note 17, second incident). It used to hold
    every non-decisive removal to one rung, with "decisive" decided by a
    completion vocabulary — and twice a wrong ledger's root cause was that
    vocabulary missing one more way English says a garment came off ("pulls
    the tank top off", then "shrugs the jacket off" on a live reroll). The
    Director owns objective causality: a resolved removal IS the resolution,
    and an engine that re-decides it silently forks the ledger from the
    fiction with no recovery. So a proposed `removed` now LANDS unless
    `process` says this beat's own prose shows the act still in progress
    ("begins to untie", "works at the knots") — a smaller, closed set that
    fails in the safe direction: an unrecognised phrasing lets a removal
    land that the Director asserted anyway.

    What survives of the old rule, deliberately:
    - intermediate jumps still clamp (a `worn -> open` proposal reaches
      `loosened` first) — the dramatic middle is still the contract, stated
      in the prompt and held here for staged states;
    - `process` holds a removal one rung, so "begins on the sash" cannot
      reach bare in the same paragraph — the exact defect the clamp was
      built against, now detected from the prose that defines it;
    - `decisive` lifts everything, including a process reading in the same
      beat ("stops fumbling and tears it off").

    Putting something back on, or getting further dressed, is unrestricted --
    the asymmetry is deliberate, because it is undressing that has a
    dramatic middle worth staying in.

    Returns the reconciled regions. Anything the proposal invented (a new
    garment, a new region) is kept; this reconciles transitions, it does not
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
                # A garment already displaced off EVERYTHING it covers has
                # played its middle out on the coverage axis: trousers at the
                # ankles do not owe the ladder two more beats to leave the
                # body. Counted as `open` for the clamp distance only —
                # partial displacement earns no discount, and the state
                # itself is untouched.
                before_rung = _rung(before.get("state", "worn"))
                covers = before.get("covers") or [region]
                if all(not covered_zones_for(before, r) for r in covers):
                    before_rung = max(before_rung, _rung("open"))
                gap = _rung(state) - before_rung
                if gap > 1 and (state != "removed" or process):
                    # Hold it at the next rung: an intermediate jump always
                    # (staged states are the contract), a removal only when
                    # this beat's own prose shows the act still in progress.
                    # A resolved removal with no process reading LANDS -- see
                    # the docstring.
                    state = GARMENT_STATES[before_rung + 1]
            # Condition survives a rung change on its own terms: a proposal
            # that says nothing about it must not launder the garment, and a
            # proposal that DOES say something is this beat's news.
            condition = _clean(garment.get("condition"), CONDITION_LIMIT)
            if not condition and before:
                condition = before.get("condition") or ""
            # ...but a condition describing the garment's relationship to a
            # BODY cannot outlive its leaving one. The structured twin of this
            # is already cleared below, for the reason stated there; the prose
            # saying the same thing was not, so the same fact was half tidied
            # and half left behind.
            #
            # Measured live (chat 70, design note 17 §6): the jacket reached
            # `removed`, was minted as a floor object -- and kept
            # "peeled off one shoulder, one arm freed from sleeve, hanging
            # loose from the other shoulder" from four beats earlier. Every
            # reader of the ledger was then told a garment on the floor was
            # hanging off her shoulder, so the Director removed it AGAIN a
            # beat later and the narrator re-narrated the removal a beat after
            # that. Three removals of one jacket, each correct given what it
            # was shown.
            #
            # Only displacement prose is dropped, and only on `removed`:
            # "wine-stained down the front" is a fact about the garment and
            # survives anything, while "hanging open" is a fact about a body
            # it is no longer on.
            if state == "removed" and condition and displacement_language(
                    condition):
                condition = ""
            description = _clean(garment.get("description"), DESCRIPTION_LIMIT)
            if not description and before:
                description = before.get("description") or ""
            covered_zones = _clean_covered_zones(
                garment.get("covered_zones")
                if garment.get("covered_zones") is not None
                else (before or {}).get("covered_zones"))
            record = {"name": name, "description": description,
                      "attaches": bool(garment.get("attaches")
                                       if garment.get("attaches") is not None
                                       else (before or {}).get("attaches")),
                      "state": state, "condition": condition}
            # SOMEBODY SAID WHERE THIS GOES. Not `covers` -- that is DERIVED
            # by `_sync_spanning_garments` from the regions a garment occupies
            # and blanked for single-region ones, so it cannot carry intent.
            # This is the intent: the placement was declared rather than
            # guessed from the name, and it survives every rebuild so the name
            # table never gets to re-answer a question it was overruled on. A
            # shirt worn as trousers does not drift back to the torso next
            # beat because its name still says shirt.
            if garment.get("placed") or (before or {}).get("placed"):
                record["placed"] = True
            # `removed` clears the displacement record: a garment off the
            # body covers nothing anywhere, and a stale override must not
            # resurface half-displaced if the garment is ever re-worn.
            if covered_zones and state != "removed":
                record["covered_zones"] = covered_zones
            garments.append(record)
        out[region] = {"garments": garments,
                       "beneath": entry.get("beneath")
                       or (previous.get(region) or {}).get("beneath") or ""}
        beneath_zones = _clean_beneath_zones(
            region, entry.get("beneath_zones")
            or (previous.get(region) or {}).get("beneath_zones"))
        if beneath_zones:
            out[region]["beneath_zones"] = beneath_zones
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
                zones = REGION_ZONES.get(region)
                if (zones and isinstance(garment.get("covered_zones"), dict)
                        and region in garment["covered_zones"]):
                    covered = covered_zones_for(garment, region)
                    exposed = [zone for zone in zones if zone not in covered]
                    text += " [covers %s; exposes %s]" % (
                        ", ".join(covered) or "none",
                        ", ".join(exposed) or "none")
                elif (not zones and not garment.get("attaches")
                        and not covered_zones_for(garment, region)):
                    # Displacement at region grain: still worn, pushed off
                    # this place — a jacket off the shoulders, trousers at
                    # the ankles. The garment stays on the line because it is
                    # still ON the body; the marker is what stops the
                    # Director reading its presence as coverage.
                    text += " [displaced; not covering this region]"
                if anchored and garment.get("description"):
                    text += " — %s" % garment["description"]
                pieces.append(text)
            zones = REGION_ZONES.get(region)
            if zones:
                by_zone = zone_concealing_garments(regions).get(region) or {}
                bare_zones = [zone for zone in zones if not by_zone.get(zone)]
                beneath_zones = _clean_beneath_zones(
                    region, entry.get("beneath_zones"))
                for zone in bare_zones:
                    detail = (beneath_zones.get(zone, "")
                              if beneath_visible else "")
                    pieces.append("%s bare%s" % (
                        zone, " — %s" % detail if detail else ""))
            else:
                coverers = [g for g in worn if not g.get("attaches")]
                if coverers and not any(
                        covered_zones_for(g, region) for g in coverers):
                    # Every covering garment here is displaced off the
                    # region: the skin is bare even though the clothing is
                    # on the body. (A region holding only ornaments already
                    # reads "[worn at, covers nothing]" and needs no echo.)
                    pieces.append("bare here")
            lines.append("%s: %s" % (region, ", ".join(pieces)))
            continue
        if beneath_visible:
            beneath = entry.get("beneath") or _clean(body)
            lines.append("%s: bare%s" % (region, " — %s" % beneath if beneath else ""))
        else:
            lines.append("%s: bare" % region)
    return lines


def perceptible_region_surfaces(regions, beneath_visible=False):
    """The visible surface of each authored region, without hidden layers.

    ``describe`` is an objective/Director view: it may name under-layers while
    marking them as such.  Perception needs a stricter projection.  An outside
    observer sees the first covering garment and ornaments worn at the region,
    or the exposed body description after a garment has actually come off.
    It never receives a garment beneath another garment, nor ``beneath`` text
    for a region that has not been uncovered in play.

    Spatial and observer-specific concealment is deliberately not decided
    here; ``agents.common.observer_body_regions`` applies ``region_visibility``
    to these pure attire surfaces.
    """
    out = {}
    for region in REGIONS:
        entry = (regions or {}).get(region)
        if not isinstance(entry, dict):
            continue
        present = [
            g for g in (entry.get("garments") or [])
            if isinstance(g, dict) and g.get("state") != "removed"
        ]
        worn = [g for g in present if not g.get("attaches")]
        ornaments = [g for g in present if g.get("attaches")]
        parts = []
        zones = REGION_ZONES.get(region)
        partial = bool(zones and any(
            isinstance(g.get("covered_zones"), dict)
            and region in g["covered_zones"] for g in worn))
        if partial:
            beneath_zones = _clean_beneath_zones(
                region, entry.get("beneath_zones"))
            zone_parts = []
            described = set()
            for zone in zones:
                covering = next(
                    (g for g in worn if zone in covered_zones_for(g, region)),
                    None)
                if covering:
                    surface = _garment_text(covering)
                    key = covering.get("name", "").casefold()
                    if covering.get("description") and key not in described:
                        surface += " — %s" % covering["description"]
                        described.add(key)
                else:
                    surface = "bare"
                    beneath = (beneath_zones.get(zone, "")
                               if beneath_visible else "")
                    if beneath:
                        surface += " — %s" % beneath
                zone_parts.append("%s: %s" % (zone, surface))
            parts.append("; ".join(zone_parts))
            for shoved in worn:
                if not covered_zones_for(shoved, region):
                    # Covering no zone here at all: visible as a hanging
                    # garment, not as a surface.
                    parts.append(
                        "%s [displaced; not covering this region]"
                        % _garment_text(shoved))
        else:
            # The visible surface is the first garment STILL COVERING the
            # region — a displaced one (jacket off the shoulders, trousers at
            # the ankles) is not a covering, but it is not invisible either:
            # an observer sees the skin AND the garment hanging where it now
            # hangs, so it rides alongside like an ornament does.
            covering = next(
                (g for g in worn if covered_zones_for(g, region)), None)
            if covering:
                surface = _garment_text(covering)
                if covering.get("description"):
                    surface += " — %s" % covering["description"]
                parts.append(surface)
            else:
                surface = "bare"
                # The region's own record that it was uncovered, or -- for the
                # editor, a restored archive, and every chat written before
                # `release_removed_garments` existed -- a removed garment
                # still sitting in it. See `describe` for the full note.
                shed = bool(entry.get("uncovered")) or any(
                    isinstance(g, dict) and g.get("state") == "removed"
                    for g in (entry.get("garments") or [])
                )
                beneath = (_clean(entry.get("beneath"), BENEATH_LIMIT)
                           if shed and beneath_visible else "")
                if beneath:
                    surface += " — %s" % beneath
                parts.append(surface)
            for shoved in worn:
                if shoved is covering or covered_zones_for(shoved, region):
                    continue
                parts.append("%s [displaced; not covering this region]"
                             % _garment_text(shoved))
        for ornament in ornaments:
            text = "%s [worn at, covers nothing]" % _garment_text(ornament)
            if ornament.get("description"):
                text += " — %s" % ornament["description"]
            parts.append(text)
        out[region] = "; ".join(parts)
    return out


def apply_flat_change(previous, wanted, decisive=False, conditions=None,
                      process=False, placement=None):
    """Reconcile a flat "what they are wearing now" list against the regions.

    The Director speaks in whole garments -- add these, remove those -- because
    that is the shape a model reliably produces. A removal is a resolved
    fact and lands, unless `process` says this beat's prose still has the
    act in progress -- see `advance` for the inverted clamp and its history.

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
        beneath_zones = _clean_beneath_zones(
            region, entry.get("beneath_zones"))
        if beneath_zones:
            proposed[region]["beneath_zones"] = beneath_zones
    for key, name in wanted_keys.items():
        if key in seen:
            continue
        # DECLARED PLACEMENT BEATS THE NAME TABLE. `regions_covered` answers
        # the ordinary case from a word list, and the unusual case has no
        # bottom -- a shirt worn as trousers, trousers on the arms, a
        # flowerpot as a hat. Whoever put it on says where; the table is only
        # the default for when nobody bothered.
        where = (placement or {}).get(name) or (placement or {}).get(key)
        for region in (where or regions_covered(name)):
            entry = proposed.setdefault(region, {"garments": [], "beneath": ""})
            garment = {"name": name, "state": "worn",
                       "condition": marks.get(key, "")}
            if where:
                # Marked so nothing downstream re-guesses it, and so
                # `guessed_spans` knows this placement was chosen rather than
                # fallen into.
                garment["placed"] = True
            entry["garments"].append(garment)
    return advance(previous, proposed, decisive, process=process)


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
    # The displacement axis, said once per garment: worn, but pushed off
    # these regions. Distinct from the exposure notes below — those say what
    # the BODY shows, this says where the GARMENT has gone while staying on.
    displaced_reported = set()
    for region in REGIONS:
        for garment in ((regions or {}).get(region) or {}).get("garments") or []:
            key = garment.get("name", "").casefold()
            if (garment.get("state") == "removed" or garment.get("attaches")
                    or key in displaced_reported):
                continue
            overrides = garment.get("covered_zones")
            if not isinstance(overrides, dict) or not overrides:
                continue
            off = [r for r in REGIONS
                   if r in overrides and not covered_zones_for(garment, r)]
            if off:
                displaced_reported.add(key)
                notes.append("%s displaced off the %s" % (
                    garment["name"], ", ".join(off)))
    bare = exposed_regions(regions)
    if bare:
        notes.append("bare at the %s" % ", ".join(bare))
    for region, zones in partially_exposed_regions(regions).items():
        notes.append("partly bare at the %s: %s" % (
            region, ", ".join(zones)))
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
    if text.startswith("partly bare at the "):
        return True
    if " displaced off the " in text:
        return True
    return any(text.endswith(" " + state) for state in ("loosened", "open"))


def release_removed_garments(entry):
    """Drop garments that have left the body out of a wearer's ledger.

    REMOVED MEANS GENUINELY NOT PART OF THE CARD ANY MORE. A garment that
    came off kept its seat in the wearer's regions under `state: "removed"`,
    and every relation that seat carried -- the region it hung on, the
    condition describing how it hung there -- was a relation to a body it had
    left. It is an object in the world now; the region it vacated is simply
    uncovered, free to be filled by any attire, makeshift or otherwise.

    Measured live (chat 70, design note 17 §6): the jacket sat `removed`
    across three of Hinami's regions, carrying "hanging loose from the other
    shoulder" from four beats earlier, while the object itself lay on the
    stone in a different room. Two records of one garment, disagreeing. The
    Director removed it a second time; the narrator narrated it a third.

    Called by the commit seam AFTER `_mint_shed_garments`, never before:
    `newly_removed` reads the transition out of these very entries, so an
    earlier prune would mean nothing ever reached the floor.

    Putting it back on is an ordinary `add` -- a separate act, with its own
    beats for returning to the room and picking it up -- and `add` accepts
    any name, so the garment re-enters as `worn` like anything else would.
    """
    entry = entry if isinstance(entry, dict) else {}
    regions = entry.get("regions")
    if isinstance(regions, dict):
        for region_entry in regions.values():
            if not isinstance(region_entry, dict):
                continue
            garments = region_entry.get("garments")
            if not isinstance(garments, list):
                continue
            kept = [g for g in garments
                    if not (isinstance(g, dict)
                            and g.get("state") == "removed")]
            if len(kept) != len(garments):
                # The region remembers being uncovered even though the garment
                # that uncovered it is gone -- that is what lets `beneath`
                # surface where something came off and stay quiet where
                # nothing ever did. A fact about the body, kept on the body.
                region_entry["uncovered"] = True
            region_entry["garments"] = kept
    return rederive_entry(entry)


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


# What a region reads as when nothing is on it and the story does not spell out
# the body underneath. Not "" -- an empty value reads as "unknown" to a model,
# and the whole point of a fixed region list is that every region answers.
BARE = "bare"


# The characters that MEAN something in a compact line. A garment name or a
# look containing one would make the line ambiguous to read -- and commas are
# the reason this exists: "A snug, ribbed tank top in charcoal" sat next to
# "(loosened, wine-stained)" and nothing could tell a description's comma from
# a separator's. Structural joins now use `;`, which a look cannot contain
# because `;` is one of the sentence boundaries the look is cut at, and every
# value is stripped of the rest on the way out.
_LINE_STRUCTURAL = str.maketrans({c: " " for c in "|:=+[];"})


def _safe(text):
    return " ".join(str(text or "").translate(_LINE_STRUCTURAL).split())


def _compact_garment_piece(garment, look, look_said):
    """One compact-line garment value, including its first unsaid look.

    EVERY REGION COMES THROUGH HERE. The zoned branch called this helper and
    every other region ran a byte-equivalent copy inline -- same `_safe`, same
    first-clause split, same word-boundary truncation, same `look_said`
    dedupe, same final join -- so a change to the look rule could land on what
    the Director is told about a torso and not about a skirt.
    """
    name = _safe(garment.get("name")) or "?"
    state = garment.get("state") or "worn"
    condition = garment.get("condition") or ""
    notes = [_safe(n) for n in
             (state if state != "worn" else "", condition) if n]
    # A GARMENT'S LOOK REACHES PROSE ONLY THROUGH THIS PAYLOAD. The Director
    # is the sole path by which what a thing looks like gets into the
    # narration, so stripping descriptions outright would quietly cost the
    # story its clothing detail -- a change nothing errors on and nobody
    # notices for fifty beats. `look` keeps the FIRST CLAUSE, which is where a
    # garment's appearance lives, and drops the provenance after it: "a small
    # spring-clip holding a single feather" survives, "souvenir from some
    # distant region, pinned into her copper-gold hair near the left fox ear"
    # does not.
    described = ""
    key = name.casefold()
    if look and key not in look_said:
        # Sentence boundaries only. Splitting on the COMMA as well turned
        # "A snug, ribbed tank top in charcoal" into "A snug" -- a bare
        # adjective, which is worse than no description at all. A comma
        # separates adjectives here far more often than clauses.
        clause = re.split(r"[;—.]", str(garment.get("description") or ""), 1)[0]
        clause = " ".join(clause.split())
        if len(clause) > int(look):
            # On a word boundary. A look cut mid-word ("A snug") reads as a
            # corrupted field rather than a short description.
            clause = clause[:int(look)].rsplit(" ", 1)[0]
        clause = clause.strip(" ,;-")
        if clause and clause.casefold() != key:
            described = _safe(clause)
            look_said.add(key)
    # NAME(state;condition)=look, in that order. The look goes LAST because it
    # is the only free-text field: it runs to the next `+` or `|`, neither of
    # which it can contain, so a reader always knows where it ends. With the
    # look in the middle, "...in charcoal(open)" read as though the
    # parenthesis belonged to the description.
    piece = "%s(%s)" % (name, ";".join(notes)) if notes else name
    return "%s=%s" % (piece, described) if described else piece


def compact_line(regions, beneath_visible=False, look=0):
    """One body's clothing as a SINGLE line, every region in a fixed order.

    `head:-|torso:blouse|waist:apron|groin:skirt(loosened)|legs:skirt|feet:sandals`

    `describe` renders one line per region and includes each garment's
    description, which is right for a panel and wasteful for the Director:
    measured on a live scene, raw attire is 10,629 chars and `describe`
    summaries are 2,999. This is tighter again, and it is tighter in the way
    that matters for a prompt -- the region list is FIXED and always in the same
    order, so the shape of the line never changes and only its values do.

    That fixed shape is not cosmetic. Cacheability is a property of the prefix,
    and a body whose clothing did not change this beat renders byte-identically,
    which is what lets a provider's prefix cache absorb it instead of charging
    for it again.

    A REMOVED garment does not linger as "(removed)". The region reports what is
    THERE now -- the layer beneath if the story spells that out, otherwise
    `bare`. Naming what is gone is how a prompt ends up describing a shirt that
    is on the floor as though it were still on the body.

    `beneath_visible` is the host's `attire_beneath` choice and is honoured
    exactly as `describe` honours it: with it off, an uncovered region says
    `bare` and the body's own description fills the gap. This function must
    never be the path that leaks what a story chose not to spell out.
    """
    parts = []
    # A spanning garment appears in every region it covers, so its look would
    # be repeated verbatim two or three times in one line. Said once, at its
    # first region; after that the name alone identifies it.
    look_said = set()
    for region in REGIONS:
        entry = (regions or {}).get(region) or {}
        # ATTACHING IS NOT COVERING, and the two have to be able to coexist in
        # one slot. A hair clip, a belt, a necklace is `worn at` a region and
        # conceals nothing, so a head wearing only a clip is still bare -- which
        # is exactly the rule `covered_regions` already applies (`state !=
        # "removed" and not attaches`). Folding them together would report a
        # covered head on the strength of a hair pin.
        present = [g for g in (entry.get("garments") or [])
                   if g.get("state") != "removed"]
        worn = [g for g in present if not g.get("attaches")]
        attached = [g for g in present if g.get("attaches")]
        # A displaced garment (worn, covering nothing here) must not fill the
        # slot as though it covered: the slot answers "what is over this
        # region", and it rides alongside instead — `[off:jacket]`, the
        # `[at:]` idiom — so the Director still knows it is on the body.
        displaced_here = [g for g in worn
                          if not covered_zones_for(g, region)]
        worn = [g for g in worn if covered_zones_for(g, region)]
        zones = REGION_ZONES.get(region)
        partial = bool(zones and any(
            isinstance(g.get("covered_zones"), dict)
            and region in g["covered_zones"] for g in worn))
        if partial:
            beneath_zones = _clean_beneath_zones(
                region, entry.get("beneath_zones"))
            zone_parts = []
            for zone in zones:
                covering = next(
                    (g for g in worn if zone in covered_zones_for(g, region)),
                    None)
                if covering:
                    value = _compact_garment_piece(
                        covering, look, look_said)
                else:
                    beneath = (beneath_zones.get(zone, "")
                               if beneath_visible else "")
                    value = _safe(beneath) or BARE
                zone_parts.append("%s>%s" % (zone, value))
            parts.append("%s:%s%s%s" % (
                region, "/".join(zone_parts), _displaced_text(displaced_here),
                _attached_text(attached)))
            continue
        if not worn:
            if displaced_here:
                parts.append("%s:%s%s%s" % (
                    region, BARE, _displaced_text(displaced_here),
                    _attached_text(attached)))
                continue
            # BENEATH ONLY SURFACES WHERE SOMETHING CAME OFF. A region that was
            # never covered -- hands, usually -- is `bare` and says nothing
            # further; a region whose garment is now `removed` reports what the
            # removal exposed. The distinction matters twice over: it keeps the
            # line honest about what actually happened this beat, and it keeps
            # the underlayer out of every payload for stories that merely have
            # uncovered regions, which is most of them.
            # The STANDING state, not the moment of removal. A body stays
            # exposed until it is covered again -- by new attire or by the
            # garment it discarded -- so the underlayer belongs in the payload
            # for as long as that is true, not only on the beat it became true.
            # Putting something back on ends it, because the region then has a
            # worn garment and never reaches this branch.
            #
            # A FACT ABOUT THE REGION, not one read off a corpse. This used to
            # look for a garment still sitting here under `state: "removed"`,
            # and `removed` now means the garment is genuinely gone from the
            # card -- an object in the world with no seat on the body it left.
            # `uncovered` is the same standing fact recorded where it belongs:
            # this region had something and no longer does. A region that was
            # NEVER covered has no flag and still says `bare` and nothing more.
            #
            # EITHER signal, because this renders regions from anywhere: the
            # commit path releases removed garments and sets the flag, but the
            # attire editor, a restored archive and every chat saved before
            # this change all hold regions where the garment is still sitting
            # there under `state: "removed"`. Reading only the flag would have
            # gone quiet on every one of them.
            shed = bool(entry.get("uncovered")) or any(
                g.get("state") == "removed"
                for g in (entry.get("garments") or []))
            beneath = (_clean(entry.get("beneath"), BENEATH_LIMIT)
                       if (shed and beneath_visible) else "")
            parts.append("%s:%s%s" % (region, _safe(beneath) or BARE,
                                       _attached_text(attached)))
            continue
        pieces = [_compact_garment_piece(garment, look, look_said)
                  for garment in worn]
        parts.append("%s:%s%s%s" % (region, "+".join(pieces),
                                    _displaced_text(displaced_here),
                                    _attached_text(attached)))
    return "|".join(parts)


def _attached_text(attached):
    """Attaching garments as a suffix, so the slot's main value stays the
    answer to "is this covered" and the pins ride alongside rather than
    displacing it."""
    if not attached:
        return ""
    return "[at:%s]" % ";".join(_safe(g.get("name")) or "?" for g in attached)


def _displaced_text(displaced):
    """Garments worn but pushed off this region, as a suffix — the `[at:]`
    idiom for the displacement axis: `groin:bare[off:skirt]` is a hiked
    skirt, on the body and covering nothing here."""
    if not displaced:
        return ""
    return "[off:%s]" % ";".join(
        _safe(g.get("name")) or "?" for g in displaced)
