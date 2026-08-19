"""Weather: one sky over many rooms, and what each room gets of it.

Before this module, `scene["weather"]` was read by `backdrops.py` and
`ambience.py` and written by NOTHING -- no schema field, no Director output, no
commit path. Weather existed only as prose inside a room's description, which
meant it could not change without a description being rewritten, could not
differ between morning and midnight, and could not agree between two rooms
standing under the same sky.

Three rules shape what is here.

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
indoors. This derivation is a convenience, never an authority: it must not be
used for anything a mind could act on, only for what a place looks and sounds
like.

**3. Weather drifts deterministically, or it never moves.** A field only the
Director writes is a field that changes about once a story: it has no reason to
touch weather on a beat that was about a conversation. So `advance_weather` is
a seeded, idempotent progression on the simulation clock, in the same spirit as
`mechanics.py` -- same chat, same elapsed time, same result, so a reroll or a
resumed turn cannot produce a different sky. The Director still overrides it
outright whenever a beat says the storm breaks.

The consumers are presentational (`backdrops.py`, `ambience.py`), and one
future one is not: thunder, rain on a window and a lit horizon are all things a
character can legitimately perceive. Anything that crosses into perception must
go through the ordinary channels rather than reading this module directly.
"""

from __future__ import annotations

import hashlib
import re

# --- vocabulary ------------------------------------------------------------
#
# Small and closed on purpose. These strings reach an image prompt, a sound
# search and (later) a particle overlay, all of which want a term they can act
# on rather than a sentence; and a closed set is what lets the drift below be a
# table instead of a paragraph of prose parsing.

SKIES = ("clear", "fair", "overcast", "fog", "storm")
PRECIPITATION = ("none", "drizzle", "rain", "snow", "sleet", "hail")
INTENSITIES = ("none", "light", "moderate", "heavy")
WINDS = ("still", "breeze", "wind", "gale")
TEMPERATURES = ("freezing", "cold", "mild", "warm", "hot")

# How much of the sky a room is standing under.
EXPOSURES = ("open", "sheltered", "enclosed")

_DEFAULT = {
    "sky": "fair", "precipitation": "none", "intensity": "none",
    "wind": "still", "temperature": "mild",
}

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

# Precipitation that means the storm is NOT an electrical one. A blizzard is a
# storm sky full of snow, and it does not flash: thundersnow exists, but it is
# rare enough that having it every time is worse than never having it, and a
# reader watching lightning play over a whiteout is being told something false
# about the weather they are standing in. Hail is deliberately absent -- hail
# comes out of exactly the convective storms that do throw lightning.
_UNLIT_PRECIPITATION = ("snow", "sleet")


# The words a model writes for weather that are not the words this vocabulary
# uses. Not a nicety: the closed vocabulary is five short enums, a Director
# describing a storm reaches for the vivid word every time, and an exact-match
# lookup answers every one of them with the DEFAULT -- which is the mildest
# reading of each field. Live failure, "The Blizzard" turn 2. The Director
# declared, correctly and in full:
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
_SYNONYMS = {
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


def _resolve(value, allowed, field=""):
    """One model-written weather word as a vocabulary term, or None.

    Exact match, then the synonym table, then any vocabulary word CONTAINED in
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


def normalize_weather(value, base=None):
    """A weather dict reduced to the closed vocabulary, or {} for nothing.

    Model output reaches this, so it is a whitelist rather than a clean-up: an
    unrecognised sky must not travel on into a cache key, an image prompt and a
    sound query as a word nothing downstream can act on. A bare string
    ("raining") is accepted too, because that is what a model hands you about a
    third of the time.

    `base` is the sky this value is being written OVER -- the weather the scene
    already had. A field left out, or written in words outside the vocabulary,
    keeps what was there rather than collapsing to the default, because the
    default is the MILDEST reading of every field and a word this vocabulary
    cannot read is not evidence that the weather has cleared. Without a base a
    missing field still defaults, so a first declaration remains complete.
    See `_SYNONYMS` for the failure that made this necessary.
    """
    if isinstance(value, str):
        text = value.casefold()
        value = {}
        for field, allowed in (("sky", SKIES), ("precipitation", PRECIPITATION),
                               ("wind", WINDS), ("temperature", TEMPERATURES),
                               ("intensity", INTENSITIES)):
            # "raining"/"snowing" are the commonest forms and contain their
            # noun; `_resolve` also reads the words that do not.
            found = _resolve(text, allowed, field)
            if found:
                value[field] = found
    if not isinstance(value, dict) or not value:
        return {}
    base = base if isinstance(base, dict) else {}

    def field(name, allowed, default):
        return _pick(value.get(name), allowed,
                     _pick(base.get(name), allowed, default, name), name)

    out = {
        "sky": field("sky", SKIES, _DEFAULT["sky"]),
        "precipitation": field("precipitation", PRECIPITATION, "none"),
        "intensity": field("intensity", INTENSITIES, "none"),
        "wind": field("wind", WINDS, _DEFAULT["wind"]),
        "temperature": field("temperature", TEMPERATURES,
                             _DEFAULT["temperature"]),
        # Thundersnow: a storm that flashes while snowing. Real, spectacular,
        # and rare enough that it has to be a PROPERTY OF THIS SKY rather than
        # something derived from the precipitation -- derived, every blizzard
        # flashes; absent, none ever can. Set deterministically by the drift
        # (see advance_weather) or declared outright by a beat.
        # Carried from the base when this declaration says nothing about it,
        # like every other field: a beat that reports the wind rising must not
        # also, silently, put the lightning out.
        "thundersnow": bool(value.get("thundersnow")
                            if value.get("thundersnow") is not None
                            else base.get("thundersnow")),
    }
    # Falling water with no strength, or a strength with nothing falling, are
    # both half-written states that would read as "it is raining an amount of
    # nothing". Reconcile rather than store the contradiction.
    if out["precipitation"] != "none" and out["intensity"] == "none":
        out["intensity"] = "moderate"
    if out["precipitation"] == "none":
        out["intensity"] = "none"
    # Only a snowing storm can be thundersnow. Anywhere else the flag is either
    # meaningless (a clear sky) or redundant (a rainstorm flashes anyway), and
    # letting it linger would keep lightning over a sky that stopped snowing.
    if not (out["sky"] == "storm"
            and out["precipitation"] in _UNLIT_PRECIPITATION):
        out["thundersnow"] = False
    return out


def room_exposure(scene, room_id):
    """'open' | 'sheltered' | 'enclosed' for one room.

    The authored `exposure` field wins. Everything else is the keyword fallback
    described in rule 2 -- present because no existing scene has the field, and
    conservative by construction: a room whose text says nothing recognisable
    is treated as indoors, so weather appears in fewer places than it should
    rather than in places it should not.
    """
    room = (((scene or {}).get("rooms") or {}).get(room_id) or {})
    declared = _pick(room.get("exposure"), EXPOSURES, "")
    if declared:
        return declared
    haystack = "%s %s" % (room.get("name") or "", room.get("desc") or "")
    haystack = haystack.casefold()
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


# Barriers that do not muffle: an open doorway is not a layer of building
# between you and the rain. IMPORTED from spatial.py rather than restated, so
# ambient sound has one definition in this engine -- a copy here would drift
# the day someone adds a rung to that set.
from world.spatial import _AMBIENT_BARRIERS as _OPEN_TO_SOUND  # noqa: E402
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
    room = (((scene or {}).get("rooms") or {}).get(room_id) or {})
    haystack = ("%s %s" % (room.get("name") or "", room.get("desc") or "")).casefold()
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
                if barrier in _OPEN_TO_SOUND:
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
    falling = weather["precipitation"] != "none"
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
        "weather_visible": (falling or weather["sky"] == "storm")
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


# One drift window in this many turns a snowing storm electrical. Chosen so a
# passing squall almost never flashes and a long blizzard probably will once:
# rare enough to stay an event, common enough to be worth having built.
THUNDERSNOW_ODDS = 9


def has_lightning(weather):
    """Does this sky throw lightning? Storm alone is not enough.

    A snowing storm is ordinarily silent lightning-wise -- a reader watching
    bolts play over every whiteout is being told something false about the
    weather. Unless it is thundersnow, which is a real thing and worth having:
    rare, deliberate, and marked on the sky itself so that when it happens the
    whole beat knows, from the flash to the clap to what the room hears.
    """
    weather = weather if isinstance(weather, dict) else {}
    if weather.get("sky") != "storm":
        return False
    return (weather.get("precipitation") not in _UNLIT_PRECIPITATION
            or bool(weather.get("thundersnow")))


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
            words.append({"clear": "clear sky", "fair": "open sky",
                          "overcast": "overcast sky", "fog": "thick fog",
                          "storm": "storm sky"}[scoped["sky"]])
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

# What each sky can become. Deliberately gradual: clear does not become storm
# without passing through the states in between, which is what makes an
# unattended sky read as weather rather than as noise.
_SKY_NEXT = {
    "clear": ("clear", "clear", "fair"),
    "fair": ("fair", "fair", "clear", "overcast"),
    "overcast": ("overcast", "overcast", "fair", "storm", "fog"),
    "fog": ("fog", "fog", "overcast"),
    "storm": ("storm", "storm", "overcast"),
}

# What a sky is willing to drop, and how hard.
_SKY_FALL = {
    "clear": (("none", "none"),),
    "fair": (("none", "none"), ("none", "none"), ("drizzle", "light")),
    "overcast": (("none", "none"), ("drizzle", "light"), ("rain", "light"),
                 ("rain", "moderate")),
    "fog": (("none", "none"), ("drizzle", "light")),
    "storm": (("rain", "heavy"), ("rain", "heavy"), ("rain", "moderate"),
              ("hail", "moderate")),
}

_SKY_WIND = {
    "clear": ("still", "breeze"), "fair": ("still", "breeze"),
    "overcast": ("breeze", "wind"), "fog": ("still", "still"),
    "storm": ("wind", "gale"),
}


def _roll(seed, step, salt):
    """A stable pseudo-random integer for (seed, step, salt).

    Hashing rather than seeding an RNG because the value has to be the same in
    a fresh process, after a restart, and on a replayed turn -- `random` with a
    seed would be, but only if nothing else ever draws from it in between.
    """
    blob = "%s|%s|%s" % (seed, step, salt)
    return int(hashlib.sha256(blob.encode("utf-8")).hexdigest()[:8], 16)


def advance_weather(weather, elapsed_seconds, seed, cold=False, severity=None):
    """The sky after `elapsed_seconds`, drifted deterministically.

    `cold` swaps rain for snow, which is the one place temperature actually
    changes what falls rather than merely how it feels. Returns the input
    unchanged inside one drift window, so an ordinary conversational beat does
    not move the weather at all.

    `severity` is the story's authored ceiling (see `severity_intensity_cap`).
    A caller that does not know it passes nothing and gets an uncapped drift,
    because the calm ceiling is a choice a story made and not a default to
    fall back to.
    """
    weather = normalize_weather(weather) or dict(_DEFAULT)
    try:
        step = int(max(0.0, float(elapsed_seconds)) // DRIFT_SECONDS)
    except (TypeError, ValueError):
        return weather
    if step <= 0:
        return weather

    skies = _SKY_NEXT.get(weather["sky"], _SKY_NEXT["fair"])
    sky = skies[_roll(seed, step, "sky") % len(skies)]
    falls = _SKY_FALL.get(sky, _SKY_FALL["fair"])
    precipitation, intensity = falls[_roll(seed, step, "fall") % len(falls)]
    intensity = _capped_intensity(intensity, severity)
    if cold or weather["temperature"] == "freezing":
        precipitation = {"rain": "snow", "drizzle": "snow",
                         "hail": "sleet"}.get(precipitation, precipitation)
    winds = _SKY_WIND.get(sky, ("still", "breeze"))
    # Thundersnow, rolled rather than derived. Rare per window, so most
    # blizzards never flash -- but a long one might, and that is the point: it
    # should be something a reader gets to SEE happen rather than a constant.
    # Seeded like everything else here, so a reroll cannot conjure it and a
    # replay cannot lose it.
    thundersnow = (sky == "storm"
                   and precipitation in _UNLIT_PRECIPITATION
                   and _roll(seed, step, "thundersnow") % THUNDERSNOW_ODDS == 0)
    return normalize_weather({
        "sky": sky,
        "precipitation": precipitation,
        "intensity": intensity,
        "thundersnow": thundersnow,
        "wind": winds[_roll(seed, step, "wind") % len(winds)],
        # Temperature is authored, not drifted: a beat that says the night
        # turns bitter is the Director's to write, and guessing it here would
        # fight that.
        "temperature": weather["temperature"],
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
GROUND_LADDERS = {
    "wet": ("damp ground", "wet ground", "standing puddles", "churned mud"),
    "snow": ("a dusting of snow", "snow underfoot", "deep snow", "snowdrifts"),
    "slush": ("slush underfoot", "deep slush"),
    "hail": ("scattered hailstones",),
    "ice": ("frost underfoot", "sheet ice"),
}

# Which ladder a given precipitation lays down. Freezing turns the wet ladder
# into the ice one, which is the single most consequential thing temperature
# does to a floor.
_GROUND_KIND = {
    "rain": "wet", "drizzle": "wet", "snow": "snow", "sleet": "slush",
    "hail": "hail",
}

# How fast it piles up, per beat, by intensity.
_GROUND_GAIN = {"light": 1, "moderate": 2, "heavy": 3}
# ...and how fast it goes away once nothing is falling. Slower than it arrives:
# ground dries and snow lingers, and a puddle that vanished the moment the rain
# stopped would read as a bug.
_GROUND_DRAIN = 1
_GROUND_MAX = 12


def ground_kind(weather, ground=None):
    """Which ladder this sky is laying down, or the one already on the ground."""
    weather = normalize_weather(weather) or {}
    falling = weather.get("precipitation", "none")
    if falling != "none":
        kind = _GROUND_KIND.get(falling, "wet")
        if kind == "wet" and weather.get("temperature") == "freezing":
            return "ice"
        return kind
    return str((ground or {}).get("kind") or "wet")


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
            str(previous.get("kind") or "wet"), level))

    scoped = scoped or {}
    falling = scoped.get("precipitation", "none") != "none"
    # `falls_on_you` is the honest test: a porch is under the sky and still
    # dry underfoot, and its floor should stay that way.
    landing = bool(falling and exposed and scoped.get("falls_on_you"))
    kind = ground_kind(scoped, previous)
    if landing:
        level = min(_GROUND_MAX,
                    level + _GROUND_GAIN.get(scoped.get("intensity"), 1))
    else:
        level = max(0, level - _GROUND_DRAIN)
    if not level:
        return {}
    return {"kind": kind, "level": level, "state": _ground_state(kind, level)}


def _ground_state(kind, level):
    ladder = GROUND_LADDERS.get(kind) or GROUND_LADDERS["wet"]
    # Three beats of accumulation per rung, so a floor passes through its
    # states rather than jumping to the deepest one in a single downpour.
    rung = min(len(ladder) - 1, max(0, (level - 1) // 3))
    return ladder[rung]


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
