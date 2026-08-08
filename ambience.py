"""Room ambience: the sound of the place the player is standing in.

EXPERIMENTAL, and deliberately built as the audio twin of `backdrops.py` --
same shape, same three rules, same out-of-band execution. Nothing here is
reachable from the turn pipeline: a network fetch to a sound library must never
sit between the player and their prose.

The three rules carry over, with one deliberate difference each.

**1. The query is built from STRUCTURED spatial data.** The same whitelisted,
occupant-free room projection the picture path uses (`backdrops.room_projection`
is not reused directly because sound and sight want different fields, but the
whitelist discipline is identical). A soundscape is chosen from what the PLACE
is, never from who is in it or what they said.

**2. Ambience is the room's tone, not its population.** Backdrops depict the
room empty because a likeness is uncanny and a person in the picture is a leak.
The audio reason is different but lands in the same place: a crowd murmur that
appeared the moment a specific character walked in would report that character's
presence through a channel perception never authorized. So occupants are absent
by construction here too. A tavern sounds busy because `rooms[id].desc` says it
is a tavern, not because five entities are standing in it.

**3. A cache key is a room plus its AUDIBLE state** -- which is a different set
from its visible state, and the difference is the point. Weather changes what a
place sounds like; LIGHT DOES NOT. A room that goes dark is a completely new
picture and the identical soundscape, so `light` is excluded from the acoustic
signature where `backdrops.visual_signature` treats it as the largest term.
That exclusion is most of why ambience gets cache hits on beats where the
backdrop pays again.

Two sources, both optional, chosen per install:

  * `local` -- a folder of audio the host already owns, matched by filename.
    No network, no API key, no licence question; whatever quality the host's
    own library has.
  * `freesound` -- freesound.org's APIv2, the largest Creative Commons sound
    database with a public API. Previews stream without OAuth, so a token is
    enough. Licence-filtered to CC0 and Attribution by default, and the
    attribution for anything fetched is stored beside the audio so the UI can
    credit it (see README).

A host can also PIN a room's sound (`set_ambience_pin`), which replaces the
whole query/search path with an explicit choice. A pin is keyed by room id, not
by signature, so it survives weather and time changing under it -- "this room
sounds like this" is a statement about the room, not about one of its states.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re

import outofband
from backdrops import (_room_of_player, branch_lineage, place_desc,
                       scene_after_turn, time_bucket)
from db import get_setting, wget, wset
from weather import weather_for_room, weather_words

# Fetched audio lives beside the backdrop cache and for the same reason:
# engine.db is already large, and a few hundred ambience beds would dwarf it
# while dragging themselves through every backup and export.
AMBIENCE_DIR = os.environ.get(
    "FICTION_ENGINE_AMBIENCE_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "ambience"))

# The host's own audio. Never written to, never copied out of: a local library
# can be tens of gigabytes of purchased material, so the cache stores a POINTER
# to the chosen file rather than a duplicate of it.
DEFAULT_LIBRARY_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "ambience_library")

AUDIO_EXTENSIONS = (".mp3", ".ogg", ".oga", ".wav", ".flac", ".m4a", ".opus", ".webm")

_MEDIA_TYPES = {
    ".mp3": "audio/mpeg", ".ogg": "audio/ogg", ".oga": "audio/ogg",
    ".wav": "audio/wav", ".flac": "audio/flac", ".m4a": "audio/mp4",
    ".opus": "audio/ogg", ".webm": "audio/webm",
}

# What changes how a place SOUNDS. `light` is conspicuously absent -- see rule 3
# in the module docstring. Conditions and overlays stay because the things they
# carry (a fire, a hull breach, flooding, a storm) are all audible events.
# Weather is room-scoped rather than listed here, for the same reason it is in
# backdrops.py -- but note the audible reach is WIDER than the visible one: a
# cellar hears heavy rain it cannot see, so `weather_for_room` answers those
# two questions separately and this key changes on either.
_ACOUSTIC_STATE_KEYS = ("overlays", "conditions", "ground")

# Freesound's licence names, exactly as its filter expects them. NonCommercial
# is offered but off by default: a host who wants it can say so, and a host who
# does not should never have it arrive silently.
FREESOUND_LICENCES = ("Creative Commons 0", "Attribution", "Attribution NonCommercial")
DEFAULT_LICENCES = ("Creative Commons 0", "Attribution")

FREESOUND_SEARCH = "https://freesound.org/apiv2/search/text/"
# One sound, by its id. NOT the search endpoint with an `id:` term: Freesound's
# text search has no `id` field, so `id:341802` is tokenised as TEXT and
# happily returns a sound literally named "file_id.diz.mp3" -- the same wrong
# sound for every id ever asked for. See `freesound_sound`.
FREESOUND_SOUND = "https://freesound.org/apiv2/sounds/%s/"
_FREESOUND_FIELDS = ("id,name,tags,category,license,username,url,duration,"
                     "previews,avg_rating,num_ratings,num_downloads")

# A bed, not a bang. Below ~15s a clip loops audibly; above ten minutes the
# fetch stops being worth the wait for a file that plays under prose.
_MIN_SECONDS, _MAX_SECONDS = 15, 600

_REQUEST_TIMEOUT = 20


def media_type_for(path):
    return _MEDIA_TYPES.get(os.path.splitext(str(path or ""))[1].lower(),
                            "application/octet-stream")


# --- settings --------------------------------------------------------------

def ambience_settings():
    """Everything the feature is configured with, in one read.

    `configured` is the question the UI actually asks: not "is a key set" but
    "could this produce a sound at all", which for a local library means the
    folder exists and for freesound means a token is present.
    """
    source = (get_setting("ambience_source") or "local").strip() or "local"
    if source not in ("local", "freesound"):
        source = "local"
    library = (get_setting("ambience_library") or "").strip() or DEFAULT_LIBRARY_DIR
    key = (get_setting("freesound_key") or "").strip()
    try:
        licences = json.loads(get_setting("ambience_licenses") or "[]")
    except (ValueError, TypeError):
        licences = []
    licences = [lic for lic in licences if lic in FREESOUND_LICENCES] or list(DEFAULT_LICENCES)
    return {
        "enabled": get_setting("ambience_enabled") == "1",
        "source": source,
        "library": library,
        "has_key": bool(key),
        "key": key,
        "licenses": licences,
        "configured": bool(key) if source == "freesound" else os.path.isdir(library),
    }


# --- pins ------------------------------------------------------------------
#
# A host override, per chat, per room. Stored as an ordinary (frame-unscoped)
# world key so branching and portable archives carry it with no extra work:
# `chat_archive` exports the whole `world` table, and a pin that did not travel
# with a branch would silently revert a room the host had already fixed.

def ambience_pins(chat_id):
    pins = wget(chat_id, "ambience_pins", {}) or {}
    return pins if isinstance(pins, dict) else {}


def ambience_pin_for(chat_id, room_id):
    if not room_id:
        return None
    pin = ambience_pins(chat_id).get(str(room_id))
    if not isinstance(pin, dict):
        return None
    # Either shape counts: a single sound (what the first version wrote, still
    # in live saves) or a whole mix.
    return pin if pin.get("source") or pin.get("layers") else None


def _normalize_choice(choice, role="tone", gain=1.0):
    """One pinned sound, normalized rather than trusted: this value decides
    which bytes a later request serves, and `local` becomes a filesystem
    path."""
    source = str((choice or {}).get("source") or "").strip()
    if source not in ("local", "freesound"):
        raise ValueError("source must be 'local' or 'freesound'")
    out = {
        "source": source,
        "title": str((choice or {}).get("title") or "").strip(),
        "role": str((choice or {}).get("role") or role),
        "gain": max(0.0, min(1.0, float((choice or {}).get("gain", gain) or 0))),
    }
    if source == "local":
        rel = _safe_relative(str((choice or {}).get("path") or ""))
        if not rel:
            raise ValueError("a local pin needs a path inside the library")
        out["path"] = rel
    else:
        try:
            out["id"] = int((choice or {}).get("id"))
        except (TypeError, ValueError):
            raise ValueError("a freesound pin needs a numeric sound id")
        for field in ("preview", "license", "username", "url"):
            value = str((choice or {}).get(field) or "").strip()
            if value:
                out[field] = value
    return out


def set_ambience_pin(chat_id, room_id, choice):
    """Fix one room's sound to an explicit choice, or to a whole mix.

    A mix is `{"layers": [choice, ...]}`, each carrying its own gain -- which
    is what makes "this hall is a room tone at full, a fountain at a third"
    something a host can state and keep.
    """
    if isinstance((choice or {}).get("layers"), list):
        layers = [_normalize_choice(item, role=("tone" if i == 0 else "extra"))
                  for i, item in enumerate(choice["layers"][:MAX_LAYERS])]
        if not layers:
            raise ValueError("a pinned mix needs at least one layer")
        pin = {"layers": layers}
    else:
        pin = _normalize_choice(choice)
    pins = ambience_pins(chat_id)
    pins[str(room_id)] = pin
    wset(chat_id, "ambience_pins", pins)
    return pin


def clear_ambience_pin(chat_id, room_id):
    pins = ambience_pins(chat_id)
    if str(room_id) in pins:
        pins.pop(str(room_id), None)
        wset(chat_id, "ambience_pins", pins)
        return True
    return False


# --- cache keying ----------------------------------------------------------

def _anchor_words(room):
    """A room's named fixtures, as plain strings.

    `RoomDef.anchors` is `{anchor_id: {desc, dir?}}` naming the fixed features
    of a place -- a hearth, a fountain, a bank of consoles (see the note above
    `anchor_desc` in `spatial.py`). They are FURNITURE, never occupants, so
    they carry no more information than the description already does and belong
    in the same occupant-free projection.

    They are also, very often, the only thing in a room that actually makes a
    noise. Live failure, "The Blizzard": the Waystation Main Hall had
    `fireplace: "crackling stone hearth"` sitting in the scene and unread, while
    the query built from the room's prose ("waystation main hall warm modest
    lit") described the light and the mood -- neither of which a microphone can
    hear -- and the search settled on a recording of a cave.
    """
    out = []
    for key, anchor in ((room or {}).get("anchors") or {}).items():
        desc = str((anchor or {}).get("desc") or "").strip() if isinstance(anchor, dict) else ""
        word = desc or str(key or "").replace("_", " ").strip()
        if word:
            out.append(word)
    return out


def acoustic_fingerprint(scene, room_id, style=None):
    """What this room sounds like, reduced to the TERMS a search would use.

    Deliberately coarser than the room's own data. The key has to be a function
    of what the engine would go LOOKING for, not of the prose it was written
    from: a description reworded without changing a material, a style guide
    edited anywhere but its genre, an overlay rephrased -- none of those change
    what the place sounds like, and each of them used to buy a fresh model call
    and a fresh download for the identical bed.

    Order is discarded too (the terms are sorted), so a sentence rearranged is
    the same room. What survives is what a microphone would notice: materials,
    the hour, the sky, and whatever has happened to the place.
    """
    scene = scene or {}
    room = ((scene.get("rooms") or {}).get(room_id) or {})
    state = []
    for key in _ACOUSTIC_STATE_KEYS:
        value = scene.get(key)
        if isinstance(value, dict):
            value = value.get(room_id)
        if value:
            state.append(value if isinstance(value, str)
                         else json.dumps(value, sort_keys=True, ensure_ascii=False))
    return {
        "room": room_id,
        "name": sorted(_keywords(room.get("name"), 4)),
        # The people-stripped description, for the same reason backdrops hashes
        # the projected text: a room must not pay for a re-fetch because
        # someone was written into a sentence the query never sees.
        "desc": sorted(_keywords(place_desc(room), 8)),
        # The fixtures, which are what a room is usually heard through. A
        # hearth lit or gone cold is the sound of the place changing, and
        # without this the key could not tell those two rooms apart.
        "anchors": sorted(_keywords(" ".join(_anchor_words(room)), 6)),
        "time": time_bucket(scene.get("time")),
        # The words, not the dict -- same reason as backdrops, with the
        # audible/visible split doing the work: an enclosed room's key moves
        # for rain it can hear and not for a sky it cannot see.
        "weather": weather_words(weather_for_room(scene, room_id), "sound"),
        # Only the genre reaches `compose_query`; the rest of a style guide is
        # about prose, and prose has no sound.
        "genre": sorted(_keywords((style or {}).get("genre"), 2)),
        "state": sorted(_keywords(" ".join(state), 6)),
    }


# How alike two fingerprints have to be for one room's already-resolved bed to
# answer for the other. Both sides are always the SAME ROOM under the same sky
# at the same hour, so this only has to separate "something happened in here"
# from "this is a different place" -- and half the terms in common is a long way
# past that. Calibrated against a real run: one bedroom's candle burning down
# rewrote its description from "a dying candle, the window open" to "the candle
# has burned lower", scoring 0.54. Nothing in that is audible, and at 0.6 it
# bought a fresh model call and a fresh download.
_REUSE_SIMILARITY = 0.5

# What must be identical regardless of similarity -- these are not detail, they
# are the sound changing. Rain starting, night falling, or the hearth a room is
# heard through going cold is a new bed. Fixtures sit here rather than in the
# graded half because the graded half cannot see them: a hall whose fire has
# died has the same name, the same description and the same materials, and
# scored 0.78 against its burning self -- comfortably inside the reuse
# threshold, which would have kept the fire playing in a cold room.
_REUSE_EXACT = ("room", "time", "weather", "anchors")


def fingerprint_similarity(a, b):
    """0..1 over the parts of two fingerprints that are a matter of degree.

    Returns 0 outright when anything in `_REUSE_EXACT` differs, so a threshold
    can never be talked into playing a dry room under a downpour.
    """
    a, b = a or {}, b or {}
    if not a or not b:
        return 0.0
    for key in _REUSE_EXACT:
        left, right = a.get(key), b.get(key)
        # An hour nobody recorded is not evidence of a DIFFERENT hour. Scenes
        # lose their clock routinely, and treating that as nightfall re-fetched
        # a room three times in one measured run.
        if key == "time" and not (left and right):
            continue
        # A fingerprint written before fixtures were keyed has no `anchors`
        # entry at all. Read as "this room has no fixtures" that would discard
        # every cached bed in every install at once, so an absent entry and an
        # empty one are the same thing -- and ONLY where the room really has
        # none. A bed chosen before the hearth was legible was chosen without
        # it, and adopting that one would carry the old pick straight past the
        # change that made the hearth searchable.
        if key == "anchors":
            left, right = left or [], right or []
        if left != right:
            return 0.0
    left, right = set(), set()
    for key in ("name", "desc", "genre", "state"):
        left |= {"%s:%s" % (key, term) for term in (a.get(key) or [])}
        right |= {"%s:%s" % (key, term) for term in (b.get(key) or [])}
    if not left and not right:
        return 1.0
    return len(left & right) / float(len(left | right))


def acoustic_signature(scene, room_id, style=None, pin=None):
    """A stable hash of everything that changes how `room_id` SOUNDS.

    A pinned room collapses to the pin itself: the host has said what this
    place sounds like, so weather and hour must not send the engine looking for
    something else, and two rooms pinned to the same file share one cache
    entry.
    """
    if pin:
        blob = json.dumps({"pin": pin}, sort_keys=True, ensure_ascii=False)
        return "pin" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:21]
    blob = json.dumps(acoustic_fingerprint(scene, room_id, style),
                      sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]


def manifest_path(chat_id, signature):
    return os.path.join(AMBIENCE_DIR, str(chat_id), "%s.json" % signature)


def audio_path(chat_id, signature, ext=".mp3"):
    return os.path.join(AMBIENCE_DIR, str(chat_id), "%s%s" % (signature, ext))


def _safe_relative(rel):
    """A library-relative path with traversal removed, or ''.

    Every path that reaches the filesystem passes through here: a pin is host
    input and the library root is a real directory, so `../../engine.db` has to
    be unrepresentable rather than merely discouraged.
    """
    rel = str(rel or "").strip().replace("\\", "/").lstrip("/")
    if not rel:
        return ""
    parts = [p for p in rel.split("/") if p not in ("", ".", "..")]
    if not parts:
        return ""
    joined = "/".join(parts)
    if os.path.splitext(joined)[1].lower() not in AUDIO_EXTENSIONS:
        return ""
    return joined


def resolve_local(rel, library=None):
    """An absolute path to a library file, or None if it escapes the root.

    The realpath check is the actual guard -- `_safe_relative` removes the
    obvious traversal, this one also catches a symlink pointing out of the
    library.
    """
    library = library or ambience_settings()["library"]
    rel = _safe_relative(rel)
    if not rel or not library:
        return None
    root = os.path.realpath(library)
    full = os.path.realpath(os.path.join(root, rel))
    if full != root and not full.startswith(root + os.sep):
        return None
    return full if os.path.isfile(full) else None


# --- layers ----------------------------------------------------------------
#
# A room is rarely one sound. A courtyard in the rain is stone-and-city under
# rain-on-flagstones; a tavern is a room tone under a murmur. Resolving one
# clip per room forces a library to have the exact combination already mixed,
# which no library does -- so the engine mixes them itself, and each layer
# keeps its own level.
#
# Three roles, in the order they are laid down. `tone` is the room itself and
# is always present; `weather` carries the sky's own attenuation (a downpour
# two rooms in is a quiet layer over an undiminished room tone, which is
# exactly right and is impossible to express with one clip); `extra` is
# whatever else the query stage thought the place had.
#
# WEATHER IS ONLY WEATHER. Not thunder (the engine draws the flash and times
# the clap from it -- see role_veto), and not wildlife. Field recordings of
# rain are very often rain AND something alive, and taking one wholesale puts
# a dawn chorus in a midday market and welds it to the sky's own gain, which is
# derived from how deep the room is. Birds belong to the PLACE: they are an
# `extra`, on their own level, and they carry on when the rain stops.
LAYER_ROLES = ("tone", "weather", "extra")

# Ceiling on simultaneous beds. Three is already busy; past that the layers
# stop being a place and start being a noise floor, and every one is another
# fetch and another decoder.
MAX_LAYERS = 3


def _as_layered(manifest):
    """Any manifest, old or new, as {'layers': [...]}.

    Single-track manifests were written before layering existed and are still
    on disk in every install that ran the first version -- and in every branch
    ancestor's directory, which is read in place and never rewritten. They
    become a one-layer mix rather than a migration.
    """
    manifest = dict(manifest or {})
    layers = manifest.get("layers")
    if isinstance(layers, list) and layers:
        manifest["layers"] = [dict(layer) for layer in layers
                              if isinstance(layer, dict)][:MAX_LAYERS]
        for layer in manifest["layers"]:
            layer.setdefault("gain", 1.0)
            layer.setdefault("role", "tone")
        return manifest
    single = {k: manifest[k] for k in
              ("source", "path", "file", "title", "license", "username", "url",
               "query", "id")
              if k in manifest}
    single.setdefault("gain", 1.0)
    single.setdefault("role", "tone")
    manifest["layers"] = [single] if single.get("source") else []
    return manifest


def cached_ambience(chat_id, signature):
    """The manifest for an already-resolved soundscape, or None.

    Own directory first, then the branch lineage -- read in place, never copied
    forward, exactly as backdrops does with images. A local pick resolves
    through the library each time rather than being copied into the cache: the
    host's own files stay the host's, and a 40MB field recording is not
    duplicated per chat.
    """
    for cid in [chat_id] + branch_lineage(chat_id):
        path = manifest_path(cid, signature)
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                manifest = json.load(fh)
        except (ValueError, OSError):
            continue
        if not isinstance(manifest, dict):
            continue
        manifest = _as_layered(manifest)
        if manifest.get("silent"):
            # A room judged to have no continuous sound. Resolved, cached and
            # complete -- with nothing to play, which is why it returns HERE,
            # before the loop that discards a manifest with no playable layer.
            manifest["layers"] = []
            manifest["signature"] = signature
            manifest["rev"] = len(manifest.get("rejected") or [])
            return manifest
        resolved_layers = []
        for layer in manifest["layers"]:
            if layer.get("source") == "local":
                resolved = resolve_local(layer.get("path"))
                if not resolved:
                    # The host moved or deleted the file. Not an error worth
                    # keeping: drop the layer so the next request picks again.
                    continue
                layer["file_path"] = resolved
            else:
                audio = os.path.join(os.path.dirname(path), layer.get("file") or "")
                if not os.path.isfile(audio):
                    continue
                layer["file_path"] = audio
            resolved_layers.append(layer)
        if not resolved_layers:
            continue
        manifest["layers"] = resolved_layers
        # The first layer doubles as the manifest's own track for every caller
        # written before layering existed.
        manifest.update({k: v for k, v in resolved_layers[0].items()
                         if k in ("file_path", "title", "source", "license",
                                  "username", "url")})
        manifest["signature"] = signature
        # How many times this signature has been rerolled. The audio URL is
        # served immutable and content-addressed by signature -- which a reroll
        # would quietly violate, since the same signature now points at
        # different bytes. Carrying the revision into the URL keeps both true:
        # a rerolled bed is a new URL, and every URL is still permanently
        # cacheable.
        manifest["rev"] = len(manifest.get("rejected") or [])
        return manifest
    return None


# --- the query -------------------------------------------------------------

# Words that carry no acoustic information. Deliberately small: this trims a
# room description down to search terms, and over-trimming costs a worse match
# while under-trimming costs nothing much, since relevance ranking does the
# rest.
_STOPWORDS = frozenset("""
a an the and or but of in on at to from with without for by is are was were be
been being this that these those it its into over under above below near around
here there where when while as if then than so such very more most some any all
one two three you your they their he she his her them we our us i me my
has have had did does not now just only
""".split())
# The last line is auxiliary verbs and filler. They arrive with a description
# being REWRITTEN rather than changed -- "the candle has burned lower" -- and
# both the search and the cache key are better off never seeing them.

# Fields describing the PLACE, whitelisted like the backdrop projection. No
# entities, no positions, no attire, no dialogue -- a soundscape built from a
# projection with no concept of occupants cannot report one.
_PLACE_FIELDS = ("name", "desc")


def room_soundscape(scene, room_id):
    """A whitelisted, occupant-free description of what one room sounds like."""
    scene = scene or {}
    room = ((scene.get("rooms") or {}).get(room_id) or {})
    out = {k: room.get(k) for k in _PLACE_FIELDS if room.get(k)}
    if out.get("desc"):
        out["desc"] = place_desc(room)
        if not out["desc"]:
            out.pop("desc")
    out["room"] = room_id
    # The room's fixed features -- see `_anchor_words`. A place is far more
    # often heard through what is IN it (a hearth, a fountain, a generator)
    # than through the adjectives its description spends on light and mood.
    anchors = _anchor_words(room)
    if anchors:
        out["anchors"] = anchors
    bucket = time_bucket(scene.get("time"))
    if bucket:
        out["time"] = bucket
    # Only what this room can hear of the sky. The reach is deliberately wider
    # than sight's: rain on a roof is the most recognisable indoor ambience
    # there is, and a cellar that ignored a downpour would sound wrong.
    words = weather_words(weather_for_room(scene, room_id), "sound")
    if words:
        out["weather"] = words
    overlay = (scene.get("overlays") or {}).get(room_id)
    if overlay:
        out["overlays"] = overlay
    # What the weather has left underfoot. A yard that has turned to mud is a
    # different sound as well as a different picture, and the ladder drops it
    # first if no library has rain on mud.
    ground = ((scene.get("ground") or {}).get(room_id) or {}).get("state")
    if ground:
        out["ground"] = ground
    # Whether the room opens onto anywhere is audible in a way its exits'
    # bearings are not: an enclosed cell and a room open to a street are
    # different recordings. Only the count and the barrier kinds, never a
    # destination.
    barriers = sorted({str(edge.get("barrier") or "open")
                       for edge in (room.get("adjacent") or [])
                       if isinstance(edge, dict)})
    if barriers:
        out["openings"] = barriers
    return out


def _keywords(text, limit=5):
    words = [w for w in re.findall(r"[a-z][a-z'-]{2,}", str(text or "").casefold())
             if w not in _STOPWORDS]
    seen, out = set(), []
    for word in words:
        if word not in seen:
            seen.add(word)
            out.append(word)
        if len(out) >= limit:
            break
    return out


def compose_query(place, style=None):
    """A deterministic search query from the whitelisted place projection.

    Used as-is when no `ambience_prompt` model is configured, and as the draft
    handed to that agent when one is. Deterministic on purpose: the feature has
    to work, and be testable, with no extra model call at all.
    """
    terms = []
    terms.extend(_keywords(place.get("name"), 3))
    # Weather BEFORE the description, and ahead of the term cap: heavy rain IS
    # the sound of a place while it lasts, whereas the third adjective in a
    # room description is a detail. Ordered the other way round, "rain" fell
    # off the end of the query for a courtyard in a downpour.
    if place.get("weather"):
        terms.extend(_keywords(" ".join(str(w) for w in place["weather"]), 3))
    # Fixtures before the description, and for the same reason weather comes
    # before it: a hearth is a SOUND, whereas "warm, modest, lit by a few oil
    # lanterns" is three things a microphone cannot hear. Ordered the other way
    # round, the hall's hearth fell off the end of the query and the search
    # answered its remaining words -- stone -- with a cave.
    if place.get("anchors"):
        terms.extend(_keywords(" ".join(str(a) for a in place["anchors"]), 3))
    terms.extend(_keywords(place.get("desc"), 4))
    if place.get("overlays"):
        terms.extend(_keywords(" ".join(str(o) for o in place["overlays"]), 2))
    if place.get("ground"):
        terms.extend(_keywords(place["ground"], 2))
    if place.get("time") in ("night", "evening"):
        terms.append(place["time"])
    for key in ("genre",):
        if (style or {}).get(key):
            terms.extend(_keywords(style[key], 1))
    seen, out = set(), []
    for term in terms:
        if term not in seen:
            seen.add(term)
            out.append(term)
    # "ambience" and "room tone" are what the recordings on the other end are
    # actually tagged with; without them a query for "kitchen" returns knives
    # and cupboard doors rather than the sound of a kitchen.
    out.append("ambience")
    return " ".join(out[:9])


# What rain SOUNDS LIKE is mostly what it is landing on: the same downpour is
# a roar on a tin roof, a hiss on grass, a clatter on cobbles and almost
# nothing on soft ground. The room already says which, in the same whitelisted
# projection the tone layer reads -- so the weather layer can ask for rain ON
# something rather than rain in the abstract. First match wins, most acoustically
# distinctive first: a tin roof over a stone yard is a tin roof.
_RAIN_SURFACES = (
    ("tin roof", ("tin", "corrugated", "sheet metal", "metal roof")),
    ("canvas awning", ("awning", "canopy", "tarp", "canvas", "marquee", "tent")),
    ("window", ("window", "glass", "pane", "casement", "skylight")),
    ("leaves", ("leaves", "foliage", "forest", "woodland", "trees", "jungle",
                "undergrowth")),
    ("roof tiles", ("roof", "eaves", "gutter", "shingle", "thatch")),
    ("cobblestones", ("cobble", "flagstone", "paving", "pavement", "courtyard",
                      "street", "lane")),
    ("stone", ("stone", "slate", "granite", "marble", "brick")),
    ("water", ("river", "lake", "pond", "canal", "harbour", "harbor", "sea",
               "water")),
    ("grass", ("grass", "meadow", "field", "lawn", "earth", "mud")),
    ("wood", ("wooden", "timber", "planks", "deck", "boards")),
)


def rain_surface(place):
    """The surface this room's rain falls on, as a search term, or ''.

    Read from the room's own words, never invented: a room that says nothing
    about what it is made of gets plain rain, which is the honest answer.
    """
    haystack = "%s %s" % (str((place or {}).get("name") or ""),
                          str((place or {}).get("desc") or ""))
    haystack = haystack.casefold()
    if not haystack.strip():
        return ""
    for surface, cues in _RAIN_SURFACES:
        if any(_cue_present(haystack, cue) for cue in cues):
            return surface
    return ""


# Whole words only, and not the ones a room says it does NOT have. Both of
# these were live errors on the first draft: "hosting dozens of market stalls"
# matched `tin` and roofed an open square in corrugated iron, and "bare stone,
# no windows" matched `window` and put rain on the glass of a cellar.
_CUE_NEGATIONS = ("no", "not", "without", "never", "nothing", "neither")


def _cue_present(haystack, cue):
    # Plural too: rooms are described in the plural constantly ("overhanging
    # awnings", "wooden planks"), and a cue that only matched the singular sent
    # a lane under awnings to rain-on-cobblestones instead.
    for match in re.finditer(r"\b%ss?\b" % re.escape(cue), haystack):
        before = haystack[max(0, match.start() - 24):match.start()]
        if not any(word in before.split()[-2:] for word in _CUE_NEGATIONS):
            return True
    return False


def compose_layers(place, style=None, weather=None):
    """The deterministic layer plan for one room: 1-3 {role, query, gain}.

    Weather is its OWN layer rather than words folded into the room's query,
    and that is the whole reason layering earns its keep here: a downpour heard
    two rooms in is a QUIET rain layer over an UNDIMINISHED room tone. Mixing
    that into one clip would either drop the room or drown it.
    """
    tone = dict(place)
    tone.pop("weather", None)          # the tone layer is the room without its sky
    layers = [{"role": "tone", "query": compose_query(tone, style), "gain": 1.0}]
    if place.get("weather"):
        words = [str(w) for w in place["weather"]]
        # The surface goes LAST of the meaningful terms on purpose: the ladder
        # broadens from the end, so a library with no rain-on-cobblestones
        # falls back to plain rain of the right intensity rather than to
        # nothing. It is a refinement, never a requirement.
        surface = rain_surface(place)
        if surface:
            words.append(surface)
        layers.append({
            "role": "weather",
            "query": " ".join(words) + " ambience loop",
            # How much of the sky reaches this room, straight from weather.py.
            "gain": float((weather or {}).get("gain") or 1.0),
        })
    return layers[:MAX_LAYERS]


def refine_layers(layers, place):
    """Optionally rewrite the deterministic layer plan with the
    `ambience_prompt` model, which may also ADD one layer -- or answer that
    this room should make no sound at all.

    Returns `(plan, verdict)`. `verdict` is `{}` for an ordinary room and
    `{"silent": True, "reason": ...}` when the model judged that the place has
    no continuous sound: a sealed vault, a vacuum, a dead cellar in still air.
    The job is ambience TRUE TO THE ROOM, not ambience at all costs -- a bed
    laid under a room that has none is an invention, and a feature that always
    finds something is a feature that lies about quiet places.

    Silence is deliberately an EXPLICIT flag rather than an empty `layers`
    list: an empty list is what a confused answer looks like, and the two must
    not be the same gesture.

    Returns the input unchanged if no model is configured or the call fails --
    a nicety, never a dependency. The model may not change a layer's gain, and
    may not silence the WEATHER: both are facts the engine derived from the
    room graph, and a language model has no standing to overrule them. A silent
    verdict on a room with rain overhead therefore keeps the rain and drops
    only the room's own tone.
    """
    try:
        from providers import resolve_role_candidates
        resolve_role_candidates("ambience_prompt")
    except Exception:
        return layers, {}
    try:
        from agents.common import _agent_json
        from prompts import get_prompt
        out = _agent_json("ambience_prompt", "ambience_prompt",
                          get_prompt("ambience_prompt"),
                          {"place": place, "layers": layers}, temperature=0.4)
        # What must not be in this room's bed, in the model's words. Written by
        # the prompt since the first version and, until now, read by nobody.
        avoid = str((out or {}).get("avoid") or "").strip()
        if (out or {}).get("silent"):
            return ([dict(layer) for layer in layers
                     if layer.get("role") == "weather"],
                    {"silent": True, "avoid": avoid,
                     "reason": str((out or {}).get("reason") or "").strip()})
        written = (out or {}).get("layers")
        if not isinstance(written, list) or not written:
            # Older prompt shape: a single query string.
            query = str((out or {}).get("query") or "").strip()
            if query and layers:
                layers = [dict(layers[0], query=_anchored(query))] + layers[1:]
            return layers, {"avoid": avoid}
        by_role = {layer["role"]: layer for layer in layers}
        rebuilt = []
        for item in written[:MAX_LAYERS]:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "extra")
            role = role if role in LAYER_ROLES else "extra"
            query = str(item.get("query") or "").strip()
            if not query:
                continue
            original = by_role.get(role) or {}
            if role == "weather" and original.get("query"):
                # The WEATHER layer's words are not the model's to rewrite, for
                # the same reason its gain is not: what is falling, and how
                # hard, is a fact the engine derived from the scene. Measured
                # cost of allowing it -- the draft "rain light ambience loop"
                # came back as "gentle light rain ground loop", the ladder
                # broadened it from the end to "gentle light loop", and a
                # rainstorm got a corporate music track called "Wide Flower
                # Fields". The one word that could not be dropped was third.
                query = original["query"]
            rebuilt.append({
                # Anchored here, not merely asked for in the prompt: an
                # unanchored query is how a bathroom gets falling roof tiles.
                "role": role, "query": _anchored(query),
                # The model's gain is accepted for a layer it invented and
                # ignored for one whose level the engine derived.
                "gain": float(original.get("gain")) if original.get("gain") is not None
                else max(0.05, min(1.0, float(item.get("gain") or 0.6))),
            })
        return (rebuilt or layers), {"avoid": avoid}
    except Exception:
        return layers, {}


def refine_query(draft, place):
    """Optionally rewrite the deterministic draft with the `ambience_prompt`
    model. Returns the draft unchanged if no model is configured or the call
    fails -- a nicety, never a dependency.

    This is where a fictional referent becomes an acoustic description: a model
    asked for "the bridge of a starship" returns hum, air handling and sparse
    console tones, which a sound library can actually match. Searching the
    proper noun matches nothing.
    """
    try:
        from providers import resolve_role_candidates
        resolve_role_candidates("ambience_prompt")
    except Exception:
        return {"query": draft, "avoid": ""}
    try:
        from agents.common import _agent_json
        from prompts import get_prompt
        out = _agent_json("ambience_prompt", "ambience_prompt",
                          get_prompt("ambience_prompt"),
                          {"place": place, "draft": draft}, temperature=0.4)
        query = str((out or {}).get("query") or "").strip()
        return {"query": query or draft,
                "avoid": str((out or {}).get("avoid") or "").strip()}
    except Exception:
        return {"query": draft, "avoid": ""}


# --- sources ---------------------------------------------------------------

def library_files(library=None, limit=2000):
    """Every audio file in the local library, as library-relative paths."""
    library = library or ambience_settings()["library"]
    if not library or not os.path.isdir(library):
        return []
    out = []
    root = os.path.realpath(library)
    for base, _dirs, files in os.walk(root):
        for name in sorted(files):
            if os.path.splitext(name)[1].lower() not in AUDIO_EXTENSIONS:
                continue
            rel = os.path.relpath(os.path.join(base, name), root).replace(os.sep, "/")
            out.append(rel)
            if len(out) >= limit:
                return sorted(out)
    return sorted(out)


def search_local(query, library=None, limit=8, avoid="", rank_query=""):
    """Rank library files against a query by filename token overlap.

    Deliberately dumb and deterministic: no index to rebuild, no embedding to
    recompute when the host drops a new folder in. A host who wants better
    matching renames files or drops an `index.json` beside them mapping a
    relative path to extra tags.
    """
    library = library or ambience_settings()["library"]
    files = library_files(library)
    if not files:
        return []
    tags = {}
    index = os.path.join(library, "index.json") if library else ""
    if index and os.path.isfile(index):
        try:
            with open(index, "r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                tags = {str(k).replace("\\", "/"): str(v) for k, v in loaded.items()}
        except (ValueError, OSError):
            tags = {}
    wanted = set(_keywords(query, 12))
    # The standard the results are judged against, when it differs from the
    # words used to find them -- see `search_freesound`.
    standard = set(_keywords(rank_query, 12)) if rank_query else wanted
    # What the model asked not to hear in this room, applied here as a hard
    # exclusion: a local library is small enough that a vetoed file is a file
    # the host would rather have silence than.
    unwanted = set(_keywords(avoid, 200))
    scored = []
    for rel in files:
        haystack = set(_keywords(rel.replace("/", " ").replace("_", " ")
                                 .replace("-", " ") + " " + tags.get(rel, ""), 24))
        if unwanted & haystack:
            continue
        hits = len(wanted & haystack)
        if hits:
            # Shorter names win ties: "rain.wav" is a better answer to "rain"
            # than "rain_on_a_car_roof_take_3.wav", which is a more specific
            # recording that a more specific query should be finding.
            scored.append((hits, -len(rel), rel, len(standard & haystack)))
    scored.sort(reverse=True)
    return [{"source": "local", "path": rel, "title": rel, "score": hits,
             # Same meaning as the Freesound ranker's: how much of the ROOM
             # this file actually answers, for a caller deciding whether the
             # best match is good enough to lay under it.
             "fit": fit,
             # And how much of what was ASKED FOR, which here is what the file
             # was matched on in the first place -- nothing with a zero reaches
             # this list. Carried so a caller can apply one rule to both
             # sources rather than knowing which one it is talking to.
             "intent": hits}
            for hits, _len, rel, fit in scored[:limit]]


# Freesound ANDs the words of a query: every term has to appear on the sound,
# so an eight-word acoustic description matches nothing whatsoever. Measured
# against the live API, EVERY room query this module composes returned zero
# results -- "stone tile small room open reverb quiet ambience" finds nothing,
# while "stone tile small room ambience" finds beds. Without broadening, the
# Freesound source cannot play a sound at all. Joining terms with OR is not the
# escape hatch it looks like: bare terms joined that way score zero too.
_QUERY_ANCHORS = ("ambience", "loop", "tone")

# Words that mark a recording as an EVENT rather than a bed. A bath scene was
# given a well-rated recording of falling roof tiles, because "stone tile"
# matched it and nothing downstream cared what KIND of sound it was. These do
# not disqualify a candidate outright -- a room tone can legitimately be named
# "door closed, distant traffic" -- but they push it below anything continuous.
# Uploaders say so when they have prepared a bed to loop -- trimmed at the zero
# crossings, no fade at either end. Freesound exposes no loopability descriptor
# (its `ac_loop` filter field is undefined on the search server), so the tag is
# the only signal there is. A preference, never a filter: there are far too few
# to search inside.
_LOOP_WORDS = frozenset("loop loops loopable looping looped seamless".split())

# Music is never the sky. A ROOM may legitimately have music in it -- a tavern
# band, a radio left on, a music box -- so this is not a global exclusion and
# the tone layer is free to find one. It is scoped to the WEATHER layer, where
# a melody is not a mediocre answer but a wrong one: rain does not play in a
# key. Unlike everything else here it is a hard filter rather than a ranking
# penalty, and no "something is better than nothing" fallback relaxes it -- a
# room with no rain layer is right, and a room whose rain is a guitar is not.
_MUSIC_WORDS = ("music musical song songs melody melodic tune tunes "
                "instrumental soundtrack orchestra orchestral symphony choir "
                "guitar piano violin cello flute harp drum drums percussion "
                "synth synthesizer techno beat beats rhythm chord chords riff "
                # What library music is actually tagged with. The recording
                # that put flower fields under a rainstorm was tagged
                # "ambient, atmospheric, background, calm, cheerful" and named
                # "Gentle Corporate - Inspirational Background": not one
                # instrument, not the word music, and unmistakably music.
                "corporate inspirational uplifting motivational cinematic "
                "royalty jingle bgm")

_MUSIC_TERMS = frozenset(_MUSIC_WORDS.split())

# Freesound's own taxonomy, which is far better evidence than a tag: those
# tracks are all `category: "Music"`. Requested as a field and, where a layer
# may not have music at all, excluded server-side so they are never fetched.
_MUSIC_CATEGORY = "Music"

# Thunder is not the weather layer's to play. The engine draws the flash and
# then schedules the clap from it, by a delay standing in for distance -- that
# gap is the whole reason the effect reads as a storm. A bed with thunder baked
# in claps on its own schedule, so the sky flashes in one place and rumbles in
# another, twice over. Vetoed here so the bed stays rain and the storm stays
# ours. (The current story's bed was literally "Rain&ThunderLoop1Light.wav".)
_THUNDER_WORDS = ("thunder thunderclap thunderclaps thunderstorm thunders "
                  "thundering lightning")

# Nor is wildlife the sky's. Field recordings of rain are very often rain AND
# something alive -- "Birds_at_Dawn_light_Rain", "Roosters_and_light_rain",
# "Frog croaking in the rain" -- and every one of those puts a dawn chorus into
# a market at midday, or a frog under an awning. They are legitimate ROOM tones
# and never a weather layer, which is why this veto is scoped to the role
# rather than applied to the whole search.
_FAUNA_WORDS = ("birds bird birdsong rooster roosters chicken chickens "
                "frog frogs crickets cricket insects seagull seagulls gulls "
                "dog dogs cat cats owl owls")

_ROLE_VETO = {
    "weather": " ".join((_MUSIC_WORDS, _THUNDER_WORDS, _FAUNA_WORDS)),
}


def role_veto(role):
    """What a layer may never be, whatever words the model chose for it."""
    return _ROLE_VETO.get(role or "", "")


_EVENT_WORDS = frozenset("""
drop dropping drops hit hits impact impacts crash crashing slam slamming
smash break breaking bang knock knocking footsteps foley sfx one-shot oneshot
scream shout speech dialogue voice voices
""".split())
# Musical words used to live in that list too, which double-counted them once
# music became a rule of its own -- and quietly penalised a tavern that had
# actually asked for a band. Each list means one thing now.


def _anchored(query):
    """A query guaranteed to ask for a BED.

    `compose_query` always ends on "ambience"; the model rewriting it does not
    reliably keep one, and an unanchored query is how a bathroom ends up with
    falling roof tiles -- "stone tile" matches that recording perfectly well.
    The anchor is what the continuous recordings are tagged with, so it is
    appended here rather than merely asked for in the prompt.
    """
    terms = str(query or "").split()
    if any(term.casefold() in _QUERY_ANCHORS for term in terms):
        return " ".join(terms)
    return " ".join(terms + ["ambience"])


# The crowd's opinion, weighted by how much crowd there was. Freesound's own
# `sort=rating_desc` is a trap for this: five stars from one rater outranks 4.5
# from six thousand, and the library is full of the former. So the raw average
# is pulled toward the mean by a handful of imaginary middling votes -- the
# standard Bayesian correction -- and downloads are folded in as the other half
# of the signal, since a sound taken away 150,000 times is telling you
# something no rating does.
_CROWD_PRIOR_VOTES, _CROWD_PRIOR_MEAN = 5.0, 3.6


def _crowd_score(candidate):
    rating = float(candidate.get("rating") or 0)
    votes = max(0, int(candidate.get("votes") or 0))
    downloads = max(0, int(candidate.get("downloads") or 0))
    weighted = ((votes * rating + _CROWD_PRIOR_VOTES * _CROWD_PRIOR_MEAN)
                / (votes + _CROWD_PRIOR_VOTES))
    # Logarithmic, so popularity is a nudge between near-equals rather than a
    # second relevance score: the gap from 10 to 100 downloads counts the same
    # as 100 to 1000, and neither ever outweighs being the right room.
    return round(weighted + math.log10(1 + downloads) * 0.25, 4)


def _fold(words):
    # Crude plural folding, applied to both sides of every overlap here:
    # uploaders tag "tiles" and "voices" where a query says "tile" and "voice",
    # and an exact-match overlap that misses those is measuring spelling rather
    # than sound.
    return {w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words}


def ranking_terms(query):
    """The words a candidate is actually scored against -- the query without
    its bed anchors, folded. Exposed so a caller can ask how high a `fit` this
    query could possibly earn (`search_freesound`)."""
    return _fold(term for term in _keywords(query, 12)
                 if term not in _QUERY_ANCHORS)


def _rank_candidates(candidates, query, avoid="", intent=""):
    """Order search results by how well they answer the FULL query.

    The search that produced these may have been broadened several rungs down
    the ladder, and the library's own ordering is by crowd rating -- neither of
    which knows what this room actually is. Ranking here, against the whole
    query and against what the model asked to avoid, is the difference between
    "a well-liked recording containing the word stone" and "the sound of this
    room". Costs nothing: the names and tags came back in the same response.

    `query` is the STANDARD -- the room's own words. `intent` is what was
    actually asked for, when a model rewrote the room into an acoustic
    description and those are no longer the same vocabulary. Both are scored,
    and the room outranks the request: a recording answering the room is the
    goal, and answering the request is the tiebreaker beneath it.

    Keeping them apart rather than scoring one merged query is the point. Live
    failure, "The Blizzard": ranked against the room alone ("waystation main
    hall warm modest lit"), a cave and a crackling hearth both scored ZERO --
    the ranker could not tell them apart at all, and the pick fell through to a
    `loopable` tag. Merged instead, `fit` would stop meaning "is this the room"
    and the guard that catches a model query which found nothing OF THIS ROOM
    (see `resolve_ambience`) would never fire again.
    """
    fold = _fold
    wanted = ranking_terms(query)
    # The same folding, against the words that did the FINDING. Anchors dropped
    # for the same reason: every bed on the far end is tagged "ambience", so
    # matching it says nothing about anything.
    asked = ranking_terms(intent) if intent else set()
    # A far wider cap than the query's: a veto list is a LIST, not a
    # description, and truncating it silently lets whatever sits past the cut
    # back in. It grew past 40 the moment thunder joined music, and the words
    # that fell off the end were the new ones.
    unwanted = fold(_keywords(avoid, 200))
    events = fold(_EVENT_WORDS)
    # Did this ROOM ask for music? A tavern band, a radio, a music box are all
    # real things to hear in a place, so music is only ever wrong here when
    # nothing in the room's own words called for it -- which is the difference
    # between excluding music and merely never stumbling into it.
    asked_for_music = bool(fold(_MUSIC_TERMS) & wanted)
    ranked = []
    for index, candidate in enumerate(candidates):
        # Hyphens split: uploaders write "background-music" and
        # "field-recording" as single tags, and a set intersection that cannot
        # see inside them misses the word that matters.
        haystack_text = ("%s %s" % (candidate.get("title") or "",
                                    " ".join(candidate.get("tags") or []))
                         ).replace("-", " ").casefold()
        haystack = fold(_keywords(haystack_text, 40))
        overlap = len(wanted & haystack)
        musical = (candidate.get("category") == _MUSIC_CATEGORY
                   or bool(fold(_MUSIC_TERMS) & haystack))
        vetoed = len(unwanted & haystack)
        # Long veto words also match INSIDE a token. Uploaders write
        # "Rain&ThunderLoop1Light.wav" and "stormthunder", which tokenise to
        # something no exact-match set will ever contain. Only words of six
        # letters or more, because a substring test on short ones catches
        # "sextet" and "heartbeat".
        if not vetoed:
            blob = haystack_text
            vetoed = sum(1 for word in unwanted
                         if len(word) >= 6 and word in blob)
        eventish = len(events & haystack)
        candidate["crowd"] = _crowd_score(candidate)
        # `fit` travels with the candidate: how much of the room this recording
        # actually answers. A winner with a fit of zero is the search reporting,
        # honestly, that it found nothing of this place -- which the caller can
        # act on, and which a bare ordering cannot express.
        candidate["fit"] = 0 if vetoed else overlap
        # How much of what was ASKED FOR this answers. Ranks beneath `fit` and
        # above everything else: when nothing in the results is of the room,
        # this is the difference between the hearth that was searched for and
        # whatever else the broadened rung happened to return.
        candidate["intent"] = 0 if vetoed else len(asked & haystack)
        # Travels with the candidate so a caller with a HARD veto (the weather
        # layer's, say) can drop it outright rather than merely rank it last.
        candidate["vetoed"] = bool(vetoed)
        candidate["musical"] = musical
        # Music the room never asked for sinks BENEATH every other candidate
        # without being removed: a place can legitimately have a band or a
        # radio in it, so this is last-resort rather than forbidden. Only the
        # weather layer turns it into an outright refusal, because the sky
        # cannot have a band in it under any circumstances.
        stray_music = 1 if (musical and not asked_for_music) else 0
        # A bed the uploader prepared to loop: it breaks a tie between two
        # equally room-like recordings, and is not allowed to beat relevance --
        # a seamless loop of the wrong place is still the wrong place.
        candidate["loopable"] = bool(_LOOP_WORDS & haystack)
        # Ordered by: nothing the model vetoed, then how much of the room this
        # actually is, then how much of what was asked for, then whether it
        # loops, and only then the crowd's opinion of the recording. The last
        # two sit where they do because they are not relevance at all, and
        # promoting them decides nothing well: with every candidate tied at a
        # fit of zero, a `loopable` tag alone chose the cave.
        # Sounding like an EVENT costs relevance rather than
        # outranking it -- rain is tagged "drops" and is still the most
        # continuous sound there is, so a veto on the word would throw away the
        # best bed in the list.
        ranked.append(((-vetoed, -stray_music, overlap - min(eventish, 2),
                        candidate["intent"],
                        int(candidate["loopable"]), candidate["crowd"], -index),
                       candidate))
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    return [candidate for _score, candidate in ranked]


# How many single-term rungs to add past the prefix ones. Every term would be
# tidier and is not worth the requests: four is enough to reach the head noun of
# any room query this module composes, and the caller stops the moment a rung
# actually answers the room.
_MAX_PROBES = 4


def _query_ladder(query):
    """One query, then progressively broader ones, to try until a hit.

    Two shapes of rung, in order.

    PREFIX rungs drop terms from the END, on the premise that the query is
    ordered with the most important words first -- which is true of what
    `compose_query` writes. The anchor is always kept: "ambience" is what the
    recordings on the other end are tagged with, and a kitchen query without it
    returns knives and cupboard doors. Halving rather than dropping a term at a
    time bounds this half at four requests.

    PROBE rungs are one body term each, and exist because that premise fails
    twice over.

    A model's rewrite is ordered by GRAMMAR, not by importance, and English puts
    modifiers in front of the head noun -- so truncating "stone hearth fire
    crackle wooden room" from the end keeps the adjective and throws away the
    thing making the noise. Live failure, "The Blizzard": every prefix rung
    missed until the query was the single word `stone`, and a warm hall with a
    lit hearth was given a recording titled "ambience in a large cave".
    `hearth ambience` -- a term the ladder could never reach -- returns four
    recordings tagged `ambience, fire, hearth`.

    `compose_query`'s own output fails the other way: it leads with the room's
    NAME, and a name in fiction is an invented proper noun that matches nothing.
    The same room's draft ladder returned zero results at all four rungs,
    because `waystation` survived to the last one.

    Probes are ordered but not ranked -- there is no honest way to guess which
    single word a library knows -- so the caller tries them and JUDGES what
    comes back rather than taking the first rung that returns anything. See
    `search_freesound`.
    """
    terms = str(query or "").split()
    anchors = [t for t in terms if t.casefold() in _QUERY_ANCHORS]
    body = [t for t in terms if t.casefold() not in _QUERY_ANCHORS]
    out = []

    def add(words):
        candidate = " ".join(list(words) + anchors).strip()
        if candidate and candidate not in out:
            out.append(candidate)

    for keep in (len(body), (len(body) + 1) // 2, 2, 1):
        if keep >= 1:
            add(body[:keep])
    # `body[0]` is already the last prefix rung; `add` dedupes it.
    for term in body[:_MAX_PROBES + 1]:
        add([term])
    return out or [str(query or "").strip()]


# How much of the room a recording has to answer before the ladder stops
# broadening. See `search_freesound`.
_GOOD_FIT = 2


def _beats(ranked, best):
    """Is this rung's winner a better answer than the best rung seen so far?

    Strictly better, so a tie keeps the EARLIER rung -- the one that was asked
    the more complete question. Vetoed candidates carry a fit and an intent of
    zero already, so a rung whose only results were vetoed loses to any rung
    with a real one.
    """
    if not ranked:
        return False
    if not best:
        return True
    return ((ranked[0].get("fit", 0), ranked[0].get("intent", 0))
            > (best[0].get("fit", 0), best[0].get("intent", 0)))


def _freesound_page(query, key, licence_filter, limit):
    """One Freesound search request, mapped to candidate dicts."""
    import requests

    params = {
        "query": query,
        "token": key,
        # Music cannot be excluded here the way the licence is: `category` is a
        # field Freesound will RETURN but not one its search server will filter
        # on -- `category:"Music"` narrows, `-category:"Music"` answers 400
        # "undefined field category". So it comes back with every result and is
        # weighed in `_rank_candidates` instead.
        "filter": "duration:[%d TO %d] license:(%s)" % (
            _MIN_SECONDS, _MAX_SECONDS, licence_filter),
        # Relevance, not crowd rating: the caller re-ranks what comes back
        # against the full query anyway, and a page chosen by rating is a page
        # of well-liked recordings that may have nothing to do with the room.
        "sort": "score",
        # Always a full page, however few the caller wants: ranking needs
        # something to choose between, and it is one request either way.
        "page_size": 15,
        "fields": _FREESOUND_FIELDS,
    }
    response = requests.get(FREESOUND_SEARCH, params=params,
                            timeout=_REQUEST_TIMEOUT)
    if response.status_code in (401, 403):
        raise RuntimeError("Freesound rejected the API key.")
    response.raise_for_status()
    out = []
    for row in (response.json() or {}).get("results") or []:
        candidate = _as_candidate(row)
        if candidate:
            out.append(candidate)
    return out


def _as_candidate(row):
    """One Freesound API row as a candidate dict, or None with no preview."""
    row = row or {}
    previews = row.get("previews") or {}
    preview = previews.get("preview-hq-mp3") or previews.get("preview-lq-mp3")
    if not preview:
        return None
    return {
        "source": "freesound",
        "id": row.get("id"),
        "title": row.get("name") or str(row.get("id")),
        # Kept for ranking: a recording's tags say what KIND of sound it is
        # far more reliably than its filename does, and Freesound's own
        # category says it better still.
        "tags": [str(tag) for tag in (row.get("tags") or [])],
        "category": row.get("category") or "",
        "license": row.get("license") or "",
        "username": row.get("username") or "",
        "url": row.get("url") or "https://freesound.org/s/%s/" % row.get("id"),
        "duration": round(float(row.get("duration") or 0), 1),
        "rating": round(float(row.get("avg_rating") or 0), 2),
        # How MANY people said so, and how many took it away. A rating
        # without its sample size is not a rating -- see _crowd_score.
        "votes": int(row.get("num_ratings") or 0),
        "downloads": int(row.get("num_downloads") or 0),
        "preview": preview,
    }

def freesound_sound(sound_id, key=None):
    """One sound fetched BY ID, or None.

    Its own endpoint, because the search endpoint cannot do this: Freesound has
    no `id` search field, so `id:852349` is matched as free text and returns
    whatever happens to score -- in practice a sound named "file_id.diz.mp3",
    identically for every id. A pinned soundscape resolved that way fetched the
    same unrelated recording for every one of its layers.
    """
    import requests

    key = key or ambience_settings()["key"]
    if not key or not str(sound_id or "").strip():
        return None
    response = requests.get(FREESOUND_SOUND % sound_id,
                            params={"token": key, "fields": _FREESOUND_FIELDS},
                            timeout=_REQUEST_TIMEOUT)
    if response.status_code in (401, 403):
        raise RuntimeError("Freesound rejected the API key.")
    if response.status_code == 404:
        return None
    response.raise_for_status()
    candidate = _as_candidate(response.json())
    # The endpoint is asked for one id and should answer with it. Checked
    # anyway: this is the function that exists because the previous lookup
    # confidently returned the wrong sound.
    if candidate and str(candidate.get("id")) != str(sound_id):
        raise RuntimeError(
            "Freesound returned sound %s when asked for %s"
            % (candidate.get("id"), sound_id))
    return candidate


def search_freesound(query, key=None, licences=None, limit=8, avoid="",
                     rank_query=""):
    """Freesound APIv2 text search, filtered to loopable-length ambience.

    Previews stream without OAuth, so a token is all this needs. Licence
    filtering is applied SERVER-SIDE in the query rather than by discarding
    results afterwards, so a NonCommercial recording a host did not opt into is
    never even fetched.

    Broadens the query until something matches (`_query_ladder`), then ranks
    what came back (`_rank_candidates`) -- the rung that hit is vaguer than what
    was asked for, so the library's own ordering is not the answer to the room.

    `rank_query` is the standard the results are JUDGED against when it differs
    from the words used to FIND them: a model's query is a search strategy,
    while the room's own description is what the bed is supposed to sound like.

    A rung that returns results is not the same as a rung that returns an
    ANSWER. Broadening throws words away, so the further down the ladder a hit
    comes the less of the room it was asked about -- and the last rungs are one
    word each. So this keeps going until a rung comes back with a recording
    that is actually of this place, and returns the best it saw rather than the
    first thing it found. Live failure, "The Blizzard": the rung that hit was
    the single word `stone`, all fifteen results were caves and beaches, and
    taking the first non-empty rung meant a hall with a lit hearth got one of
    the caves. The rungs that would have found the hearth were never tried,
    because something had already come back.
    """
    settings = ambience_settings()
    key = key or settings["key"]
    if not key:
        raise RuntimeError("No Freesound API key configured.")
    licences = licences or settings["licenses"]
    licence_filter = " OR ".join('"%s"' % lic for lic in licences)
    standard = rank_query or query
    # What was asked for, when that is a different vocabulary from what the
    # results are judged against. Empty when they are the same words, so a
    # host's own search in the picker is not scored twice for one match.
    intent = query if (rank_query and rank_query != query) else ""
    # How good is good enough to stop broadening. Two of the room's own words
    # is a recording that is plausibly of this place; one is a coincidence, and
    # a coincidence is exactly what the cave was. Capped by what the standard
    # could possibly yield, so a two-word room ("kitchen ambience") is not held
    # to a bar it cannot clear.
    target = max(1, min(_GOOD_FIT, len(ranking_terms(standard))))
    best = []
    # Not anchored here: every query the ENGINE composes already ends on
    # "ambience" (`compose_query`, `refine_layers`), and this is also the route
    # a host's own search in the picker takes -- someone who typed four words
    # meant those four words.
    for attempt in _query_ladder(query):
        found = _freesound_page(attempt, key, licence_filter, limit)
        if not found:
            continue
        ranked = _rank_candidates(found, standard, avoid, intent)
        if _beats(ranked, best):
            best = ranked
        # Ties keep the WIDER rung, which was asked a more complete question.
        if best and best[0].get("fit", 0) >= target:
            break
    return best[:max(1, int(limit))]


def search_candidates(query, source=None, limit=8, avoid="", rank_query=""):
    """Whatever the configured source can offer for a query, for the picker."""
    settings = ambience_settings()
    source = source or settings["source"]
    if source == "freesound":
        return search_freesound(query, limit=limit, avoid=avoid,
                                rank_query=rank_query)
    return search_local(query, limit=limit, avoid=avoid, rank_query=rank_query)


# --- resolution ------------------------------------------------------------

def build_ambience_request(chat_id, turn_idx, player_name=None, style=None):
    """Everything needed to resolve (or serve from cache) one room's ambience.

    Returns None when there is no room to sound -- an opening beat before
    anyone has been placed, say. Not an error: there is simply nothing to play.
    """
    scene = scene_after_turn(chat_id, turn_idx)
    room_id = _room_of_player(scene, player_name)
    if not room_id:
        return None
    pin = ambience_pin_for(chat_id, room_id)
    signature = acoustic_signature(scene, room_id, style, pin)
    room = ((scene.get("rooms") or {}).get(room_id) or {})
    return {
        "room": room_id,
        "room_name": room.get("name") or room_id,
        "signature": signature,
        "pin": pin,
        # Carried so a miss can ask whether some ALREADY-resolved state of this
        # room is near enough to answer for it -- see `reusable_manifest`.
        "fingerprint": acoustic_fingerprint(scene, room_id, style),
        "cached": cached_ambience(chat_id, signature),
        "place": room_soundscape(scene, room_id),
        # The sky's own attenuation for this room, which becomes the WEATHER
        # LAYER's gain rather than the whole bed's: two rooms deep, rain is a
        # quiet layer over an undiminished room tone. See compose_layers.
        "weather": weather_for_room(scene, room_id),
    }


# The parts of a manifest that describe the SOUND rather than where it was
# filed. Everything else -- signature, rev, resolved absolute paths -- is
# derived on read and must not be copied forward.
_MANIFEST_SOUND_KEYS = ("room", "layers", "rejected", "silent", "reason",
                        "query", "avoid", "fingerprint")


def reusable_manifest(chat_id, fingerprint, exclude=""):
    """An already-resolved bed near enough to answer for `fingerprint`, or None.

    The room's state moves constantly -- a description gains a clause, damage is
    noted, the style guide is edited -- and almost none of that is audible. This
    is the threshold under which the engine stops paying to re-decide: same
    room, same hour, same sky, and a description that still means the same
    place, gets the bed that is already on disk.

    Deliberately scoped to THIS chat's own directory, never the branch lineage.
    A Freesound layer's audio file is named for the signature that fetched it
    and found relative to the manifest beside it; a manifest copied out of an
    ancestor's directory would point at bytes that are not there.
    """
    best, score = None, _REUSE_SIMILARITY
    folder = os.path.join(AMBIENCE_DIR, str(chat_id))
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return None
    for name in names:
        if not name.endswith(".json"):
            continue
        signature = name[:-len(".json")]
        if signature == exclude or signature.startswith("pin") or signature.startswith("fx"):
            continue
        try:
            with open(os.path.join(folder, name), "r", encoding="utf-8") as fh:
                raw = json.load(fh)
        except (ValueError, OSError):
            continue
        if not isinstance(raw, dict):
            continue
        similarity = fingerprint_similarity(fingerprint, raw.get("fingerprint"))
        if similarity < score:
            continue
        # Only a manifest that still RESOLVES: a host who emptied the cache
        # directory of audio must not be handed a reference to it.
        if not cached_ambience(chat_id, signature):
            continue
        best, score = raw, similarity
    if not best:
        return None
    return {key: best[key] for key in _MANIFEST_SOUND_KEYS if key in best}


def _write_manifest(chat_id, signature, manifest):
    path = manifest_path(chat_id, signature)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, path)          # atomic: a reader never sees half a manifest
    manifest = dict(manifest)
    manifest["signature"] = signature
    return manifest


# A Freesound preview URL carries the sound's own id in its filename:
#   https://cdn.freesound.org/previews/341/341802_1511977-hq.mp3
# That makes the URL self-identifying, which is the whole basis of the guard
# below -- the id a layer CLAIMS can be checked against the file it is about to
# download, with no extra request.
_PREVIEW_ID = re.compile(r"/previews/\d+/(\d+)_")


def preview_sound_id(url):
    """The sound id a preview URL belongs to, or None if it does not say."""
    match = _PREVIEW_ID.search(str(url or ""))
    return int(match.group(1)) if match else None


def _fetch_preview(chat_id, signature, url, index=0, expect_id=None):
    """Download a Freesound preview into the cache. Returns the filename.

    `index` is the layer this belongs to: a mix stores several files under one
    signature, so the name has to carry which is which.

    `expect_id` is the sound this layer says it is. The URL names its own sound,
    so the two can disagree -- and when they did, nothing noticed: a pinned
    soundscape downloaded one unrelated recording for every layer and simply
    sounded like a bad recording. Fetching by id fixed the cause; this catches
    the CLASS, wherever a mismatched preview comes from. It refuses rather than
    substituting, because a wrong file written into the cache persists and is
    indistinguishable from a bad pick.
    """
    import requests

    if expect_id is not None:
        actual = preview_sound_id(url)
        # Only when the URL says. An unrecognised preview format is not
        # evidence of a mismatch, and failing on one would take the whole
        # feature down the day Freesound changes its CDN paths.
        if actual is not None and int(expect_id) != actual:
            raise RuntimeError(
                "Freesound preview mismatch: layer claims sound %s but the "
                "preview URL is sound %s (%s)" % (expect_id, actual, url))
    response = requests.get(url, timeout=_REQUEST_TIMEOUT)
    response.raise_for_status()
    ext = ".ogg" if url.endswith((".ogg", ".oga")) else ".mp3"
    path = audio_path(chat_id, "%s-%d" % (signature, index) if index else signature,
                      ext)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".part"
    with open(tmp, "wb") as fh:
        fh.write(response.content)
    os.replace(tmp, path)          # atomic: a player never opens a half file
    return os.path.basename(path)


def _materialize(chat_id, signature, index, choice, role="tone", gain=1.0,
                 query=""):
    """One chosen sound as a stored layer. Fetches only what needs fetching.

    A local pick is stored as a POINTER -- the host's own files stay theirs and
    a 40MB field recording is not duplicated per chat -- while a Freesound
    preview is downloaded into the cache under its layer index.
    """
    layer = {"role": role, "gain": round(float(gain), 3), "query": query}
    if choice["source"] == "local":
        if not resolve_local(choice.get("path")):
            raise RuntimeError("File missing from the library: %s"
                               % choice.get("path"))
        return dict(layer, source="local", path=choice["path"],
                    title=choice.get("title") or choice["path"])
    preview = choice.get("preview")
    if not preview:
        # A choice made from a search result carries its preview URL; one made
        # from a bare id -- a PIN, which stores identity rather than a URL that
        # would expire -- has to be looked up first. By id, on the sound
        # endpoint: the text search has no `id` field, so the `id:%s` query
        # this used to run returned a sound named "file_id.diz.mp3" for every
        # id alike, and a pinned two-layer soundscape played that same
        # unrelated recording twice.
        found = freesound_sound(choice.get("id"))
        preview = (found or {}).get("preview")
        if not preview:
            raise RuntimeError("Freesound has no preview for sound %s"
                               % choice.get("id"))
    filename = _fetch_preview(chat_id, signature, preview, index,
                              expect_id=choice.get("id"))
    return dict(layer, source="freesound", file=filename, id=choice.get("id"),
                title=choice.get("title") or str(choice.get("id")),
                license=choice.get("license") or "",
                username=choice.get("username") or "",
                url=choice.get("url")
                or "https://freesound.org/s/%s/" % choice.get("id"))


def _pin_manifest(chat_id, signature, pin, room_name):
    """A manifest straight from a host's explicit choice, no search at all.

    A pin may be a single sound (the shape the first version wrote, still on
    disk in every install that used it) or a whole mix.
    """
    choices = pin.get("layers") if isinstance(pin.get("layers"), list) else [pin]
    layers = [
        _materialize(chat_id, signature, index, choice,
                     role=choice.get("role") or ("tone" if index == 0 else "extra"),
                     gain=choice.get("gain", 1.0))
        for index, choice in enumerate(choices[:MAX_LAYERS])
    ]
    return _write_manifest(chat_id, signature, {
        "room": room_name, "pinned": True, "rejected": [], "layers": layers,
    })


# One resolution per signature no matter how many callers want it. Same shape
# as the backdrop generation lock and for the same reason: two turns in one
# room become visible together, a second tab is open, the reader scrolls back.
#
# And the same table, for the same reason: this dict was never pruned either,
# so a long story left one dead entry per distinct audible room-state for the
# life of the process. Being the twin of a leaking module is how a leak gets
# copied, so the fix is shared rather than written twice -- see `outofband`.
_AMB_LOCKS = outofband.KeyedLocks()


def _resolution_lock(key):
    """Exclusive use of one signature, for as long as the `with` block runs."""
    return _AMB_LOCKS.hold(key)


def candidate_key(candidate):
    """A stable identity for one search result, so a rejected sound can be
    recognised again on the next search even though ranking may have moved."""
    if (candidate or {}).get("source") == "freesound":
        return "fs:%s" % candidate.get("id")
    return "lc:%s" % (candidate or {}).get("path")


def resolve_ambience(chat_id, turn_idx, player_name=None, style=None,
                     force=False, reroll=False, reroll_layer=None, work=None):
    """Choose (or serve from cache) the ambience for a turn.

    Blocks for the length of a search plus a download, which is why nothing in
    the request path calls it directly -- see `request_ambience`.

    `reroll` is the escape hatch for a bad pick: a query that reads sensibly can
    still land on a recording with a siren in it, and a feature whose only
    remedy is "search again and get the identical top hit" has no remedy at
    all. The rejected choice is remembered IN THE MANIFEST -- the one place
    that already travels with branches and archives -- so rerolling walks down
    the result list instead of re-offering what was just refused.

    `work` is the queue's handle when this is running out of band, and None for
    every direct blocking caller. Returns None when it was cancelled: a room
    nobody is standing in any more gets no bed, and none was promised.
    """
    req = build_ambience_request(chat_id, turn_idx, player_name, style)
    if not req:
        return None
    if req["cached"] and not (force or reroll):
        return dict(req["cached"], cached=True)

    with _resolution_lock((chat_id, req["signature"])):
        existing = cached_ambience(chat_id, req["signature"])
        if existing and not (force or reroll):
            return dict(existing, cached=True)

        # Between steps, never mid-flight. Everything past this line is a model
        # call, a search or a download, and the commonest way to arrive here
        # already cancelled is the one the lock above creates: several callers
        # queued on one signature and released one at a time.
        if outofband.stopped(work):
            return None

        if req["pin"]:
            if reroll:
                # A pin is an explicit instruction; silently replacing it would
                # be the feature overruling the host.
                raise RuntimeError(
                    "This room's sound is pinned. Clear the pin to reroll it.")
            return dict(_pin_manifest(chat_id, req["signature"], req["pin"],
                                      req["room_name"]), cached=False)

        if not (force or reroll):
            # Nothing cached under THIS key, but the room may have been resolved
            # a description-edit ago. Below the threshold, adopt that bed rather
            # than paying a model call and a download to arrive back at it.
            twin = reusable_manifest(chat_id, req.get("fingerprint") or {},
                                     exclude=req["signature"])
            if twin:
                manifest = _write_manifest(chat_id, req["signature"],
                                           dict(twin, room=req["room_name"]))
                return dict(cached_ambience(chat_id, req["signature"]) or manifest,
                            cached=True)

        rejected = [k for k in ((existing or {}).get("rejected") or [])
                    if isinstance(k, str)]
        keep = {}
        if reroll and existing:
            # Reject only what is being rerolled, and KEEP the rest of the mix
            # playing as it was: a reader who says "not that rain" has not also
            # asked for a different room underneath it.
            for index, layer in enumerate(_as_layered(existing)["layers"]):
                if reroll_layer is None or index == reroll_layer:
                    rejected.append(candidate_key(layer))
                else:
                    keep[index] = layer

        settings = ambience_settings()
        # A reroll reuses the queries the manifest already stores. Re-deriving
        # them would mean another model call (measured at ~27s on a reasoning
        # model standing in for an unconfigured `ambience_prompt` role) to
        # arrive at the same words -- and the complaint a reroll answers is
        # "that CLIP is wrong", not "that description is wrong".
        stored = [layer.get("query") for layer in
                  _as_layered(existing or {}).get("layers", [])]
        verdict = {}
        draft = compose_layers(req["place"], style, req.get("weather"))
        if reroll and (existing or {}).get("silent"):
            # Rerolling a room the model called silent is the host overruling
            # that verdict -- so ask the deterministic plan for a bed and do NOT
            # put the question back to the model, which would only answer
            # "silent" again and make the button do nothing.
            plan = draft
            # The refusal goes in the ledger like any other, because `rev` --
            # and therefore the token the player crossfades on -- counts it. A
            # silent manifest has no layers to reject, so without this the new
            # bed would arrive under the token that was already playing and the
            # client would poll for a change that never came.
            rejected.append("silent")
        elif reroll and existing and stored and all(stored):
            plan = [{"role": layer.get("role") or "tone",
                     "query": layer.get("query"),
                     "gain": layer.get("gain", 1.0)}
                    for layer in _as_layered(existing)["layers"]]
        else:
            plan, verdict = refine_layers(draft, req["place"])
        # What must not turn up in this room, kept in the manifest so a reroll
        # -- which reuses the stored queries rather than re-asking the model --
        # still knows what the room was told to avoid.
        avoid = verdict.get("avoid") or (existing or {}).get("avoid") or ""

        if verdict.get("silent") and not plan:
            # A cached silence: written like any other manifest so the room
            # settles into quiet once, instead of paying for the same judgement
            # on every beat and reading as a permanent failure in between.
            manifest = _write_manifest(chat_id, req["signature"], {
                "room": req["room_name"], "rejected": rejected, "layers": [],
                "silent": True, "reason": verdict.get("reason") or "",
                "query": (draft[0]["query"] if draft else ""),
                "fingerprint": req.get("fingerprint") or {},
            })
            return dict(cached_ambience(chat_id, req["signature"]) or manifest,
                        cached=False)

        # The deterministic draft, by role: what the scene itself says each
        # layer should sound like, before any model rewrote it.
        draft_by_role = {layer.get("role"): layer.get("query")
                         for layer in draft if layer.get("query")}
        layers = []
        for index, step in enumerate(plan[:MAX_LAYERS]):
            # One layer is a search plus a download, so the top of this loop is
            # a genuine step boundary and the last one that saves anything. A
            # cancelled resolution writes no manifest at all rather than a
            # half-built mix: a bed missing the layer it was named for is a
            # worse artefact than no bed.
            if outofband.stopped(work):
                return None
            if index in keep:
                layers.append(keep[index])
                continue
            # A deeper page when rerolling: the point is to have somewhere to go.
            # The ROOM's own words are the standard every candidate is judged
            # against, whatever words were used to find it: the model writes a
            # search strategy, the scene says what the place is. An invented
            # 'extra' layer has no draft counterpart and answers to itself.
            standard = draft_by_role.get(step.get("role")) or step["query"]
            # What this layer may never be, on top of what the model asked to
            # avoid: music can be in a room and can never be the sky.
            veto = role_veto(step.get("role"))
            step_avoid = " ".join(part for part in (avoid, veto) if part)
            candidates = search_candidates(step["query"], settings["source"],
                                           limit=15 if reroll else 8,
                                           avoid=step_avoid, rank_query=standard)
            # A model query that finds nothing OF THIS ROOM loses to the
            # engine's own draft, which leads with the room's name -- and the
            # ladder drops from the END, so a name written last is the first
            # word discarded. That is how "stone tile floor curtain air flow
            # bathroom" became a search for "stone tile", and a bath scene got
            # falling roof tiles.
            if (standard != step["query"]
                    and not (candidates and candidates[0].get("fit"))):
                plain = search_candidates(standard, settings["source"],
                                          limit=15 if reroll else 8,
                                          avoid=step_avoid, rank_query=standard)
                if plain and plain[0].get("fit", 0) > (
                        candidates[0].get("fit", 0) if candidates else 0):
                    candidates = plain
                    step = dict(step, query=standard)
            if not candidates and settings["source"] == "local" and index == 0:
                # A local library rarely has a match for a specific room name,
                # and a silent failure reads as a broken feature. Retry on the
                # room's coarsest terms before giving up on the ROOM layer;
                # a missing weather or extra layer is simply left out.
                candidates = search_local(compose_query(
                    {"name": "", "desc": req["place"].get("desc") or ""}, style),
                    avoid=step_avoid)
            if veto:
                # A hard filter, and deliberately with no fallback: every path
                # above may have relaxed something to find SOMETHING, and this
                # is the one thing that must not be relaxed. A layer left out is
                # the correct outcome here.
                candidates = [c for c in candidates
                              if not (c.get("vetoed") or c.get("musical"))]
                # And it must actually BE the weather. Broadening can end on a
                # rung so vague that the winner shares no word with the sky at
                # all -- a room once got "Night Ambiance" as its rain. A weather
                # layer that is not weather is worse than no weather layer.
                candidates = [c for c in candidates if c.get("fit")]
            # Nothing of the room AND nothing of what was asked for. Every path
            # above has already relaxed what it could -- a broader rung, the
            # engine's own draft instead of the model's words -- so a winner
            # still scoring zero on both is the search saying, accurately, that
            # it found nothing of this place. Leaving the layer out is the
            # honest answer; laying it under the room anyway is how a warm hall
            # with a lit hearth ended up sounding like a cave, on the strength
            # of a `loopable` tag and nothing else.
            candidates = [c for c in candidates
                          if c.get("fit") or c.get("intent")]
            fresh = [c for c in candidates if candidate_key(c) not in rejected]
            if not fresh and candidates:
                # Every result for this layer has been refused at least once.
                # Cycle rather than dead-end: a reroll button that eventually
                # does nothing is worse than one that comes back round.
                rejected = [k for k in rejected
                            if k not in {candidate_key(c) for c in candidates}]
                fresh = candidates
            if not fresh:
                continue
            layers.append(_materialize(chat_id, req["signature"], index, fresh[0],
                                       role=step.get("role") or "tone",
                                       gain=step.get("gain", 1.0),
                                       query=step["query"]))

        if not layers:
            raise RuntimeError("No ambience found for: %s"
                               % (plan[0]["query"] if plan else req["room_name"]))
        manifest = _write_manifest(chat_id, req["signature"], {
            "room": req["room_name"], "rejected": rejected, "layers": layers,
            "avoid": avoid,
            # What this bed was chosen FOR, so a near-identical state of the
            # same room can adopt it instead of resolving again.
            "fingerprint": req.get("fingerprint") or {},
            # Kept at the top level too, so a manifest still says at a glance
            # what it was looking for.
            "query": layers[0].get("query") or "",
        })
    resolved = cached_ambience(chat_id, req["signature"]) or manifest
    return dict(resolved, cached=False)


# --- one-shots -------------------------------------------------------------
#
# A bed loops; a one-shot happens once. Thunder is the only one so far, and it
# exists because the weather overlay draws lightning: a flash with no sound is
# a screen artifact, and a flash followed by a rumble is a storm.
#
# Deliberately a CLOSED set rather than a search parameter. The route that
# serves these is host-only, but "fetch and cache whatever string arrives" is
# still the wrong shape for something that reaches the filesystem and an
# external API -- and there are, so far, exactly two of them.

ONESHOTS = {
    "thunder": "thunder rumble distant storm",
    "thunder_close": "thunder crack close loud",
}

# How many DIFFERENT takes of each effect to keep. One thunderclap replayed
# for a whole storm stops being weather and becomes a sample: the ear learns
# it in three or four strikes and every one after that is the same sound
# arriving again. Variants walk down the ranked results of the same search, so
# they are genuinely different recordings of the same thing rather than the
# same file pitched about.
ONESHOT_VARIANTS = 4


def oneshot_signature(name, variant=0):
    # Variant 0 keeps the historical key, so caches fetched before this
    # existed are still the first take rather than orphaned bytes on disk.
    key = str(name) if not variant else "%s#%d" % (name, int(variant))
    return "fx" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:22]


def resolve_oneshot(chat_id, name, variant=0, work=None):
    """Fetch (or serve from cache) one non-looping effect. Blocking.

    Returns None when `work` was cancelled -- see `resolve_ambience`.
    """
    if name not in ONESHOTS:
        raise ValueError("Unknown effect: %s" % name)
    variant = max(0, min(int(variant or 0), ONESHOT_VARIANTS - 1))
    signature = oneshot_signature(name, variant)
    existing = cached_ambience(chat_id, signature)
    if existing:
        return dict(existing, cached=True)

    with _resolution_lock((chat_id, signature)):
        existing = cached_ambience(chat_id, signature)
        if existing:
            return dict(existing, cached=True)
        # The step boundary: the search and the download are below it.
        if outofband.stopped(work):
            return None
        settings = ambience_settings()
        # No model call: a one-shot's query is a constant, so the whole
        # query-writing stage is skipped and this is search-plus-fetch only.
        candidates = search_candidates(ONESHOTS[name], settings["source"],
                                       limit=max(8, ONESHOT_VARIANTS * 2))
        if not candidates:
            raise RuntimeError("No %s sound found in the configured source." % name)
        # Nth-best rather than best: that IS the variety. A library with only
        # one usable thunder falls back to it rather than failing.
        best = candidates[min(variant, len(candidates) - 1)]
        common = {"room": "", "query": ONESHOTS[name], "rejected": [],
                  "oneshot": name}
        if best["source"] == "local":
            manifest = _write_manifest(chat_id, signature, dict(common, **{
                "source": "local", "path": best["path"],
                "title": best.get("title") or best["path"]}))
        else:
            filename = _fetch_preview(chat_id, signature, best["preview"])
            manifest = _write_manifest(chat_id, signature, dict(common, **{
                "source": "freesound", "file": filename, "id": best.get("id"),
                "title": best.get("title") or "", "license": best.get("license") or "",
                "username": best.get("username") or "", "url": best.get("url") or ""}))
    return dict(cached_ambience(chat_id, signature) or manifest, cached=False)


def request_oneshot(chat_id, name, variant=0):
    """Ensure an effect exists, fetching in the background. Never blocks."""
    if name not in ONESHOTS:
        raise ValueError("Unknown effect: %s" % name)
    variant = max(0, min(int(variant or 0), ONESHOT_VARIANTS - 1))
    signature = oneshot_signature(name, variant)
    cached = cached_ambience(chat_id, signature)
    if cached:
        return {"signature": signature, "status": "ready", "name": name}
    _QUEUE.submit(
        signature,
        lambda work: resolve_oneshot(chat_id, name, variant, work=work),
        group=chat_id)
    return {"signature": signature, "status": "pending", "name": name}


# --- out-of-band resolution queue ------------------------------------------
#
# Nothing may WAIT on a sound. A search plus a download is seconds of network,
# and a route that blocks on it holds a server worker for the whole time --
# for audio nobody is waiting on, since the prose is already on screen.
#
# Shared with backdrops.py through `outofband.Queue`, because both tables this
# used to keep grew with the key space rather than with the work:
# `_AMB_IN_FLIGHT` pruned itself, but `_AMB_LAST_ERROR` only ever lost an entry
# when somebody asked for that exact signature again, which a reader who never
# walks back into that room never does. One-shots share the queue too, as they
# always shared these dicts.

_QUEUE = outofband.Queue("ambience")


def ambience_status(chat_id, signature):
    """'ready' | 'pending' | 'error' | 'absent' for one signature."""
    if cached_ambience(chat_id, signature):
        return "ready"
    return _QUEUE.status(signature)


def ambience_error(signature):
    """The last failure for this signature, or None -- out-of-band work that
    fails silently is worse than work that fails loudly."""
    return _QUEUE.error(signature)


def cancel_ambience(chat_id):
    """Stop the resolutions in flight for one chat. Returns how many were asked.

    Cooperative and BETWEEN steps, like `backdrops.cancel_backdrops`: a
    download already in progress finishes, and the resolution stops at the top
    of the next layer rather than leaving a half-built mix behind it.
    """
    return _QUEUE.cancel_group(chat_id)


def request_ambience(chat_id, turn_idx, player_name=None, style=None,
                     force=False, reroll=False, reroll_layer=None):
    """Ensure this turn's ambience exists, resolving in the background.

    Returns {signature, status, room} and NEVER blocks on the network.
    """
    req = build_ambience_request(chat_id, turn_idx, player_name, style)
    if not req:
        return None
    signature = req["signature"]
    if req["cached"] and not (force or reroll):
        return {"signature": signature, "status": "ready",
                "room": req["room_name"]}

    # A reroll SUPERSEDES rather than joins, and this is the case that made the
    # missing cancellation path visible: pressing reroll while the first
    # resolution was still running returned "pending" and dropped the reroll
    # entirely, so the host waited and was handed back the very sound they had
    # just refused -- by a queue reporting success. Joining is right for two
    # readers who want the same bed and wrong for an explicit instruction to
    # replace it.
    _QUEUE.submit(
        signature,
        lambda work: resolve_ambience(chat_id, turn_idx, player_name, style,
                                      force=force, reroll=reroll,
                                      reroll_layer=reroll_layer, work=work),
        group=chat_id, supersede=force or reroll)
    return {"signature": signature, "status": "pending",
            "room": req["room_name"]}
