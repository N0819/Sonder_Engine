"""Weather: one sky over many rooms, and what each room gets of it.

Before this module, `scene["weather"]` was read by `backdrops.py` and
`ambience.py` and written by NOTHING -- no schema field, no Director output, no
commit path. Weather existed only as prose inside a room's description, which
meant it could not change without a description being rewritten, could not
differ between morning and midnight, and could not agree between two rooms
standing under the same sky.

Four rules shape what is here.

**0. The engine owns what weather DOES; the story owns what it is called.**
Review 2026-09-07 A88. This module used to be a closed Earth vocabulary --
five skies crossed with five falls -- and a sandstorm, an ashfall and a rain
of blood all normalised to `sky: storm` with the particulate lost, after which
the drift put ordinary rain in the middle of them once an in-story hour. What
is closed now is the set of things weather DOES to a body and a room (see
`AIRS`/`CLOUDS`/`FALL_KINDS` below), which this engine defines and can
enumerate; the sky's name and the fall's name are authored text nothing
matches against a list. Everything downstream reads the axis.

**1. Weather is a property of the SCENE, exposure is a property of the ROOM.**
There is one sky. A cellar, a courtyard and a rooftop under it are not having
three different weathers -- they are having three different amounts of the same
one. Modelling it the other way (weather per room) invites two adjacent
outdoor rooms to disagree, which is the sort of incoherence this engine exists
to avoid; and it would multiply the Director's bookkeeping by the room count.

**2. Exposure is authored where it can be, derived where it cannot.**
`rooms[id].exposure` is the source of truth. Every scene that predates this
module has none, so `room_exposure` falls back to a deliberately small keyword
pass over the room's own name and description -- and defaults to `enclosed`
when it sees nothing it recognises. That default is the conservative direction:
an unrecognised room quietly gets no weather, rather than rain appearing
indoors.

AND THE FALLBACK IS READ BY A RULE A MIND ACTS ON, which this paragraph denied
until E28 (2026-09-07). `world/spatial_light.room_light` asks `room_exposure`
whether the sky is a room's ceiling, and the light word it returns gates SIGHT
(`_LIGHT_SIGHT`): a room the word lists cannot place is a room a character can
be in the dark in. That use is the owner's, recorded in `docs/UNBUILT.md`
§ 2.28, and what makes it safe is the DEFAULT rather than the coverage -- an
unrecognised room reads `enclosed`, and an `enclosed` room keeps its declared
light untouched, so the failure direction is "a square that should have gone
dark stayed lit" and never a room darkened by a keyword. Widen the lists with
that direction in mind, and read `docs/UNBUILT.md` § 1.18 first: `exposure` is
authored on 13.6% of live rooms, so the fallback is not the fallback.

**3. Weather drifts deterministically, or it never moves.** A field only the
Director writes is a field that changes about once a story: it has no reason to
touch weather on a beat that was about a conversation. So `advance_weather` is
a seeded, idempotent progression on the simulation clock, in the same spirit as
`mechanics.py` -- same chat, same elapsed time, same result, so a reroll or a
resumed turn cannot produce a different sky. The Director still overrides it
outright whenever a beat says the storm breaks.

Most consumers are presentational (`backdrops.py`, `ambience.py`); one is not,
and it is `room_exposure` rather than the sky that crossed over -- see rule 2.
Thunder, rain on a window and a lit horizon are all things a character can
legitimately perceive, and a WEATHER fact that crosses into perception still
goes through the ordinary channels rather than being read out of this module
at the delivery site.
"""

from __future__ import annotations

import hashlib
import re

# --- what weather IS, and what weather DOES --------------------------------
#
# Two halves, and the split between them is the whole of review 2026-09-07
# A88.
#
# THE NAME IS THE STORY'S. "rain", "ashfall", "spore drift", "a slow fall of
# blood" -- authored free text, never matched against a list. This module used
# to hold a closed Earth vocabulary here instead (clear|fair|overcast|fog|storm
# crossed with drizzle|rain|snow|sleet|hail) and it failed twice over: a
# sandstorm and an ashfall both normalised to `sky: storm` with the
# particulate LOST, and the drift then read `_SKY_FALL["storm"]` and put rain
# in the middle of them.
#
# THE AXES ARE THE ENGINE'S, and they are what weather DOES to a body and to a
# room. Each is a small set this engine defines and can enumerate, which is a
# schema rather than a guess at how English will phrase something:
#
#   air          how much the air between two things blocks sight
#   cloud        how much of the day's own light the sky shuts out
#   electrical   whether the sky throws light and sound of its own
#   fall kind    what the falling stuff DOES on arrival: wets, piles, dusts
#   intensity    how much of it -- which is also how far its sound carries
#   wind         how much the air moves
#   temperature  what it costs a body to stand in
#
# A story that invents a fall this engine has never heard of gives it a name
# and says which of the four things it does; everything downstream -- footing,
# wetness, sound carry, the overlay, the discomfort in `world/exposure.py` --
# reads the AXIS and never the name. Nothing here has to be widened for a
# fiction to have weather in it.

#: How much the air itself blocks a look through it.
AIRS = ("clear", "hazy", "thick")
#: How much of the day's own light the sky shuts out.
CLOUDS = ("clear", "broken", "covered")
#: What a fall does when it lands. `other` is the honest answer for a fall a
#: story named without saying what it does: it arrives, it is seen and heard,
#: and this engine asserts nothing about wetness or footing from it. There is
#: no default of "liquid" -- guessing one is how a sandstorm rained.
FALL_KINDS = ("none", "liquid", "frozen", "particulate", "other")
INTENSITIES = ("none", "light", "moderate", "heavy")
WINDS = ("still", "breeze", "wind", "gale")
TEMPERATURES = ("freezing", "cold", "mild", "warm", "hot")

#: How long an authored weather name may be. It reaches an image prompt, a
#: sound query and a cache key, none of which want a paragraph; a name longer
#: than this is TRUNCATED, never rejected, so a story never loses its weather
#: to a length. Named per the house rule on caps.
NAME_LIMIT = 60

# How much of the sky a room is standing under.
EXPOSURES = ("open", "sheltered", "enclosed")

_DEFAULT = {
    "sky": "fair", "air": "clear", "cloud": "clear", "electrical": False,
    "precipitation": "none", "precipitation_kind": "none",
    "intensity": "none", "wind": "still", "temperature": "mild",
}

# --- reading what is already stored ----------------------------------------
#
# The five sky words and five fall words this engine used to be, mapped to
# their axes ONCE, at read (the ruling's own wording). Every live story's
# stored sky is one of these, so this is a MIGRATION TABLE and not a
# vocabulary: nothing consults it to decide whether a weather is valid, and a
# name it cannot read is a name, not an error.
_LEGACY_SKY_AXES = {
    #  sky word:  (air,     cloud,      electrical)
    "clear":      ("clear",  "clear",   False),
    "fair":       ("clear",  "broken",  False),
    "overcast":   ("clear",  "covered", False),
    "fog":        ("thick",  "covered", False),
    "storm":      ("clear",  "covered", True),
}

_LEGACY_FALL_KINDS = {
    "drizzle": "liquid", "rain": "liquid",
    "snow": "frozen", "sleet": "frozen", "hail": "frozen",
}

#: The two engine falls that used to make a storm sky silent. Hail is
#: deliberately absent and always was -- it comes out of exactly the
#: convective storms that do throw lightning -- which is why this is read off
#: the folded NAME and not off `frozen`, the axis that covers all three.
_LEGACY_UNLIT = ("snow", "sleet")

#: The sight phrase the five engine sky words have always produced. Kept so a
#: story running under a stored "fair" still reads "open sky" rather than
#: "fair sky"; any other name takes the general form below.
_LEGACY_SKY_PHRASE = {
    "clear": "clear sky", "fair": "open sky", "overcast": "overcast sky",
    "fog": "thick fog", "storm": "storm sky",
}

#: The name the engine gives a sky it is itself drifting, read off the axes.
#: Applied ONLY to a sky still carrying one of the five engine words -- the
#: drift moves the axes, and it renames the sky only when the name it holds is
#: one the engine wrote. A story's own word is never rewritten.
def _engine_sky_name(air, cloud, electrical):
    if electrical:
        return "storm"
    if air in ("hazy", "thick"):
        return "fog"
    return {"clear": "clear", "broken": "fair", "covered": "overcast"}[cloud]

# Words that mean a place is under the open sky, standing beneath something
# that only half covers it, or indoors. Checked longest-list-first in that
# order because a "covered market" is sheltered and not open, and a
# "underground car park" is enclosed even though "park" is outdoors.
_ENCLOSED_WORDS = (
    "cellar", "basement", "vault", "tunnel", "corridor", "hallway", "cabin",
    "bedroom", "bathroom", "kitchen", "office", "bridge", "engine room",
    "cockpit", "hold", "interior", "lobby", "stairwell", "attic", "loft",
    "chamber", "shop", "store room", "storeroom", "library", "laboratory",
    "lab", "cabin", "berth", "closet", "elevator", "turbolift", "lift",
    "underground", "indoors", "inside",
)
_SHELTERED_WORDS = (
    "porch", "veranda", "verandah", "awning", "canopy", "arcade", "colonnade",
    "cloister", "portico", "gatehouse", "shelter", "lean-to", "cave mouth",
    "covered", "under cover", "carport", "bandstand", "gazebo", "pergola",
    "tent", "marquee", "stable", "barn", "boathouse", "dugout", "overhang",
)
_OPEN_WORDS = (
    "street", "road", "lane", "alley", "courtyard", "yard", "square",
    "plaza", "rooftop", "roof", "terrace", "balcony", "garden", "field",
    "meadow", "moor", "clearing", "forest", "wood", "hillside", "hill",
    "mountain", "beach", "shore", "cliff", "quay", "pier",
    # "deck" and "dock" are deliberately ABSENT. On a ship they are open air;
    # on a starship a deck is a floor number and a dock is a hangar, and this
    # engine's live corpus is full of the latter. An authored `exposure` is the
    # right way to say "this one really is open", and guessing wrong here puts
    # rain inside a spacecraft.
    "park", "graveyard", "cemetery", "path", "trail", "track",
    "riverbank", "bank", "ridge", "valley", "plain", "desert", "outdoors",
    "outside", "open sky", "sky",
)

# Places that are deep by their nature. These matter only when the map cannot
# answer: an unmapped room is normally assumed to be one layer in (the common
# indoor case), but assuming that of a bunker or a cave system would put rain
# inside a mountain. A story that has actually mapped its cave passages gets
# the real depth from the graph and never consults this.
_DEEP_WORDS = (
    "cave", "cavern", "grotto", "bunker", "vault", "crypt", "catacomb",
    "mine", "shaft", "tunnel", "sewer", "undercroft", "dungeon", "silo",
    "sub-basement", "subbasement", "underground", "deep below", "buried",
)

# The words a model writes for the CLOSED AXES that are not the axis words
# themselves. Not a nicety: an exact-match lookup answers every one of them
# with the DEFAULT -- which is the mildest reading of each field. Live
# failure, "The Blizzard" turn 2. The Director declared, correctly and in
# full:
#
#     {"sky": "blizzard", "precipitation": "heavy snow", "intensity": "severe",
#      "wind": "gale-force", "temperature": "sub-zero"}
#
# Not one of the five matched. The declaration normalised to fair / none / none
# / still / mild -- a calm spring day -- and, being a declaration, replaced the
# blizzard that was actually blowing. The player stood in an open clearing in a
# whiteout with the snow overlay switched off and the wind gone from the room's
# sound, and every later beat inherited the calm.
#
# Substring matching (below) already catches "heavy snow" and "gale-force". This
# table is for the ones with no vocabulary word inside them at all.
#
# NAMES ARE NO LONGER FOLDED THROUGH IT. Since A88 the sky and the fall carry
# whatever the story called them, so "blizzard" stays "blizzard"; the sky and
# precipitation halves moved to `_LEGACY_FOLD` below, where their only job is
# to recognise a name this ENGINE once wrote so its axes can be derived. What
# remains here is the three closed axes a model still writes in its own words.
_SYNONYMS = {
    "intensity": {
        "severe": "heavy", "extreme": "heavy", "torrential": "heavy",
        "violent": "heavy", "driving": "heavy", "hard": "heavy",
        "intense": "heavy", "strong": "heavy", "fierce": "heavy",
        "steady": "moderate", "medium": "moderate", "normal": "moderate",
        "gentle": "light", "faint": "light", "slight": "light",
        "soft": "light", "thin": "light", "weak": "light",
    },
    "wind": {
        "gale-force": "gale", "galeforce": "gale", "howling": "gale",
        "hurricane": "gale", "tearing": "gale", "screaming": "gale",
        "gusty": "wind", "gusting": "wind", "gusts": "wind",
        "blustery": "wind", "windy": "wind", "brisk": "wind",
        "breezy": "breeze", "light": "breeze",
        "calm": "still", "none": "still", "nothing": "still",
        "motionless": "still", "dead": "still",
    },
    "temperature": {
        "sub-zero": "freezing", "subzero": "freezing", "frigid": "freezing",
        "arctic": "freezing", "icy": "freezing", "bitter": "freezing",
        "glacial": "freezing", "frozen": "freezing", "frosty": "freezing",
        "below zero": "freezing",
        "chilly": "cold", "cool": "cold", "crisp": "cold", "raw": "cold",
        "temperate": "mild", "moderate": "mild", "fine": "mild",
        "balmy": "warm", "pleasant": "warm",
        "hot": "hot", "sweltering": "hot", "baking": "hot",
        "scorching": "hot", "blazing": "hot", "sultry": "hot",
    },
}

# The engine's own five-and-five, plus the English that reaches them. Read for
# ONE purpose: a name whose axes were not declared, folded here to see whether
# it is a sky or a fall this engine itself used to mint, so its axes can be
# recovered. A name that folds to nothing keeps its axes from the record it is
# written over, or takes `other` -- it is never discarded and never guessed at.
_LEGACY_FOLD = {
    "sky": {
        "blizzard": "storm", "snowstorm": "storm", "thunderstorm": "storm",
        "tempest": "storm", "squall": "storm", "gale": "storm",
        "hurricane": "storm", "typhoon": "storm", "stormy": "storm",
        "cloudy": "overcast", "clouded": "overcast", "grey": "overcast",
        "gray": "overcast", "dull": "overcast", "leaden": "overcast",
        "sunny": "clear", "bright": "clear", "cloudless": "clear",
        "blue": "clear", "starry": "clear",
        "misty": "fog", "mist": "fog", "haze": "fog", "hazy": "fog",
        "foggy": "fog", "murk": "fog", "smog": "fog",
        "mild": "fair", "calm": "fair", "settled": "fair",
    },
    "precipitation": {
        "snowing": "snow", "flurries": "snow", "flurry": "snow",
        "blizzard": "snow", "raining": "rain", "downpour": "rain",
        "shower": "rain", "showers": "rain", "rainfall": "rain",
        "drizzling": "drizzle", "misting": "drizzle", "spitting": "drizzle",
        "sleeting": "sleet", "hailing": "hail", "dry": "none",
        "clear": "none", "nothing": "none",
    },
}


def _resolve(value, allowed, field=""):
    """One model-written word as a CLOSED AXIS value, or None.

    Exact match, then the synonym table, then any axis word CONTAINED in
    the phrase -- "heavy snow" is snow, "gale-force winds" is a gale. Where more
    than one is contained, the EARLIEST in the phrase wins: "gale-force wind"
    names a gale and qualifies it with the noun, and taking the first match in
    vocabulary order instead answered it with `wind`.

    None rather than a default when nothing resolves, so the caller can keep
    what the scene already had. A word this vocabulary cannot read is not
    evidence that the sky is fair.
    """
    text = str(value or "").strip().casefold()
    if not text:
        return None
    if text in allowed:
        return text
    mapped = _SYNONYMS.get(field, {}).get(text)
    if mapped in allowed:
        return mapped
    for word, mapped in _SYNONYMS.get(field, {}).items():
        if mapped in allowed and re.search(r"\b%s\b" % re.escape(word), text):
            return mapped
    hits = [(text.index(term), term) for term in allowed
            if term != "none" and term in text]
    return min(hits)[1] if hits else None


def _pick(value, allowed, fallback, field=""):
    return _resolve(value, allowed, field) or fallback


def _name(value, limit=NAME_LIMIT):
    """One authored weather name: whitespace folded, truncated, never mapped."""
    return " ".join(str(value or "").split())[:limit].strip()


def _fold_legacy(value, field):
    """The engine word a NAME folds to, or ''.

    Read for one purpose only -- recovering AXES from a name this engine
    itself once minted, or from the English a model writes for one. It never
    replaces the name: since A88 a story's "blizzard" stays "blizzard" and
    only its axes are read off the fold.
    """
    text = " ".join(str(value or "").split()).casefold()
    if not text:
        return ""
    known = _LEGACY_SKY_AXES if field == "sky" else _LEGACY_FALL_KINDS
    if text in known:
        return text
    table = _LEGACY_FOLD.get(field, {})
    mapped = table.get(text)
    if mapped:
        return mapped
    for word, mapped in table.items():
        if re.search(r"\b%s\b" % re.escape(word), text):
            return mapped
    hits = [(text.index(term), term) for term in known if term in text]
    return min(hits)[1] if hits else ""


def _weather_from_prose(text):
    """The fields a bare weather string states. What a model hands you about a
    third of the time ("heavy rain, gale, cold")."""
    text = str(text or "").casefold()
    out = {}
    for field, allowed in (("wind", WINDS), ("temperature", TEMPERATURES),
                           ("intensity", INTENSITIES)):
        found = _resolve(text, allowed, field)
        if found:
            out[field] = found
    for field in ("sky", "precipitation"):
        folded = _fold_legacy(text, field)
        if folded:
            out[field] = folded
    return out


def normalize_weather(value, base=None):
    """A weather record as a NAME plus the axes it acts on, or {} for nothing.

    Model output reaches this, so the AXES are a whitelist rather than a
    clean-up: an unreadable axis word must not travel on into a cache key, an
    image prompt and a sound query as a term nothing downstream can act on.
    The NAMES are not filtered at all -- since review 2026-09-07 A88 the sky
    and the fall carry whatever the story called them, and only their length
    is bounded (`NAME_LIMIT`). A bare string is accepted too.

    Where a name arrives with no axes, the axes are read off the name ONCE, by
    `_fold_legacy` -- which is how every scene stored before A88, and every
    Director still writing "storm", keeps behaving exactly as it did.

    `base` is the sky this value is being written OVER -- the weather the scene
    already had. A field left out, or written in words outside the axis,
    keeps what was there rather than collapsing to the default, because the
    default is the MILDEST reading of every field and a word this engine
    cannot read is not evidence that the weather has cleared. Without a base a
    missing field still defaults, so a first declaration remains complete.
    See `_SYNONYMS` for the failure that made this necessary.
    """
    if isinstance(value, str):
        value = _weather_from_prose(value)
    if not isinstance(value, dict) or not value:
        return {}
    base = base if isinstance(base, dict) else {}

    def axis(name, allowed, default):
        return _pick(value.get(name), allowed,
                     _pick(base.get(name), allowed, default, name), name)

    # --- the names, which are the story's ---------------------------------
    sky = _name(value.get("sky")) or _name(base.get("sky")) or _DEFAULT["sky"]
    fall = _name(value.get("precipitation")) or _name(base.get("precipitation"))

    # --- what the fall DOES ------------------------------------------------
    declared_kind = _resolve(value.get("precipitation_kind"), FALL_KINDS)
    folded_fall = _fold_legacy(fall, "precipitation")
    stated_fall = _name(value.get("precipitation"))
    if declared_kind == "none" or _fold_legacy(
            stated_fall or fall, "precipitation") == "none" \
            or (fall or "none").casefold() in ("", "none"):
        # Nothing is coming down. Both halves say so, so nothing downstream
        # has to reconcile a name against a kind.
        fall, kind = "none", "none"
    elif declared_kind:
        kind = declared_kind
    elif folded_fall:
        kind = _LEGACY_FALL_KINDS[folded_fall]
    elif not stated_fall:
        # The name was carried from the base; carry its kind with it.
        kind = _resolve(base.get("precipitation_kind"), FALL_KINDS) or "other"
    else:
        # A fall this engine has never heard of, and the story did not say
        # what it does. It falls, it is seen and it is heard; wetness and
        # footing are simply not asserted. Guessing `liquid` here is the A88
        # defect in one line.
        kind = "other"
    if kind != "none" and (fall or "none").casefold() in ("", "none"):
        # A kind declared with no name at all. The axis word is the last
        # resort, because the alternative is minting an Earth noun.
        fall = kind

    # --- how much of it, which is also how far its sound carries -----------
    stated_intensity = _resolve(value.get("intensity"), INTENSITIES, "intensity")
    if kind == "none":
        intensity = "none"
    elif stated_intensity is not None:
        # Including an explicit "none": a sky that HAS a fall and is not
        # dropping it right now. That is the state the drift moves through,
        # and the only reason `intensity` rather than the name answers
        # "is anything falling" (`is_falling`).
        intensity = stated_intensity
    else:
        intensity = _resolve(base.get("intensity"), INTENSITIES, "intensity")
        if intensity is None or intensity == "none":
            # A fall named with no strength anywhere is a beat declaring that
            # it is falling, not one declaring an amount of nothing.
            intensity = "moderate"

    # --- what the sky does, read off its name when it does not say ---------
    #
    # ORDER, and it is load-bearing. An axis this record states outranks
    # everything. Failing that, a record that NAMES a sky is making a
    # declaration, so the name's own axes are read; a record that names none
    # is a partial report over a sky that already stands, and that sky's
    # stored axes are what carry -- otherwise a beat saying only "the wind
    # rose" would re-derive the lightning from the word "storm" and put out a
    # flash the story had declared.
    declared_sky = bool(_name(value.get("sky")))
    legacy_sky = _LEGACY_SKY_AXES.get(_fold_legacy(sky, "sky")) \
        if declared_sky or not base else None
    carried_sky = _LEGACY_SKY_AXES.get(_fold_legacy(sky, "sky"))

    def sky_axis(field, allowed, index, default):
        stated = _resolve(value.get(field), allowed)
        if stated:
            return stated
        if legacy_sky is not None:
            return legacy_sky[index]
        held = _resolve(base.get(field), allowed)
        if held:
            return held
        return (carried_sky[index] if carried_sky else default)

    air = sky_axis("air", AIRS, 0, _DEFAULT["air"])
    cloud = sky_axis("cloud", CLOUDS, 1, _DEFAULT["cloud"])
    if isinstance(value.get("electrical"), bool):
        electrical = value["electrical"]
    elif legacy_sky is not None:
        electrical = legacy_sky[2]
        if electrical and folded_fall in _LEGACY_UNLIT:
            # The rule the old `_UNLIT_PRECIPITATION` set enforced, kept
            # exactly for records that still carry the engine's own words: a
            # snowing storm did not flash unless the record said thundersnow.
            # Read off the FOLDED NAME rather than the kind, because hail is
            # frozen and was deliberately not on that set -- it comes out of
            # exactly the convective storms that do throw lightning.
            flag = value.get("thundersnow")
            electrical = bool(base.get("thundersnow") if flag is None else flag)
    elif isinstance(base.get("electrical"), bool):
        electrical = base["electrical"]
    elif carried_sky is not None:
        electrical = carried_sky[2] and folded_fall not in _LEGACY_UNLIT
    else:
        electrical = bool(value.get("thundersnow") or base.get("thundersnow"))

    out = {
        "sky": sky,
        "air": air,
        "cloud": cloud,
        "electrical": bool(electrical),
        "precipitation": fall,
        "precipitation_kind": kind,
        "intensity": intensity,
        "wind": axis("wind", WINDS, _DEFAULT["wind"]),
        "temperature": axis("temperature", TEMPERATURES,
                            _DEFAULT["temperature"]),
    }
    # WHICH DRIFT WINDOW THIS SKY BELONGS TO. Carried from the RECORD and
    # never from the base, because a record written over is a new record: a
    # re-normalization of a stored sky keeps its window, and a beat DECLARING
    # a sky over one the scene already had is an authored fact that starts its
    # own (`DECLARED_STEP`). Absent when neither applies, so a scene whose sky
    # has never been drifted or declared serializes exactly as it did before
    # the field existed.
    stamp = value.get(DRIFT_STEP_KEY)
    if isinstance(stamp, bool) or not isinstance(stamp, (int, str)) \
            or (isinstance(stamp, str) and stamp != DECLARED_STEP):
        stamp = None
    if stamp is None and base:
        stamp = DECLARED_STEP
    if stamp is not None:
        out[DRIFT_STEP_KEY] = stamp
    return out


def is_falling(weather):
    """Is anything coming down right now?

    ONE representation, and this is it: `intensity` says WHETHER, the name and
    the kind say WHAT. Before A88 the pair could disagree -- a record naming a
    fall at intensity `none` read as raining an amount of nothing -- and the
    reconcile that hid it also made it impossible for a sky to keep its own
    fall through a dry spell, which is what the drift needs in order to move
    along the axes instead of picking a new Earth word out of a table.
    """
    weather = weather if isinstance(weather, dict) else {}
    return (str(weather.get("intensity") or "none") != "none"
            and str(weather.get("precipitation_kind") or "none") != "none")


#: What a room's own record says about it, derived once per record.
#:
#: Review 2026-09-07 C17. Everything that asks whether the sky reaches a place
#: goes through `room_exposure` -- the ground ledger, the light field, the
#: sound and scent fields, the backdrop prompt -- and `weather_depth`'s graph
#: walk asks it once per node it visits, for every room it is asked about. On
#: chat 117's stored 38-room scene one `weather_for_room` pass over the scene
#: made 1341 of those calls: 35 asks per room, each casefolding the room's
#: name and description afresh and scanning ~110 keywords over the result.
#:
#: The key is the WHOLE READ SET -- the four fields the derivation looks at --
#: so the memo cannot go stale: a room whose text is edited is a different key
#: the next time it is asked, and two chats whose rooms read identically have
#: the same right answer. It holds objective world state and no observer, so
#: it cannot carry one mind's view to another. Bounded the way
#: `spatial_fov._ANCHOR_CACHE` and `spatial_light_field._FIELD_CACHE` are:
#: cleared whole when full, because every entry is recomputable and dropping
#: one costs a casefold and a keyword pass, never an answer.
_ROOM_FACTS: dict = {}
_ROOM_FACTS_MAX = 1024


def _room_facts(room):
    """`(haystack, exposure)` for one room record, memoised on the record.

    The casefolded text is handed back alongside the exposure because it is
    the same parse: `_matches` scans it for the deep and reverberant words
    that `room_exposure` has already built it to answer.
    """
    key = (room.get("parent_entity"), room.get("exposure"),
           room.get("name"), room.get("desc"))
    try:
        cached = _ROOM_FACTS.get(key)
    except TypeError:
        # One of the four fields holds an unhashable value -- a malformed
        # record rather than a shape this engine writes. Answer it without
        # the memo rather than refusing it.
        return _derive_room_facts(room)
    if cached is not None:
        return cached
    facts = _derive_room_facts(room)
    if len(_ROOM_FACTS) >= _ROOM_FACTS_MAX:
        _ROOM_FACTS.clear()
    _ROOM_FACTS[key] = facts
    return facts


def _derive_room_facts(room):
    haystack = ("%s %s" % (room.get("name") or "",
                           room.get("desc") or "")).casefold()
    return (haystack, _derive_exposure(room, haystack))


def _derive_exposure(room, haystack):
    # AN INSIDE IS ENCLOSED, AND THAT IS NOT THE AUTHOR'S CALL. A room whose
    # record carries `parent_entity` is the inside of a body or a vehicle
    # (`world/spatial_transit.py`), and the sky is not its ceiling however the
    # field was filled in. This outranks the declared value because it is
    # structural rather than descriptive: the weather cannot reach inside a
    # thing, so there is nothing for an author to be right about. Measured
    # live (chat 114): a TARDIS console room minted `exposure: "sheltered"`
    # took the night sky for its ambient light, and `room_light` then darkened
    # its declared `lit` to `dark` -- the inside of a lamplit time machine
    # reading as pitch black at 1am because the field said the rain could
    # half-reach it.
    if str(room.get("parent_entity") or "").strip():
        return "enclosed"
    declared = _pick(room.get("exposure"), EXPOSURES, "")
    if declared:
        return declared
    if any(word in haystack for word in _ENCLOSED_WORDS):
        return "enclosed"
    # Sheltered BEFORE deep, so "Cave Mouth" is the overhang it is rather than
    # being swallowed by the "cave" in its name.
    if any(word in haystack for word in _SHELTERED_WORDS):
        return "sheltered"
    # Deep places are enclosed places, and this check has to come BEFORE the
    # open words: a cave is routinely described by the landscape it is in
    # ("Cave System — deep below the ridge"), and "ridge" alone made it read as
    # open ground, standing the player out in the rain inside a mountain.
    if any(word in haystack for word in _DEEP_WORDS):
        return "enclosed"
    if any(word in haystack for word in _OPEN_WORDS):
        return "open"
    return "enclosed"


def room_exposure(scene, room_id):
    """'open' | 'sheltered' | 'enclosed' for one room.

    The authored `exposure` field wins. Everything else is the keyword fallback
    described in rule 2 -- present because no existing scene has the field, and
    conservative by construction: a room whose text says nothing recognisable
    is treated as indoors, so weather appears in fewer places than it should
    rather than in places it should not.
    """
    return _room_facts(
        (((scene or {}).get("rooms") or {}).get(room_id) or {}))[1]


# Barriers that do not muffle: an open doorway is not a layer of building
# between you and the rain. READ from spatial.py rather than restated, so
# ambient sound has one definition in this engine -- a copy here would drift
# the day someone adds a rung to that set. Read at CALL time, not import:
# three `world/spatial_*` siblings import this module (for `room_exposure`
# and `weather_for_room`), and the facade imports every sibling at module
# scope, so a module-level `from world.spatial import ...` here was an
# import cycle waiting on import order -- it held only because each sibling
# happened to import weather inside a function (flagged 2026-09-04).
def _open_to_sound():
    from world.spatial import _AMBIENT_BARRIERS
    return _AMBIENT_BARRIERS


# A wall conducts nothing in this engine's model, so it is not an edge sound
# can walk. Everything else (a closed door, a window, a curtain) is one layer.
_SOUND_BLOCKS = ("wall",)

# How many muffling layers each strength of weather can still be heard through.
# Drizzle stops at the doorway; a downpour reaches two rooms in.
_REACH = {"none": -1, "light": 0, "moderate": 1, "heavy": 2}

# What that many layers does to the sound, and to its level. The gain is
# applied on top of the reader's own volume, so a muffled bed sits under an
# open-air one exactly as it would through a wall.
_MUFFLING = (
    # (layers, label, gain)
    (0, "", 1.0),
    (1, "muffled", 0.45),
    (2, "faint", 0.22),
)

# How far to walk the room graph looking for open air. A story's map can be
# large and the answer past two layers is "you cannot hear it" regardless.
_DEPTH_LIMIT = 4

# How thunder reads at each depth the rain is muffled to. One rung softer than
# the weather itself, never silent: the clap is what reaches a cellar when the
# snow does not.
_THUNDER_BY_MUFFLING = {"": "thunder", "muffled": "distant thunder",
                        "faint": "muffled thunder"}


def _thunder_words(muffling):
    return _THUNDER_BY_MUFFLING.get(str(muffling or ""), "muffled thunder")

# Places with hard surfaces and volume, where a sound arriving from outside
# arrives with the room's own tail on it. Purely a hint for choosing the
# RECORDING -- "echoing muffled rain" and "muffled rain" are different clips.
_REVERBERANT_WORDS = (
    "cave", "cavern", "grotto", "tunnel", "vault", "crypt", "catacomb",
    "cathedral", "chapel", "hall", "stairwell", "silo", "sewer", "mine",
    "cistern", "chamber", "atrium", "warehouse", "hangar",
)


def _matches(scene, room_id, words):
    # Same parse as `room_exposure`'s, and memoised with it (C17): the room's
    # text is casefolded once per record, not once per word list asked about.
    haystack = _room_facts(
        (((scene or {}).get("rooms") or {}).get(room_id) or {}))[0]
    return any(word in haystack for word in words)


def weather_depth(scene, room_id):
    """How many muffling layers separate `room_id` from the open air.

    0 means the weather is either on you or one open doorway away; 1 is a room
    behind a closed door off that; `None` means no path at all -- a sealed
    interior, where the storm outside is not a sound.

    Walks the room graph rather than guessing from the description, because the
    graph is where the engine already knows a cellar is two doors below a
    courtyard. Barrier semantics come from spatial.py's ambient set, so this
    cannot drift from how the engine gates every other ambient sound.
    """
    scene = scene or {}
    rooms = scene.get("rooms") or {}
    if room_id not in rooms:
        return None
    if room_exposure(scene, room_id) in ("open", "sheltered"):
        return 0

    # Breadth-first by LAYER COUNT, not by hop count: crossing an open doorway
    # is free, so a suite of open-plan rooms is all equally close to the rain.
    frontier, seen = {room_id}, {room_id}
    for layers in range(_DEPTH_LIMIT + 1):
        # Expand every free (unmuffled) hop first, so `layers` only counts the
        # boundaries that actually deaden sound.
        pending = list(frontier)
        while pending:
            current = pending.pop()
            if room_exposure(scene, current) in ("open", "sheltered"):
                return layers
            for edge in ((rooms.get(current) or {}).get("adjacent") or []):
                if not isinstance(edge, dict):
                    continue
                target = edge.get("to")
                barrier = str(edge.get("barrier") or "open").strip().casefold()
                if not target or target in seen or barrier in _SOUND_BLOCKS:
                    continue
                if barrier in _open_to_sound():
                    seen.add(target)
                    frontier.add(target)
                    pending.append(target)
        # Then step through the muffling boundaries, one layer at a time.
        step = set()
        for current in frontier:
            for edge in ((rooms.get(current) or {}).get("adjacent") or []):
                if not isinstance(edge, dict):
                    continue
                target = edge.get("to")
                barrier = str(edge.get("barrier") or "open").strip().casefold()
                if not target or target in seen or barrier in _SOUND_BLOCKS:
                    continue
                seen.add(target)
                step.add(target)
        if not step:
            return None
        frontier = step
    return None


def _mapped(scene, room_id):
    """Whether this room is joined to the map at all.

    An edge must name a destination to count. Live scenes carry adjacency
    entries that record only a bearing or a barrier ({'barrier': 'open',
    'dir': 'aft'}) -- those describe an opening without saying where it goes,
    so a room with nothing but those is still unmapped for the purpose of
    walking outward, and must not be treated as provably sealed.
    """
    room = (((scene or {}).get("rooms") or {}).get(room_id) or {})
    return any(isinstance(e, dict) and e.get("to")
               for e in (room.get("adjacent") or []))


def weather_for_room(scene, room_id):
    """What `room_id` actually gets of the scene's weather, or {}.

    The channels are separate because they fail separately: a cellar under a
    downpour sees nothing, feels nothing and may still HEAR it, and an image
    prompt, a sound query and a particle overlay each want a different one of
    those answers.
    """
    weather = normalize_weather((scene or {}).get("weather"))
    if not weather:
        return {}
    exposure = room_exposure(scene, room_id)
    falling = is_falling(weather)
    layers = weather_depth(scene, room_id)
    if layers is None and not _mapped(scene, room_id):
        # No path found AND no adjacency to walk: the room is simply not joined
        # to the map yet, which is a gap in the data and not a statement that it
        # is sealed. Assume one layer in -- the commonest indoor case -- so a
        # downpour is still heard, muffled. Silence is only ever asserted for a
        # room whose OWN edges lead nowhere near the air.
        # ...unless the room is deep by its nature. A bunker or a cave is not
        # "an ordinary room we have not mapped yet", and rain inside a mountain
        # is a worse error than silence in a cellar.
        layers = _DEPTH_LIMIT if _matches(scene, room_id, _DEEP_WORDS) else 1
    reach = _REACH.get(weather["intensity"], -1)
    # Sheltered is its own case: covered but not built into, so the rain is
    # right there and only the roof is between you and it.
    audible = falling and layers is not None and layers <= reach
    muffling, gain = "", 1.0
    if audible:
        # `_REACH`'s ceiling (2) IS `_MUFFLING`'s last limit, and the loop is
        # only entered when `layers <= reach`, so a rung always matches. The
        # `for...else` that used to sit here could not fire and therefore
        # proved nothing. The two tables are one ladder read from opposite
        # ends -- keep them in step: a new intensity reaching further needs a
        # new muffling rung, or a sound would arrive through more layers than
        # there is a word for.
        for limit, label, level in _MUFFLING:
            if layers <= limit:
                muffling, gain = label, level
                break
        if exposure == "sheltered" and not muffling:
            gain = 0.8
    return dict(weather, **{
        "exposure": exposure,
        # Can you see the sky from here? The whole question the overlay asks.
        "sky_visible": exposure == "open",
        # Is it landing on you? A porch keeps the rain off and the wind does
        # not care about a porch.
        "falls_on_you": falling and exposure == "open",
        "wind_reaches": exposure in ("open", "sheltered")
        and weather["wind"] in ("wind", "gale"),
        # Can you SEE weather from here? A different question from
        # `sky_visible`, and the one the overlay actually asks. Under an awning
        # the sky above you is a plank and `sky_visible` is rightly false, but
        # the rain a metre beyond the eaves is the entire scene -- standing out
        # of it and watching it fall is what sheltering IS. Sight was the only
        # channel treating a porch as a sealed room; sound and wind already
        # reach one.
        #
        # WHAT MAKES A DRY SKY VISIBLE IS AN AXIS, not the word "storm" (A88):
        # a sky throwing light of its own, or air you cannot see through, is
        # weather happening whatever the fiction calls it. Cloud alone is
        # deliberately not enough -- a grey sky is a colour, not an event.
        "weather_visible": (falling or weather["electrical"]
                            or weather["air"] != "clear")
        and exposure in ("open", "sheltered"),
        # And how much of it is in view: all of it in the open, the edges of it
        # from under cover.
        "visible_reach": 1.0 if exposure == "open"
        else (0.45 if exposure == "sheltered" else 0.0),
        # Audible from further in than it is visible, and quieter the deeper in
        # you go: rain on a roof one room away, the same rain barely there two
        # rooms further, nothing at all in a sealed vault.
        "audible": audible,
        "layers": layers,
        "muffling": muffling,
        # Hard surfaces and volume: rain arriving into a cave comes with the
        # cave on it. Only a hint for which recording to choose, never a gate.
        "reverberant": bool(muffling) and _matches(scene, room_id, _REVERBERANT_WORDS),
        "gain": round(gain, 2) if audible else 0.0,
    })


def has_lightning(weather):
    """Does this sky throw light and sound of its own?

    ONE axis now, read here and nowhere else derived (A88). It used to be a
    question about the word "storm" crossed with the word "snow", with a
    `thundersnow` flag bolted on for the case that crossing got wrong -- three
    Earth nouns deciding whether a sky flashes. A sky that flashes is a sky
    the story said flashes; `normalize_weather` recovers the answer for every
    record written before the axis existed, including the thundersnow flag.
    """
    weather = weather if isinstance(weather, dict) else {}
    return bool(weather.get("electrical"))


def weather_words(scoped, channel="sight"):
    """Short phrases describing this room's weather on ONE channel.

    The channel argument is not a convenience. Sight and sound reach different
    distances through the same wall -- a cellar under a downpour sees nothing
    and hears it clearly -- and a single undifferentiated word list put "heavy
    rain outside" into an image prompt for a room with no window, and repainted
    a cached backdrop for weather that room could only hear. Callers must say
    which sense they are asking about.

    Returns [] when nothing reaches the room on that channel, which is the
    common case indoors and is what keeps a cellar's picture and sound bed free
    of a storm three floors up.
    """
    if not scoped:
        return []
    words = []
    if channel == "sight":
        if scoped.get("sky_visible"):
            # The sky's own NAME, which is the story's (A88). The five words
            # this engine used to mint keep the exact phrase they always
            # produced, so a scene stored under `fair` still reads "open sky";
            # anything else takes the general form, and "an ash-choked pall
            # sky" is the shape a made-up sky arrives in.
            sky = str(scoped.get("sky") or "").strip()
            words.append(_LEGACY_SKY_PHRASE.get(sky.casefold())
                         or ("%s sky" % sky if sky else "sky"))
        if scoped.get("falls_on_you"):
            words.append("%s %s" % (scoped["intensity"], scoped["precipitation"]))
        if scoped.get("wind_reaches"):
            words.append("%s blowing" % scoped["wind"])
        return words

    # Sound. The noun leads, because a search query is ranked on its terms and
    # "rain" is the one that has to survive any truncation downstream. The
    # muffling word matters as much as the intensity: "muffled rain" and "heavy
    # rain" are different RECORDINGS, not the same recording at two volumes,
    # and a library has both.
    if scoped.get("audible"):
        if scoped.get("muffling"):
            words.append("%s %s" % (scoped["muffling"], scoped["precipitation"]))
            words.append("echoing cave reverb" if scoped.get("reverberant")
                         else "indoors through wall")
        else:
            words.append("%s %s" % (scoped["precipitation"], scoped["intensity"]))
            if not scoped.get("falls_on_you"):
                words.append("under cover")
    # Thunder carries where nothing else does: through a wall, into a cellar,
    # from a sky nobody in the room can see. Carrying is not arriving
    # undiminished, though -- a room that reports `faint snow` and a
    # full-strength clap is describing two distances at once. It is graded one
    # rung SOFTER than the rain in the same room, because that is the whole
    # point of thunder: it gets in where the weather does not.
    if has_lightning(scoped) and (
            scoped.get("exposure") != "enclosed" or scoped.get("audible")):
        words.append(_thunder_words(scoped.get("muffling")))
    if scoped.get("wind_reaches"):
        words.append(scoped["wind"])
    return words


# --- deterministic drift ---------------------------------------------------
#
# Weather that only the Director changes is weather that never changes. This
# walks it slowly, on the simulation clock, from a seed -- so the same chat at
# the same elapsed time always has the same sky, no matter how many times the
# turn is rerun, rerolled or resumed.

# Roughly one step per in-story hour. Fast enough that a long scene sees the
# sky move, slow enough that it is not weather-as-strobe.
DRIFT_SECONDS = 3600

#: The drift window a weather record belongs to, stamped on the record itself
#: (`advance_weather`). Present only once a record has been placed in a
#: window, so a scene whose sky has never been drifted or declared hashes and
#: archives exactly as it did before this field existed.
DRIFT_STEP_KEY = "drift_step"

#: A sky a BEAT declared, waiting to be placed. The drift is the world's own
#: cycle and a declaration is an authored fact, so a declaration outranks the
#: roll for as long as it stands: the next drift check stamps it with the
#: window it is observed in and returns it unchanged, and only the window
#: AFTER that rolls on from it.
#:
#: Measured 2026-09-05 ("The Long Road to Ambry", turns 10-13): `step =
#: elapsed // DRIFT_SECONDS` is CUMULATIVE and was used only as a roll salt,
#: while the transition walked `_SKY_NEXT` from whatever sky the scene
#: currently had -- so past the first in-story hour the sky took a fresh hop
#: on EVERY commit. Four consecutive beats inside one window went fair ->
#: overcast/drizzle -> storm/rain/gale, then the Director declared
#: overcast/drizzle/breeze, and the next beat put the gale back. Fifteen
#: seconds of story time, and the invented storm went on to raise the
#: clearing's noise floor to 2.8 and silence a conversation.
DECLARED_STEP = "declared"

# THE DRIFT MOVES AXES, AND IT NEVER MOVES A NAME.
#
# Review 2026-09-07 A88. There used to be three tables here keyed by the five
# Earth sky words -- `_SKY_NEXT` (what a sky becomes), `_SKY_FALL` (what it is
# willing to drop) and `_SKY_WIND` -- and the second of them is the defect: a
# sandstorm and an ashfall both normalised to `sky: storm`, and `_SKY_FALL`
# then rolled `("rain", "heavy")` over them once an in-story hour. There is no
# table of weathers any more, because there is no set of weathers a story may
# have.
#
# What is left is one motion, applied to a ladder: a rung up, a rung down, or
# stay. Three of the four axes walk it -- `cloud`, `wind`, and `intensity` --
# and the rule that stops the drift inventing anything is that INTENSITY IS
# THE ONLY THING IT MAY DO TO A FALL. What falls, and what it is called, are
# the story's, carried through the drift untouched; a sky with nothing to drop
# never starts dropping something.
#
# `air`, `temperature` and `electrical` are not drifted at all. They are the
# axes a beat DECLARES -- the fog coming down, the night turning bitter, the
# storm beginning to throw light -- and guessing at them here is the same
# mistake in a different field.
_DRIFT_STEPS = (0, 1, -1)


def _walk(ladder, value, roll):
    """One rung along a closed ladder, chosen by a seeded roll."""
    try:
        at = ladder.index(value)
    except ValueError:
        return ladder[0]
    return ladder[max(0, min(len(ladder) - 1,
                             at + _DRIFT_STEPS[roll % len(_DRIFT_STEPS)]))]


def _roll(seed, step, salt):
    """A stable pseudo-random integer for (seed, step, salt).

    Hashing rather than seeding an RNG because the value has to be the same in
    a fresh process, after a restart, and on a replayed turn -- `random` with a
    seed would be, but only if nothing else ever draws from it in between.
    """
    blob = "%s|%s|%s" % (seed, step, salt)
    return int(hashlib.sha256(blob.encode("utf-8")).hexdigest()[:8], 16)


def advance_weather(weather, elapsed_seconds, seed, severity=None):
    """The sky after `elapsed_seconds`, drifted deterministically.

    IT MOVES AXES AND CARRIES NAMES (review 2026-09-07 A88). `cloud` and
    `wind` walk one rung; `intensity` walks one rung too, but only while the
    sky is shut in, and only for a fall the story has already established --
    so a sky that has never dropped anything stays dry, and a sky dropping ash
    goes on dropping ash. The drift renames a sky only when the name it is
    carrying is one this engine minted itself (`_engine_sky_name`); a story's
    own word for its own sky is never rewritten. Returns the input unchanged
    inside one drift window, so an ordinary conversational beat does not move
    the weather at all.

    `severity` is the story's authored ceiling (see `severity_intensity_cap`).
    A caller that does not know it passes nothing and gets an uncapped drift,
    because the calm ceiling is a choice a story made and not a default to
    fall back to.

    ONE DRIFT PER WINDOW, AND A DECLARED SKY OUTRANKS THE ROLL. `elapsed` is
    cumulative, so `step` names the window rather than counting hops; the
    window is stamped on the record (`DRIFT_STEP_KEY`) and the sky moves only
    when it ADVANCES. A sky a beat declared carries `DECLARED_STEP` instead:
    it is placed in whatever window first observes it and returned unchanged,
    so it stands for the rest of that window and the NEXT one drifts from it.
    Without the stamp every commit past the first in-story hour took a fresh
    hop from the current sky and reverted the Director's declaration the beat
    after it landed -- see `DECLARED_STEP` for the measurement.
    """
    weather = normalize_weather(weather) or dict(_DEFAULT)
    try:
        step = int(max(0.0, float(elapsed_seconds)) // DRIFT_SECONDS)
    except (TypeError, ValueError):
        return weather
    if step <= 0:
        return weather
    stamped = weather.get(DRIFT_STEP_KEY)
    if stamped == DECLARED_STEP:
        return dict(weather, **{DRIFT_STEP_KEY: step})
    if stamped == step:
        return weather

    cloud = _walk(CLOUDS, weather["cloud"], _roll(seed, step, "cloud"))
    wind = _walk(WINDS, weather["wind"], _roll(seed, step, "wind"))
    kind = weather["precipitation_kind"]
    if kind == "none":
        # Nothing has ever fallen from this sky. The drift does not get to
        # decide that something does -- that is the whole of A88.
        intensity = "none"
    elif cloud == "covered":
        intensity = _walk(INTENSITIES, weather["intensity"],
                          _roll(seed, step, "fall"))
    else:
        # A sky opening up puts its fall down. Stated as the axis rather than
        # as a fall table: whatever a story's weather is made of, it does not
        # come out of a sky that has cleared.
        intensity = _walk(INTENSITIES, weather["intensity"], 2)
    intensity = _capped_intensity(intensity, severity)
    sky = weather["sky"]
    if _fold_legacy(sky, "sky") == sky.strip().casefold():
        # The sky is still wearing a word this engine wrote, so this engine
        # may keep it in step with the axes it just moved. An authored name
        # is left exactly as the story wrote it.
        sky = _engine_sky_name(weather["air"], cloud, weather["electrical"])
    return normalize_weather({
        "sky": sky,
        "air": weather["air"],
        "cloud": cloud,
        "electrical": weather["electrical"],
        "precipitation": weather["precipitation"],
        "precipitation_kind": kind,
        "intensity": intensity,
        "wind": wind,
        # Temperature is authored, not drifted: a beat that says the night
        # turns bitter is the Director's to write, and guessing it here would
        # fight that.
        "temperature": weather["temperature"],
        DRIFT_STEP_KEY: step,
    })


# --- what the weather leaves behind ----------------------------------------
#
# Weather that changes nothing is scenery. An hour of heavy rain should leave a
# yard muddy, a night of snow should leave it deep, and both should still be
# there once the sky clears -- because that is what the reader will expect to
# walk through, and because the room SOUNDS and LOOKS different afterwards.
#
# Deliberately a small integer per room rather than a simulation. `level`
# accumulates while something falls on a room that is open to it and drains
# when it stops; the label is read off a ladder chosen by what fell. That makes
# it deterministic, cheap, idempotent under reroll, and legible in the scene
# blob a host can open and edit.

# Each ladder is ordered by depth: level 1 takes the first rung, and the last
# rung is the floor for anything deeper.
# FOOTING IS AN AXIS TOO (A88). A ladder is chosen by what the fall DOES on
# arrival crossed with the temperature -- never by its name -- so ash, spores
# and a fall of blood each land on a floor the engine can describe without
# ever having heard of them. `piled` carries the fall's own name, which is the
# whole point: "drifts of ash" and "deep snow" come out of one ladder.
GROUND_LADDERS = {
    "wet": ("damp ground", "wet ground", "standing puddles", "churned mud"),
    "ice": ("frost underfoot", "sheet ice"),
    "slush": ("slush underfoot", "deep slush"),
    "piled": ("a dusting of %s", "%s underfoot", "deep %s", "drifts of %s"),
    # The names this engine wrote before the axes existed, kept so a floor
    # already carrying one goes on reading as it did while it drains.
    "snow": ("a dusting of snow", "snow underfoot", "deep snow", "snowdrifts"),
    "hail": ("scattered hailstones",),
}

# Which ladder each fall kind lays down, and where temperature changes the
# answer. Freezing turns a liquid floor into an ice one -- the single most
# consequential thing temperature does to a floor -- and a frozen fall landing
# on ground above freezing turns to slush instead of piling.
def _ground_ladder(kind, temperature):
    if kind == "liquid":
        return "ice" if temperature == "freezing" else "wet"
    if kind == "frozen":
        return "piled" if temperature in ("freezing", "cold") else "slush"
    if kind == "particulate":
        return "piled"
    # `other` and `none`: this engine was told a name and no axis, so it
    # asserts nothing about the floor. Silence, not a guess at mud.
    return ""

# How fast it piles up, per beat, by intensity.
_GROUND_GAIN = {"light": 1, "moderate": 2, "heavy": 3}
# ...and how fast it goes away once nothing is falling. Slower than it arrives:
# ground dries and snow lingers, and a puddle that vanished the moment the rain
# stopped would read as a bug.
_GROUND_DRAIN = 1
_GROUND_MAX = 12


def ground_kind(weather, ground=None):
    """Which ladder this sky is laying down, or the one already on the ground."""
    return _ground_of(weather, ground)[0]


def _ground_of(weather, ground=None):
    """`(ladder, name)` for the floor this sky is making.

    The NAME rides with the ladder because `piled` renders with it, and
    because a floor keeps draining after the sky that made it has cleared --
    a room three beats into a dry spell still has ash on it, and nothing else
    on disk remembers what fell.
    """
    weather = normalize_weather(weather) or {}
    ground = ground if isinstance(ground, dict) else {}
    if is_falling(weather):
        ladder = _ground_ladder(weather.get("precipitation_kind"),
                                weather.get("temperature"))
        return ladder, _name(weather.get("precipitation"))
    return (str(ground.get("kind") or "wet"),
            _name(ground.get("name")))


def ground_after(previous, scoped, severity=None, exposed=True):
    """The state of one room's floor after this beat.

    `scoped` is that room's own weather (`weather_for_room`), so a cellar under
    a downpour stays dry: what matters is whether anything is landing HERE, not
    whether it is falling somewhere overhead.

    Returns {} for a floor with nothing on it, which keeps the scene blob free
    of an entry per room per beat saying "still dry".
    """
    from story.scene import DEFAULT_WEATHER_SEVERITY, WEATHER_SEVERITIES

    severity = severity if severity in WEATHER_SEVERITIES else DEFAULT_WEATHER_SEVERITY
    previous = previous if isinstance(previous, dict) else {}
    level = max(0, min(_GROUND_MAX, int(previous.get("level") or 0)))
    if severity == "calm":
        # Weather is scenery here, by the host's choice. Anything already on
        # the ground drains away rather than being stranded mid-puddle.
        level = max(0, level - _GROUND_DRAIN)
        if not level:
            return {}
        return dict(previous, level=level, state=_ground_state(
            str(previous.get("kind") or "wet"), level,
            _name(previous.get("name"))))

    scoped = scoped or {}
    # `falls_on_you` is the honest test: a porch is under the sky and still
    # dry underfoot, and its floor should stay that way.
    landing = bool(is_falling(scoped) and exposed
                   and scoped.get("falls_on_you"))
    kind, name = _ground_of(scoped, previous)
    if not kind:
        # A fall whose axis nothing stated leaves nothing this engine is
        # willing to describe underfoot. Whatever was already there drains.
        landing = False
        kind, name = str(previous.get("kind") or "wet"), _name(
            previous.get("name"))
    if landing:
        level = min(_GROUND_MAX,
                    level + _GROUND_GAIN.get(scoped.get("intensity"), 1))
    else:
        level = max(0, level - _GROUND_DRAIN)
    if not level:
        return {}
    out = {"kind": kind, "level": level,
           "state": _ground_state(kind, level, name)}
    if name and any("%s" in rung for rung in GROUND_LADDERS.get(kind, ())):
        # Only when the ladder renders with it, so a wet or icy floor
        # serializes exactly as it did before the field existed.
        out["name"] = name
    return out


def _ground_state(kind, level, name=""):
    ladder = GROUND_LADDERS.get(kind) or GROUND_LADDERS["wet"]
    # Three beats of accumulation per rung, so a floor passes through its
    # states rather than jumping to the deepest one in a single downpour.
    rung = min(len(ladder) - 1, max(0, (level - 1) // 3))
    text = ladder[rung]
    return text % (name or "fallen matter") if "%s" in text else text


def severity_intensity_cap(severity):
    """The worst this story's sky is allowed to drift to.

    Only `calm` caps anything: the difference between seasonal, harsh and
    catastrophic is what the weather is permitted to DO, not how hard it comes
    down, and that permission belongs to the Director rather than to a table.
    The three upper values are therefore identical HERE and not identical in
    the story: the whole style guide, `weather_severity` included, is handed
    to the Director (`agents/director.py:293`) and to mapping, which is the
    surface that reads a permission.

    Read by `advance_weather`, which is the only thing that drifts a sky
    unattended; a declared beat is the Director's and is not capped.
    """
    return "light" if severity == "calm" else "heavy"


def _capped_intensity(intensity, severity):
    """`intensity`, lowered to the story's ceiling. Ordered by INTENSITIES, so
    a new rung between two existing ones needs no change here."""
    if not severity:
        return intensity
    cap = severity_intensity_cap(severity)
    try:
        if INTENSITIES.index(intensity) <= INTENSITIES.index(cap):
            return intensity
    except ValueError:
        return intensity
    return cap
