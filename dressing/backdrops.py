"""Scene backdrops: a generated image of the room the player is standing in.

EXPERIMENTAL. Runs entirely outside the turn pipeline -- image generation takes
seconds to tens of seconds and must never sit between the player and their
prose.

Three rules shape everything here.

**1. The prompt is built from STRUCTURED spatial data, with spoiler categories
dropped by construction.** Not from narrative prose. The scene graph separates
architecture (`rooms[id].name/desc`, location, time, adjacency) from occupants
(`entities`, `positions`), so keeping the former and dropping the latter is a
whitelist -- auditable, and it cannot half-work. An earlier draft derived the
prompt from perception prose and stripped people with regexes; it merged
sentences, leaked dialogue fragments, and produced a thin source. Structured
data is both safer and considerably richer.

**2. Backdrops depict the room EMPTY -- no people, ever.** Mostly this falls
out of rule 1: occupants are never in the projection to begin with, so a
character or a monster cannot reach the image. The one place it does not fall
out for free is `rooms[id].desc`, which the whitelist admits and which live
data proved carries populations ("Crew members and civilians gather here during
off-duty hours"), so that one field is additionally people-stripped on the way
out -- see `place_desc`. Keeping people out also avoids uncanny likenesses and
is what makes per-room caching correct.

**3. A cache key is a room plus its VISIBLE state.** Not the room id alone -- a
room whose lights just failed, whose window broke, or which is now on fire is
not the same picture. Anything that changes what the place looks like changes
the key; anything else (who is standing there, what was said) does not, so
walking back into a room you left is instant and free.
"""

from __future__ import annotations

import hashlib
import json
import os
import re

from core import outofband
from core.db import q, wget_for_frame
from core.logging_utils import logger
from world.spatial import (
    _PASSABLE_BARRIERS, ROOM_SIZES, body_cell, effective_adjacent,
    effective_facing, effective_light, effective_room_size, light_at,
    normalize_barrier, normalize_bearing, normalize_footprint,
    normalize_height, normalize_light, normalize_vertical, opposite_bearing,
    room_grid, room_of,
)
from core.paths import INSTALL_ROOT
from world.weather import room_exposure, weather_for_room, weather_words
from world.day_cycle import (CLOCK_READING, DAY_LENGTH_HOURS_DEFAULT,
                            PHASE_NAMES, PM_MARKER, clock_reading_hour,
                            phase_of_hour)

# Where generated images live. Deliberately NOT the database: engine.db is
# already ~400MB of text, and a few hundred backdrops would dwarf it while
# making every backup and export drag them along.
BACKDROP_DIR = os.environ.get(
    "FICTION_ENGINE_BACKDROP_DIR",
    os.path.join(INSTALL_ROOT, "backdrops"))

# A backdrop is scenery, so the visual signature only tracks what changes how
# the PLACE looks. Overlays and conditions can do that (smoke, darkness,
# wreckage); positions and dialogue cannot.
# Weather is NOT here even though it plainly changes how a place looks: it is
# scene-level, and a cellar does not become a different picture because it
# started raining over the city. It enters the key ROOM-SCOPED instead, through
# weather.weather_for_room -- see visual_signature.
_VISUAL_STATE_KEYS = ("overlays", "conditions", "ground")

# scene.time_of_day is freeform narrative text, not a clock: live values
# include "Night", "Late autumn afternoon", "Stardate 46357.4, 14:32 hours",
# "0830". Hashing it raw would key the SAME room with an IDENTICAL description
# differently on consecutive turns, defeating the cache on nearly every beat --
# the one thing that makes this feature affordable. Only the coarse visual
# bucket belongs in the key: night really does look different from noon.
#
# (This table was also the whole defence against the field's OTHER former
# tenant, a per-beat passage phrase -- "a few seconds", "moments pass" -- which
# it bucketed to "" and so survived. That writer is gone; the field now holds
# one kind of statement. See `world.mechanics.normalize_time_of_day`.)
_TIME_BUCKETS = (
    ("night", ("night", "midnight", "small hours", "after dark", "nocturn",
               "pre-dawn", "predawn", "before dawn")),
    ("evening", ("evening", "dusk", "sunset", "twilight", "nightfall")),
    ("morning", ("morning", "dawn", "sunrise", "daybreak", "first light")),
    ("day", ("noon", "midday", "afternoon", "daylight", "daytime")),
)

# A CLOCK READING IS A TIME OF DAY TOO, and a closed synonym table cannot read
# one. Measured across the author's 81-chat corpus 2026-08-25: of the 17
# openings this could not bucket, 12 said the time in digits -- "09:42",
# "14:32 hours", "08:42:15 AM", "1430 hours" -- and a whole story line (chats
# 75-84, an institutional intake) lost its light to nothing but the absence of
# a numeric branch.
#
# Three guards, each earned by a live string. A colon form may not be preceded
# by a sign, or "Cycle-End -01:45:00" (a COUNTDOWN, not a time) reads as
# quarter to two. A bare four-digit form is accepted only with a leading zero
# ("0830") or an explicit unit ("1430 hours"), because otherwise every year in
# every establish -- "Late night, 2026" -- becomes twenty past eight. And the
# minute must be a real minute, which is what stops "1893" reading as 18:93.
# The regex itself now lives with the day cycle (`world/day_cycle.py`, which
# anchors a clock on the same reading), imported rather than restated so a
# guard added to one reader cannot go missing from the other.
_CLOCK_READING = CLOCK_READING
_PM_MARKER = PM_MARKER


# WHICH BUCKET EACH PHASE OF THE DAY FALLS IN, read off the table above
# rather than restated as a second set of hour boundaries. How the day is cut
# is `world/day_cycle`'s to say; how COARSELY the scenery caches key it is
# this file's, and that is all this map adds. (Review 2026-09-07 B9: the
# hour boundaries here were 5/11/17/21 against the cycle's 4.5/7/11/13.5/18/
# 19.5/22, so a story that said "09:42 PM" got a night backdrop while the
# same moment written "evening" got an evening one.)
_PHASE_BUCKETS = {phase: bucket
                  for bucket, words in reversed(_TIME_BUCKETS)
                  for phase in PHASE_NAMES if phase in words}


def _hour_bucket(hour, day_length=DAY_LENGTH_HOURS_DEFAULT):
    """Which coarse bucket an hour of the day falls in, by way of the phase
    the day cycle puts that hour in."""
    return _PHASE_BUCKETS.get(phase_of_hour(hour, day_length), "night")


def time_bucket(value):
    """Coarse time-of-day for cache keying and prompting, or '' if the text
    says nothing about the light."""
    text = str(value or "").casefold()
    for bucket, words in _TIME_BUCKETS:
        if any(word in text for word in words):
            return bucket
    hour = clock_reading_hour(text)
    if hour is not None:
        return _hour_bucket(hour)
    return ""


def place_desc(room):
    """A room's description with its occupants stripped out.

    The single definition of "what this place looks like", used by BOTH the
    prompt projection and the cache key so the two cannot drift: a key that
    hashes text the prompt never sees would pay for regenerations the picture
    cannot show. Defined here, above its callers, because `visual_signature`
    is the first of them.
    """
    return to_visual_register(_setting_only((room or {}).get("desc") or ""))


def _room_of_player(scene, player_name):
    positions = (scene or {}).get("positions") or {}
    if player_name and positions.get(player_name):
        return positions[player_name]
    return (scene or {}).get("player_room")


# The style-guide fields an image prompt is allowed to see, and therefore the
# only ones that may appear in the cache key. `tone` is written into
# `compose_prompt`; `avoid` into both it and `compose_revision`.
#
# The rule outlived the fields it was written against: `genre`,
# `director_notes` and `mapping_notes` left STYLE_GUIDE_FIELDS on 2026-09-04
# (E39, review of 2026-09-07 -- this note still had `genre` reaching the
# prompt), and a guide that carries one of them now is a stored row from
# before that. They were instructions to OTHER READERS and never touched a
# pixel. Hashing the whole guide meant editing a Director note
# invalidated every backdrop in the story at once, which is what happened live:
# chat 67 ("Lagunica adventure") gained a style guide after its rooms were
# drawn, every signature moved, and the engine reported every existing image
# absent and began paying to redraw them.
#
# This is `place_desc`'s rule applied to the other half of the key -- the key is
# a function of what reaches the image, and a key that hashes text the prompt
# never sees pays for regenerations the picture cannot show.
VISUAL_STYLE_KEYS = ("tone", "avoid")


def visual_style(style):
    """The part of a house style that changes how a room is DRAWN.

    Empty values are dropped rather than stored, so "field absent" and "field
    present but blank" hash identically -- clearing a field must return a story
    to the images it already has, not strand them behind a third key.
    """
    style = style or {}
    return {key: style[key] for key in VISUAL_STYLE_KEYS if style.get(key)}


def visual_signature(scene, room_id, style=None, viewer=None, *,
                     regions=None, viewer_camera=False):
    """A stable hash of everything that changes how `room_id` LOOKS.

    Deliberately excludes people and speech: a room does not become a different
    picture because someone walked in. Including them would defeat the cache on
    almost every turn, which is the whole reason this feature is affordable.

    The BRIEF is keyed too (`room_brief`: walls, openings, proportion, camera,
    look), because it reaches the prompt: a fixture moved to another wall or a
    door opened is a different picture, and a bystander is still not one. Until
    2026-09-04 `exits` reached the prompt and NOT the key, against this
    module's own rule that the key is a function of what reaches the image --
    a door opening never redrew the room. Every key below is present only when
    it has something to say, so a room with none of it hashes as it did.
    """
    scene = scene or {}
    room = ((scene.get("rooms") or {}).get(room_id) or {})
    material = {
        "room": room_id,
        "name": room.get("name") or "",
        # The PROJECTED description, not the raw one: the cache key has to be a
        # function of what actually reaches the image prompt. Hashing the raw
        # text would regenerate a room because someone was written into (or out
        # of) its description -- a change the picture cannot show.
        "desc": place_desc(room),
        "time": time_bucket(scene.get("time_of_day")),
        "location": scene.get("location") or "",
        # Without this a room that goes dark keeps serving its lit backdrop --
        # the cache is keyed on what changes how the room LOOKS, and nothing
        # changes that more.
        "light": _viewer_light(scene, room_id, viewer),
        "light_sources": _light_sources_in(scene, room_id),
        # Only what this room actually gets of the sky, and only as the WORDS
        # that reach the prompt -- not the raw weather dict, which carries the
        # whole scene's sky and would repaint a cellar for a storm it cannot
        # see. Keying on the rendered description keeps the rule the rest of
        # this module follows: the key is a function of what reaches the image.
        "weather": weather_words(weather_for_room(scene, room_id), "sight"),
        # The style fields that reach the IMAGE, not the whole house style --
        # see `visual_style`.
        "style": visual_style(style),
    }
    material.update(room_brief(scene, room_id, viewer, regions=regions,
                               viewer_camera=viewer_camera))
    for key in _VISUAL_STATE_KEYS:
        value = scene.get(key)
        if isinstance(value, dict):
            # Only this room's entry, so a fire two decks away does not
            # invalidate every other room's backdrop. Absent and
            # present-but-not-for-this-room must hash identically, so an empty
            # entry is omitted rather than stored as None.
            scoped = value.get(room_id)
            if scoped:
                material[key] = scoped
        elif value:
            material[key] = value
    blob = json.dumps(material, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]


def backdrop_path(chat_id, signature, room_id=None):
    """Where one backdrop lives.

    Filed under its ROOM when the caller knows which -- a long story is
    hundreds of images across a dozen rooms, and a flat directory of hex names
    is unreadable to anyone trying to find, keep or delete a particular place.
    Images written before this are still in the flat layout and are still
    found; see `cached_backdrop`, which is the only thing that needs to know.
    """
    if room_id:
        return os.path.join(BACKDROP_DIR, str(chat_id), _room_dir(room_id),
                            "%s.png" % signature)
    return os.path.join(BACKDROP_DIR, str(chat_id), "%s.png" % signature)


# Room ids come from a model and reach the filesystem here, so they are reduced
# to something that cannot escape the directory they belong in.
_ROOM_DIR_SAFE = re.compile(r"[^a-z0-9_-]+")


def _room_dir(room_id):
    name = _ROOM_DIR_SAFE.sub("_", str(room_id or "").casefold()).strip("_")
    return name[:60] or "_room"


# How many ancestors deep a lookup will walk. A miss costs one os.path.exists
# per generation, which is nothing, but the list is written by branching and
# read here forever, so it gets a ceiling rather than trusting it to stay short.
_LINEAGE_LIMIT = 64


def branch_lineage(chat_id):
    """Chat ids this chat was branched out of, nearest ancestor first.

    A branch inherits the whole scene graph, so its early rooms are pixel-for-
    pixel the rooms the source chat already paid to draw -- same room id, same
    description, same signature. Only the storage path differed, so every
    branch used to redraw its inheritance from scratch.
    """
    try:
        row = q("SELECT branched_from FROM chats WHERE id=?", (chat_id,),
                one=True)
    except Exception:
        # A caller with no chats row (tests, a chat deleted mid-request) gets
        # its own directory only, which is the pre-lineage behaviour.
        return []
    if not row:
        return []
    try:
        ids = json.loads(row["branched_from"] or "[]")
    except (ValueError, TypeError):
        return []
    if not isinstance(ids, list):
        return []
    out = []
    for cid in ids[:_LINEAGE_LIMIT]:
        try:
            cid = int(cid)
        except (TypeError, ValueError):
            continue
        # A chat is never its own ancestor, and a repeated id would only
        # re-stat a directory that already missed.
        if cid != int(chat_id) and cid not in out:
            out.append(cid)
    return out


def cached_backdrop(chat_id, signature):
    """The path to an already-generated backdrop, or None.

    Looks in this chat's own directory first, then walks the branch lineage.
    An ancestor's file is READ IN PLACE and never copied forward: a branch is
    cheap precisely because it adds no bytes, and a story branched a dozen
    times would otherwise carry a dozen copies of the same corridor.
    """
    for cid in [chat_id] + branch_lineage(chat_id):
        # The flat layout first: it is where everything generated before rooms
        # had their own folders still lives, and checking it costs one stat.
        path = backdrop_path(cid, signature)
        if os.path.exists(path):
            return path
        # Then the room folders. A signature already encodes its room, so at
        # most one of these can match; the scan is a handful of directories.
        folder = os.path.join(BACKDROP_DIR, str(cid))
        try:
            rooms = os.listdir(folder)
        except OSError:
            continue
        for room in rooms:
            nested = os.path.join(folder, room, "%s.png" % signature)
            if os.path.exists(nested):
                return nested
    return None


# --- prompt construction ---------------------------------------------------

# Phrases that would put a person in the frame. The image prompt asks for an
# empty room, but a model handed "the Doctor leans toward the LCARS panel"
# will draw the Doctor anyway, so the source text is stripped before it ever
# reaches the prompt rather than relying on the instruction alone -- the same
# belt-and-braces shape used elsewhere in this engine.
# Matched against ONE SENTENCE at a time (see `_setting_only`), never across a
# whole description. The clause-spanning form this used to have --
# `[^.!?]*\b(...)\b[^.!?]*[.!?]` -- is the textbook quadratic-backtracking
# shape: an unbounded run on both sides of an alternation. Measured on the real
# room descriptions in engine.db it cost 8.06ms per call against 0.24ms for the
# sentence-split form, and it is called four times for every backdrop-plus-
# ambience pair the reader's scrolling asks for. Byte-identical output on all
# 54 of them; the split is the same rule expressed so it cannot backtrack.
_PERSON_WORDS = re.compile(
    r"\b(he|she|they|him|her|them|his|hers|their|"
    r"says?|said|asks?|asked|replies|replied|leans?|turns?|looks?|walks?|"
    r"stands?|sits?|smiles?|nods?|whispers?|shouts?|steps?|"
    # Collective occupants. Room DESCRIPTIONS name populations where narrative
    # prose would name a character -- live data from chat 34 had "Crew members
    # and civilians gather here during off-duty hours, conversations murmuring
    # at various tables" sitting in rooms.enterprise_ten_forward.desc, which
    # the pronoun/speech patterns above do not touch. A backdrop built from
    # that sentence draws a lounge full of people.
    # "crew members" and not bare "crew" on purpose: the same chat's corridor
    # reads "doors lead to crew quarters, labs, and utility spaces" and the
    # turbolift panel scrolls "crew registration data" -- both architecture,
    # both kept.
    r"crew ?members?|civilians?|patrons?|passengers?|bystanders?|"
    r"onlookers?|crowds?|people|figures?)\b",
    re.I)

# Sentence boundaries, keeping the terminator with the sentence it ends.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s*")


def _setting_only(text):
    """Drop sentences that are about people acting or speaking.

    Leaves architecture, light, weather, materials and sound. Conservative in
    the right direction: over-stripping yields a thinner prompt, whereas
    under-stripping puts a character in the picture.
    """
    # Quotes FIRST. Removing person-clauses first strips the attribution
    # ("He says,") while leaving the quoted sentence behind as if it were
    # narration -- the first draft produced "setting" text that was almost
    # entirely leftover dialogue.
    # Replace a quote with a sentence BREAK, not a space: the closing period
    # usually sits inside the quotation marks, so substituting whitespace
    # welded "He says," onto the next sentence and the person-clause strip then
    # ate the setting prose along with it.
    stripped = re.sub(r'[""«»"][^""«»"]*[""«»"]', " . ", str(text or ""))
    # Sentence at a time. Dropping a whole sentence is what the old
    # clause-spanning patterns did too -- they just paid quadratically for the
    # privilege of finding its edges. See `_PERSON_WORDS`.
    stripped = " ".join(
        sentence for sentence in _SENTENCE_SPLIT.split(stripped)
        if sentence and not _PERSON_WORDS.search(sentence)
        and not _BODY_WORDS.search(sentence))
    # Fragments left by removing a quote mid-sentence.
    stripped = re.sub(r"(?<![.!?])\s*\.\.+", " ", stripped)
    # Collapse the runs of bare periods left where consecutive quotes were
    # replaced by sentence breaks.
    stripped = re.sub(r"(?:\s*\.\s*){2,}", " ", stripped)
    stripped = re.sub(r"^[\s.]+", "", stripped)
    stripped = re.sub(r"\s{2,}", " ", stripped).strip()
    return stripped


# --- visual register ------------------------------------------------------
#
# Image generators reject prompts on keywords, not on meaning, and a room
# description written for prose is full of them. "Blood on the walls" is an
# ordinary thing for a room to have after a fight and an instant refusal from
# most generators -- so a legitimate empty-room backdrop fails on a word.
#
# The fix is to say what the EYE SEES instead of naming the concept: "dark red
# spatter across the plaster" paints the identical picture and is not a
# keyword. This is better image prompting regardless -- generators render
# colour, texture and form far more reliably than they render abstractions --
# and it is the whole trick here. Nothing below is trying to obtain an image a
# generator would refuse on its merits: backdrops are EMPTY ROOMS by
# construction (see _PERSON_CLAUSE above and the "no people" instruction in the
# style string), so what is being described is furniture, surfaces and light.
# Where a term describes something only a person can be or do, the right
# rewrite is to drop it, and that is what these do.
#
# Ordered longest-first at build time so "blood-soaked" is handled before
# "blood".
_VISUAL_REGISTER = {
    # Aftermath. The commonest refusal, and the easiest to render honestly.
    "bloodstained": "stained dark red",
    "blood-stained": "stained dark red",
    "bloodsoaked": "soaked dark red",
    "blood-soaked": "soaked dark red",
    "bloodspatter": "dark red spatter",
    "blood spatter": "dark red spatter",
    "bloodsplatter": "dark red spatter",
    "bloody": "dark red streaked",
    "blood": "dark red staining",
    "gore": "dark wet residue",
    "gory": "dark and wet",
    "viscera": "dark wet matter",
    "entrails": "dark wet matter",
    "carnage": "wreckage and dark staining",
    "massacre": "wreckage and dark staining",
    "slaughter": "wreckage and dark staining",
    "butchered": "torn apart",
    "mutilated": "torn apart",
    "dismembered": "broken apart",
    "severed": "cut through",
    "wound": "torn surface",
    "wounds": "torn surfaces",
    "flesh": "pale surface",
    # Furniture and implements, described as objects rather than by purpose.
    "torture": "iron",
    "torture chamber": "stone room with iron fittings",
    "torture device": "iron frame",
    "execution": "iron",
    "gallows": "heavy wooden frame",
    "guillotine": "heavy wooden frame with a blade",
    "bondage": "leather-strapped",
    "restraints": "leather straps and buckles",
    "shackles": "iron cuffs and chain",
    "manacles": "iron cuffs and chain",
    "whip": "coiled leather cord",
    "whips": "coiled leather cords",
    "brothel": "lounge with curtained alcoves",
    "bordello": "lounge with curtained alcoves",
    # Substances and apparatus.
    "drugs": "small glass vials",
    "narcotics": "small glass vials",
    "syringe": "glass and steel instrument",
    "syringes": "glass and steel instruments",
    "opium": "resin and long pipes",
    # Charged abstractions a generator cannot draw anyway.
    "horrifying": "stark", "horrific": "stark", "gruesome": "stark",
    "grotesque": "misshapen", "obscene": "lurid",
    "murder": "violence",
}

# Nouns that can only be a PERSON. A sentence containing one is dropped whole,
# exactly as a sentence with a pronoun or a speech verb is -- patching the word
# would leave "The has been removed" behind, and the sentence had no place in
# an empty-room prompt to begin with.
# Per sentence, like `_PERSON_WORDS` above and for the same reason.
_BODY_WORDS = re.compile(
    r"\b(corpses?|cadavers?|dead bodies|dead body|bodies|body|"
    r"remains|nude|naked|nudity|sex|sexual|erotic|explicit|suicide)"
    r"\b",
    re.I)

_VISUAL_REGISTER_RE = re.compile(
    r"\b(" + "|".join(
        re.escape(term) for term in
        sorted(_VISUAL_REGISTER, key=len, reverse=True)
    ) + r")\b",
    re.I,
)


def to_visual_register(text):
    """Rewrite charged vocabulary into what it actually looks like.

    Applied to every text that reaches an image prompt, and to the cache key
    through the same path, so the two cannot drift.
    """
    text = str(text or "")
    if not text:
        return ""
    out = _VISUAL_REGISTER_RE.sub(
        lambda m: _VISUAL_REGISTER[m.group(0).casefold()], text)
    # Tidy the spacing a substitution can disturb.
    out = re.sub(r"\s+([,.;])", r"\1", out)
    out = re.sub(r"\s{2,}", " ", out)
    return out.strip()


# Scene fields that describe the PLACE. Everything else -- entities, positions,
# attire, conditions on people -- is omitted by construction, which is the whole
# safety argument: a monster cannot appear in a backdrop built from a
# projection that has no concept of occupants.
# `notes` is deliberately EXCLUDED despite describing the room: it is freeform
# and routinely carries occupants. Real example from live data --
#   "The TARDIS materializes in this room... Hinami and the Doctor are
#    outside it now."
# A whitelist that admits a freeform field is not a whitelist.
# `light` is part of what a place LOOKS like -- arguably the largest part, for
# a picture. A cellar at noon and the same cellar unlit are the same
# architecture and two completely different images.
_PLACE_FIELDS = ("name", "desc", "light")


def _viewer_light(scene, room_id, viewer=None):
    """The light this picture should be painted by.

    The room's ambient light when nobody is named -- but a backdrop is the room
    as the PLAYER sees it, and a player carrying a torch through a lightless
    cave is not standing in the dark. A hand light does not raise the room's
    ambient (it makes a pool, which is right for who can see whom), so asking
    the room alone would render a cave the player is lighting as pitch black,
    and would not change back when they switch the light off.
    """
    if viewer:
        lit = light_at(scene, viewer)
        if room_of(scene, viewer) == room_id:
            return lit
    return effective_light(scene, room_id)


def _light_sources_in(scene, room_id):
    """Names of the active light sources in this room, for the image prompt.

    A picture of a cave lit by a campfire and a picture of a cave lit by a
    ceiling strip are different pictures, and the difference is the source.
    Occupant-free by construction: only entities, never people's positions.
    """
    out = []
    positions = (scene or {}).get("positions") or {}
    for eid, entity in ((scene or {}).get("entities") or {}).items():
        if not isinstance(entity, dict) or not entity.get("light_source"):
            continue
        state = entity.get("state") if isinstance(entity.get("state"), dict) else {}
        if state.get("lit", True) in (False, 0, "off", "false", "no", "doused", "out"):
            continue
        name = str(entity.get("name") or eid)
        where = positions.get(eid, positions.get(name))
        if where == room_id and not any(o["name"] == name for o in out):
            out.append({
                "name": name,
                # Intensity: a candle and a floodlight are different pictures
                # of the same room.
                "emits": normalize_light(entity.get("light_source")),
                "fills_room": _light_radius_of(entity) == "room",
            })
    return out


def _light_radius_of(entity):
    declared = str((entity or {}).get("light_radius") or "").strip().casefold()
    if declared in ("room", "spot"):
        return declared
    return "spot" if (entity or {}).get("portable") else "room"


# --- the brief --------------------------------------------------------------
#
# The room record is minted once and rendered three ways -- prose by the
# composer, sight by the geometry, a picture here -- so the picture is drawn
# from the SAME fields the other two read (`docs/design/DESIGN_ROOM_FIDELITY.md`
# §4): the anchors by the wall their bearing names, the exits by wall with
# their barrier state, the proportion the extent gives, a camera at the main
# entrance, and the region's look. Every one of them is derived from
# `rooms[id]`, its edges and the region registry, and none has a concept of an
# occupant, so the whitelist argument above still holds with nothing added.

#: The walls, in the order a brief names them and a camera is chosen from.
#: Compass order, then the corners, then what stands free of any wall.
BRIEF_WALL_ORDER = ("n", "e", "s", "w", "ne", "se", "sw", "nw", "free")

#: Which entrance is the room's MAIN one when several are passable: compass
#: order, then the neighbour's id within a wall. Deterministic, so a reroll
#: frames the same room the same way. Owner-visible.
CAMERA_WALL_ORDER = ("n", "e", "s", "w")

_WALL_WORD = {"n": "north", "e": "east", "s": "south", "w": "west",
              "ne": "north-east", "se": "south-east", "sw": "south-west",
              "nw": "north-west"}

# How an anchor's geometry words read in a picture prompt -- the closed sets
# `spatial_fov` owns, rendered.
_HEIGHT_WORD = {"waist": "waist-high", "head": "head-high",
                "full": "floor to ceiling"}
_FOOTPRINT_WORD = {"small": "small", "large": "broad",
                   "run": "running the length of the wall"}

# A BRIEF DESCRIBES WHAT THE ROOM IS. An enclosed place has walls, a ceiling
# and doorways; an open one has ground, a horizon and a sky, and the ways out
# of it are where the ground goes on. The same records answer both -- anchors
# by bearing, edges by bearing, an extent, a camera -- so the difference is
# vocabulary and not structure, and `exposure` is the field that already knows
# which one this room is.
#
# Measured 2026-09-05 (PD12, the road run): `room_brief` of `bare_hilltop`
# -- `exposure: open`, under an overcast sky in the rain -- answered
# "a vast round room, about 15 paces east to west and 20 north to south",
# bucketed its scrub and turf under "walls", and put the camera at "the north
# doorway". An image made from that brief is an interior, and none of
# exposure, weather or day phase appeared in it at all.
_OPEN_HEIGHT_WORD = {"waist": "waist-high", "head": "head-high",
                     "full": "taller than a person"}
_OPEN_FOOTPRINT_WORD = {"small": "small", "large": "broad",
                        "run": "running right across the ground"}
_OPEN_GROUND = "stretch of open ground"
_OPEN_SHAPE = {"round": "roughly circular", "l": "L-shaped",
               "composite": "irregularly shaped"}
_OPEN_WAY_WORD = {
    "open": "the ground carries on", "open_door": "an open gateway",
    "closed_door": "a shut gateway", "window": "a window",
    "bars": "a barred opening", "membrane": "a hanging way through",
    "one_way_window": "a dark pane"}
#: What being under the sky adds to a picture, by exposure. `enclosed` says
#: nothing: a room with a roof and no sky in it is the case the brief already
#: described correctly.
_EXPOSURE_PHRASE = {
    "open": "in the open air, the horizon past the edges of the ground",
    "sheltered": "under cover, open to the air at the sides",
}


def _walls_of(scene, room_id):
    """{wall: [{desc, height?, footprint?}]} -- the room's AUTHORED anchors
    grouped by the wall their bearing names; `free` for one with no bearing.
    Implicit door anchors are openings, not walls, and are not here. An
    anchor whose description names a person is dropped whole, the way a room
    sentence is (`_setting_only`), because the picture is of an empty room."""
    room = ((scene or {}).get("rooms") or {}).get(room_id) or {}
    anchors = room.get("anchors") if isinstance(room.get("anchors"), dict) else {}
    out = {}
    for aid in sorted(anchors):
        anchor = anchors[aid]
        if not isinstance(anchor, dict) or anchor.get("implicit"):
            continue
        desc = to_visual_register(_setting_only(str(anchor.get("desc") or aid)))
        if not desc:
            continue
        rec = {"desc": desc}
        if str(anchor.get("height") or "").strip():
            rec["height"] = normalize_height(anchor.get("height"))
        if str(anchor.get("footprint") or "").strip():
            rec["footprint"] = normalize_footprint(anchor.get("footprint"))
        out.setdefault(normalize_bearing(anchor.get("dir")) or "free", []).append(rec)
    return out


def _openings_of(scene, room_id):
    """{wall: [{barrier, name?, vertical?}]} -- every doorway of the room,
    declared from either side (`effective_adjacent`), by the wall it opens in;
    `unplaced` for one with no bearing. Never `to`: where a door LEADS is
    somebody's whereabouts, not the room's fabric. Sorted by the neighbour's
    id before the id is dropped, so the order is deterministic."""
    edges = [e for e in effective_adjacent(scene or {}, room_id)
             if isinstance(e, dict) and e.get("to")]
    out = {}
    for edge in sorted(edges, key=lambda e: str(e["to"])):
        barrier = normalize_barrier(edge.get("barrier"))
        if barrier == "wall":
            continue
        rec = {"barrier": barrier}
        name = to_visual_register(_setting_only(str(edge.get("name") or "")))
        if name:
            rec["name"] = name
        vertical = normalize_vertical(edge.get("vertical"))
        if vertical:
            rec["vertical"] = vertical
        out.setdefault(normalize_bearing(edge.get("dir")) or "unplaced",
                       []).append(rec)
    return out


def _proportion_of(scene, room_id, outdoors=False):
    """One sentence for how much floor there is and how it is shaped, or ''
    when nothing was measured or authored -- a tier the engine only guessed
    is not asserted to the picture. `outdoors` says the same measurements in
    the vocabulary an open place has: ground, not floor and walls."""
    room = ((scene or {}).get("rooms") or {}).get(room_id) or {}
    grid = room_grid(scene or {}, room_id)
    authored = str(room.get("size") or "").strip().casefold() in ROOM_SIZES
    if not grid.measured and not authored:
        return ""
    size = effective_room_size(scene or {}, room_id)
    # `composite` is any union of rectangles that is not the two-part L: the
    # picture is told the floor is irregular and left to the walls sentence
    # for where it turns, since a shape word for every union does not exist.
    if outdoors:
        shape = " ".join(
            w for w in (_OPEN_SHAPE.get(grid.shape, ""), _OPEN_GROUND) if w)
    else:
        shape = {"round": "round room", "l": "L-shaped room",
                 "composite": "irregularly shaped room"}.get(grid.shape, "room")
    if not grid.measured:
        return "a %s %s" % (size, shape)
    long_side, short_side = max(grid.w, grid.d), min(grid.w, grid.d)
    ratio = long_side / float(short_side)
    if ratio >= 2.0:
        proportion = "long and narrow" if grid.d > grid.w else "wide and shallow"
    elif ratio >= 4.0 / 3.0:
        proportion = "deeper than it is wide" if grid.d > grid.w \
            else "wider than it is deep"
    else:
        proportion = "roughly square"
    return ("a %s %s, about %d paces east to west and %d north to south, %s"
            % (size, shape, grid.w, grid.d, proportion))


def _part_of_room(cell, grid, outdoors=False):
    """Where in the room a cell is, as a person would say it: thirds on each
    axis -- "the north-west part", "the middle of the south side", "the
    middle". Outdoors the same thirds are named against the ground."""
    place = _OPEN_GROUND if outdoors else "room"
    x, y = cell
    col = "west" if x < grid.w / 3.0 else "east" if x >= 2 * grid.w / 3.0 else ""
    row = "north" if y < grid.d / 3.0 else "south" if y >= 2 * grid.d / 3.0 else ""
    if row and col:
        return "the %s-%s part of the %s" % (row, col, place)
    if row or col:
        return "the middle of the %s side" % (row or col)
    return "the middle of the %s" % place


def _camera_of(scene, room_id, openings, viewer=None, viewer_camera=False,
               outdoors=False):
    """Where the picture is taken from: the room's MAIN ENTRANCE looking in
    -- the first passable doorway in `CAMERA_WALL_ORDER` -- level and wide;
    or, behind `backdrop_continuity` (`viewer_camera`), the viewer's own
    measured cell and facing, so a room with continuity on is the same room
    turned rather than a new one. None when no passable doorway has a wall
    to be placed in: the prompt then says nothing about a camera.

    The viewer camera COSTS pictures: one per (part of the room, facing) the
    viewer stands in, up to nine parts by eight facings, where the entrance
    camera is one picture per visible state. It is behind the setting for
    exactly that reason (DESIGN_ROOM_FIDELITY §4).
    """
    if viewer_camera and viewer and room_of(scene or {}, viewer) == room_id:
        cell = body_cell(scene or {}, viewer)
        facing = effective_facing(scene or {}, viewer)
        if cell and facing:
            return {"from": _part_of_room(cell, room_grid(scene or {}, room_id),
                                          outdoors),
                    "looking": _WALL_WORD.get(facing, facing),
                    "framing": "eye level, wide"}
    # A CAMERA STANDS IN A DOORWAY AND LOOKS LEVEL ACROSS THE ROOM, so a
    # VERTICAL way is not a place it can stand: a stair, a ladder, a hatch or
    # a shaft is a way up or down, and there is no level, wide shot to be
    # taken from inside one. Measured (PR14,
    # `docs/experiments/PLAY_2026_09_05C_rush.md`): the brief for a landing
    # at the top of a burning stairwell put the camera in "the north
    # doorway" looking south, level and wide -- the north doorway being the
    # stair going down into the flashover. Where every passable way out is
    # vertical the answer is None, which is this function's documented "say
    # nothing about a camera" rather than a worse picture.
    for wall in CAMERA_WALL_ORDER:
        for opening in openings.get(wall) or []:
            if opening.get("vertical"):
                continue
            if opening.get("barrier") in _PASSABLE_BARRIERS:
                return {"from": ("the %s edge of the %s"
                                 % (_WALL_WORD[wall], _OPEN_GROUND))
                                if outdoors
                                else "the %s doorway" % _WALL_WORD[wall],
                        "looking": _WALL_WORD[opposite_bearing(wall)],
                        "framing": "level, wide"}
    return None


def _sky_of(scene, room_id, exposure):
    """The three facts that decide an outdoor picture, or {} for a room with
    no sky over it: how much of it this place stands under, what time of day
    the light is, and what is coming down. Every one is already on the scene;
    PD12 measured that none of them reached the brief."""
    if exposure not in _EXPOSURE_PHRASE:
        return {}
    out = {"exposure": exposure}
    bucket = time_bucket((scene or {}).get("time_of_day"))
    if bucket:
        out["time"] = bucket
    words = weather_words(weather_for_room(scene or {}, room_id), "sight")
    if words:
        out["weather"] = list(words)
    return out


def room_brief(scene, room_id, viewer=None, *, regions=None,
               viewer_camera=False):
    """The structured brief: {walls, openings, proportion, camera, look},
    each present only when it has something to say, so a room with none of
    them projects and hashes exactly as it did before the brief existed.
    `regions` is the frame's region registry (`world.regions.region_registry`),
    read for the region's `look`; the projection stays pure over it.

    An OPEN room is briefed as the place it is: {ground, ways, proportion,
    camera, sky, look}. Same records, same structure, the vocabulary an
    outdoors has -- and `sky`, which carries the exposure, the day phase and
    the weather that decide an outdoor picture. An enclosed room's brief is
    untouched, keys and text, so its cache key is the one it had.
    """
    scene = scene or {}
    out = {}
    exposure = room_exposure(scene, room_id)
    outdoors = exposure == "open"
    walls = _walls_of(scene, room_id)
    if walls:
        out["ground" if outdoors else "walls"] = walls
    openings = _openings_of(scene, room_id)
    if openings:
        out["ways" if outdoors else "openings"] = openings
    proportion = _proportion_of(scene, room_id, outdoors)
    if proportion:
        out["proportion"] = proportion
    camera = _camera_of(scene, room_id, openings, viewer, viewer_camera,
                        outdoors)
    if camera:
        out["camera"] = camera
    sky = _sky_of(scene, room_id, exposure)
    if sky:
        out["sky"] = sky
    if regions:
        from world.regions import room_region
        region = room_region(scene, room_id)
        entry = regions.get(region) if region else None
        look = to_visual_register(_setting_only(
            str((entry or {}).get("look") or ""))) if isinstance(entry, dict) \
            else ""
        if look:
            out["look"] = look
    return out


def room_projection(scene, room_id, viewer=None, *, regions=None,
                    viewer_camera=False):
    """A whitelisted, occupant-free description of one room.

    Deliberately a whitelist rather than a filter: adding a new scene field
    cannot silently start leaking people into backdrops, because anything not
    named here is simply absent. The brief (`room_brief`) is part of the
    whitelist: walls, openings, proportion, camera and look, each derived from
    the room record and its edges alone. `lighting` is a RESERVED slot -- a
    lighting sentence the light field may supply -- and is not computed here.
    """
    scene = scene or {}
    room = ((scene.get("rooms") or {}).get(room_id) or {})
    out = {k: room.get(k) for k in _PLACE_FIELDS if room.get(k)}
    out.update(room_brief(scene, room_id, viewer, regions=regions,
                          viewer_camera=viewer_camera))
    # What the room is ACTUALLY lit by, not just what it was built with: a
    # campfire, a lantern set down, a burning wreck. Without this a cellar lit
    # by a fire someone built still renders pitch black.
    out["light"] = _viewer_light(scene, room_id, viewer)
    lights = _light_sources_in(scene, room_id)
    if lights:
        out["light_sources"] = lights
    # `desc` is the richest field and was assumed to be pure architecture. Live
    # data says otherwise -- mapping writes occupants into it ("Crew members
    # and civilians gather here...") -- so it goes through the same
    # people-stripping filter as the optional prose flavour. Belt and braces
    # over the whitelist, exactly like the "no people" instruction in the
    # prompt: whichever one is imperfect, a person still has to get past both.
    # No raw-text fallback when stripping empties it: a description made
    # entirely of occupants must yield NO description, not the occupants back.
    if out.get("desc"):
        out["desc"] = place_desc(room)
        if not out["desc"]:
            out.pop("desc")
    if out.get("light"):
        out["light"] = normalize_light(out["light"])
    out["room"] = room_id
    # scene.location is NOT included -- but NOT because the engine is broken.
    # It tracks relocation correctly since TR-3 (checkpoints after that fix
    # read "Corridor, Deck 10", "Ten Forward", "Turbolift Car" in step with the
    # player's room). The reason to exclude it is that backdrops are also
    # rendered for HISTORICAL turns when scrolling back, and checkpoints
    # written before that fix carry a stale label -- the Enterprise's janitor
    # closet still reads "Back Alley, City". A wrong one-line location would
    # render a starship cupboard as a city alley, and the room description
    # already says "standard starship deck plating", so it earns nothing.
    bucket = time_bucket(scene.get("time_of_day"))
    if bucket:
        out["time"] = bucket
    # Adjacency as pure layout: which way the room opens, never who is through
    # the door.
    exits = []
    for edge in (room.get("adjacent") or []):
        if not isinstance(edge, dict):
            continue
        # `name` rides along because it is pure layout too, and it is the only
        # field that says what the way out IS. A backdrop drawn from
        # {barrier, vertical, dir} alone can put an opening in the north wall
        # and cannot know it is a staircase.
        exits.append({k: edge[k] for k in ("barrier", "vertical", "dir", "name")
                      if edge.get(k)})
    if exits:
        out["exits"] = exits
    # Per-room visual overlays (smoke, darkness, wreckage) DO belong: they
    # change what the place looks like. Overlays keyed to a PERSON never reach
    # here because the lookup is by room id.
    overlay = (scene.get("overlays") or {}).get(room_id)
    if overlay:
        out["overlays"] = overlay
    # Weather, scoped to what this room is standing under. A room with no sky
    # gets no entry at all rather than an empty one, so the prompt cannot
    # acquire a "no weather" clause it would then try to paint.
    weather = weather_for_room(scene, room_id)
    words = weather_words(weather, "sight")   # never the audible-only phrases
    if words:
        out["weather"] = words
        out["exposure"] = weather.get("exposure")
    return out


def player_view_for_turn(chat_id, turn_idx):
    """The player's own perceived prose for a turn, or ''.

    Reads the committed step exactly as the narrator saw it. Never touches
    scene.rooms[...].desc -- see this module's docstring.
    """
    row = q(
        "SELECT v.content FROM turns t "
        "JOIN steps s ON s.turn_id=t.id "
        "JOIN variants v ON v.step_id=s.id AND v.active=1 "
        "WHERE t.chat_id=? AND t.idx=? AND s.key IN "
        "('perception_outcome','perception_establish') "
        "ORDER BY s.ord DESC LIMIT 1",
        (chat_id, turn_idx), one=True)
    if not row:
        return ""
    try:
        views = (json.loads(row["content"]) or {}).get("views") or {}
    except (ValueError, TypeError):
        return ""
    view = views.get("player")
    if isinstance(view, dict):
        view = view.get("view") or view.get("text") or ""
    return str(view or "")


def arrival_turn_for_room(chat_id, turn_idx, room_id, player_name=None,
                          lookback=25):
    """The most recent turn at or before `turn_idx` where the player was NOT
    yet in `room_id` -- i.e. the beat they arrived on, whose view is the
    "you step in and see" description.

    A mid-scene view is mostly people talking; the arrival view is where the
    place itself gets described, which is what a backdrop needs. Bounded
    lookback so a long stay in one room cannot walk the whole history.
    """
    # Per-turn scene lives in `checkpoints.blob`, not in a step: this chat has
    # no `outcome_scene` step at all, and the first draft queried for one,
    # silently found nothing, and fell back to the current turn every time.
    # Blobs are megabytes each and this walks up to eight of them, which is
    # most of what the backdrop route costs. Asking for only `positions` and
    # `player_room` instead of the whole scene was tried and MEASURED WORSE:
    # two json_extract paths make SQLite walk the blob twice where
    # `scene_after_turn` walks it once. The real fix is the per-turn room index
    # named above, or a cache keyed on `checkpoints.created` -- neither of
    # which is a one-liner, and both of which want their own tests.
    arrival = turn_idx
    for idx in range(turn_idx, max(-1, turn_idx - max(1, min(int(lookback), 8))), -1):
        scene = scene_after_turn(chat_id, idx)
        if _room_of_player(scene, player_name) == room_id:
            arrival = idx
        else:
            break
    return arrival


def arrival_flavour(chat_id, turn_idx, room_id, player_name=None):
    """Optional atmosphere for an image prompt, from the ARRIVAL beat.

    Mid-scene prose is people talking; arrival prose describes the place. People
    and speech are stripped. A supplement only -- `place` is the source of
    record, so a thin or empty string costs the picture nothing.

    IT IS SEPARATE FROM `build_backdrop_request` BECAUSE IT IS EXPENSIVE AND THE
    READ PATH DOES NOT WANT IT. `arrival_turn_for_room` walks up to eight
    per-turn checkpoints backwards, and on a real story those blobs are ~4.7MB
    each -- so computing this cost up to ~38MB of JSON parsing. Measured on chat
    67 it was 0.548s of the 0.758s that seventeen `build_backdrop_request` calls
    took: 72% of the read path, spent on a field only `generate_backdrop` reads.

    Worse, it GREW with a stay: the lookback walks further back the longer the
    player has been in one room, so the same seventeen turns cost 56ms at the
    beat of arrival and 146ms five beats later. `GET /api/turns/{id}/backdrop`
    is polled while the reader scrolls and serves cache hits, so a picture that
    was already on disk paid all of that before it could be shown -- which is
    exactly what "it used to load instantly" describes, on a story whose
    checkpoints have since grown to megabytes.
    """
    return to_visual_register(_setting_only(player_view_for_turn(
        chat_id, arrival_turn_for_room(chat_id, turn_idx, room_id,
                                       player_name))))


def _turn_frame(chat_id, turn_idx):
    row = q("SELECT frame_id FROM turns WHERE chat_id=? AND idx=?",
            (chat_id, turn_idx), one=True)
    return row["frame_id"] if row else None


def _regions_for(chat_id, turn_idx):
    """The frame's region registry for the brief's `look`, or {} when it
    cannot be read -- a backdrop never fails for want of a district."""
    try:
        from world.regions import region_registry
        return region_registry(chat_id, _turn_frame(chat_id, turn_idx)) or {}
    except Exception:
        return {}


def scene_after_turn(chat_id, turn_idx):
    """The scene as it stood AFTER `turn_idx` resolved.

    Checkpoints are written BEFORE a turn runs, so checkpoint N is the state
    going INTO turn N -- the state coming out of turn N is checkpoint N+1, or
    the live scene when N is the latest turn. Mixing the two reads a room the
    player has already left, which is exactly how an earlier draft "found" a
    frame-scoping bug that did not exist.
    """
    # Only the scene, not the whole world blob it sits in. A checkpoint is
    # megabytes -- lore caches, relationship maps, everything pending -- and the
    # scene is about one percent of it, so parsing the rest was work thrown away
    # on every read of a route the reader's scrolling polls. Measured 25.4ms ->
    # 15.0ms on the largest checkpoint in this database, same result.
    try:
        row = q("SELECT json_extract(blob,'$.world.scene') AS scene "
                "FROM checkpoints WHERE chat_id=? AND turn_idx=?",
                (chat_id, turn_idx + 1), one=True)
    except Exception:
        # A blob SQLite cannot parse is one this cannot use either. Falling
        # through to the live scene is what the json.loads below did with the
        # same input; it must not become a failed request now that the parse
        # happens in the query.
        row = None
    if row and row["scene"] is not None:
        try:
            scene = row["scene"]
            if isinstance(scene, str):
                scene = json.loads(scene)
            if isinstance(scene, dict):
                return scene
        except (ValueError, TypeError):
            pass
    return wget_for_frame(chat_id, "scene", _turn_frame(chat_id, turn_idx),
                          {}) or {}


def build_backdrop_request(chat_id, turn_idx, player_name=None, style=None):
    """Everything needed to generate (or serve from cache) one backdrop.

    Returns `{room, room_name, signature, cached, place, time, location,
    weather}`, or None when there is no room to depict. `place` is the
    structured, occupant-free room projection an image prompt is written from.

    There is NO `flavour` key and no cheaper name for one: the
    perception-derived setting text used to be computed here and was moved out
    for the reason spelled out in `arrival_flavour`, so the one caller that
    needs it builds it for itself, past every cache check. This dict is the
    READ path, which serves cache hits and never writes a prompt.
    """
    scene = scene_after_turn(chat_id, turn_idx)
    room_id = _room_of_player(scene, player_name)
    if not room_id:
        return None
    # The region registry, for the brief's `look`; and whether the camera
    # may follow the viewer (behind `backdrop_continuity`, see `_camera_of`).
    regions = _regions_for(chat_id, turn_idx)
    viewer_camera = _continuity_enabled()
    signature = visual_signature(scene, room_id, style, viewer=player_name,
                                 regions=regions, viewer_camera=viewer_camera)
    room = ((scene.get("rooms") or {}).get(room_id) or {})
    return {
        "room": room_id,
        "room_name": room.get("name") or room_id,
        "signature": signature,
        "cached": cached_backdrop(chat_id, signature),
        # Structured, occupant-free: this is what an image prompt is written
        # from. Rich (architecture, light, exits, damage) and safe by
        # construction (no entities, no positions, no people).
        "place": room_projection(scene, room_id, viewer=player_name,
                                 regions=regions, viewer_camera=viewer_camera),
        # `flavour` USED TO BE COMPUTED HERE, and it was by far the most
        # expensive thing this function did -- see `arrival_flavour`, which the
        # one caller that needs it now calls for itself. Nothing else may put
        # it back: this dict is built on the READ path, which serves cache hits
        # and never writes a prompt.
        # NO raw time key. The scene's time of day reaches the prompt through
        # `place` (bucketed, like every other visual-state field), and the
        # unbucketed copy that used to sit here was read by nobody: not
        # `_backdrop_payload`, not the frontend, not the preview tool. A field
        # nothing reads is worse than no field -- it is the reason the corrupt
        # value went unnoticed here for as long as it did.
        "location": scene.get("location") or "",
        # For the weather overlay (static/js/weather-fx.js), which draws only
        # where the sky can actually be seen. Handed over as the SCOPED answer
        # rather than the scene's raw weather, so the frontend cannot draw rain
        # into a cellar by reading the wrong field.
        "weather": weather_for_room(scene, room_id),
    }


# --- prompt composition and generation ------------------------------------
#
# Both stages are OPTIONAL and out of band. Nothing here is ever called from
# the turn pipeline: a slow image, a failed prompt or a provider outage must
# never sit between the player and their prose.

# Style words that keep a backdrop reading as a BACKDROP: an establishing shot
# of an empty place, not a dramatic composition competing with the text laid
# over it.
_BACKDROP_STYLE = (
    "wide establishing shot of an empty room, no people, no figures, "
    "no text or lettering, environment concept art, muted contrast, "
    "nothing in sharp focus in the centre foreground"
)


# How each light level should be PAINTED. "dark" is the interesting one: an
# unlit room is not a black rectangle, it is a room rendered by whatever little
# light reaches it, which is what makes a usable backdrop rather than a void.
_LIGHT_PROMPT = {
    "dark": ("unlit, near-total darkness, deep shadow with only faint edges "
             "picked out, barely legible forms"),
    "dim": "dimly lit, low warm light, long shadows, muted detail",
    "bright": "harshly lit, strong bright light, blown highlights, hard shadows",
}


# How a source of a given strength paints a space. A candle in a cave and a
# floodlit hangar are the same instruction ("there is a light") only if you do
# not look: intensity decides how much of the room the picture even contains.
_SOURCE_LOOK = {
    "dim": ("a small pool of warm light around it, falling off fast into deep "
            "shadow, most of the space unlit"),
    "lit": "casting steady light across the space, shadows thrown outward",
    "bright": ("throwing harsh light, blown highlights near it and hard black "
               "shadows beyond"),
}


def _source_lighting(place):
    """Prompt fragments naming what is lighting the room, and how strongly."""
    sources = place.get("light_sources") or []
    if not sources:
        return []

    names = ", ".join(str(s.get("name") or "") for s in sources if s.get("name"))
    if not names:
        return []

    # The strongest source sets the look; a candle beside a bonfire does not
    # get a say in how the picture reads.
    strongest = max(
        sources,
        key=lambda s: {"dark": 0, "dim": 1, "lit": 2, "bright": 3}.get(
            s.get("emits"), 2),
    )
    look = _SOURCE_LOOK.get(strongest.get("emits") or "lit", "")
    fragment = "lit by " + names
    if look:
        fragment += ", " + look
    # A hand light in an otherwise dark room is the whole composition: say so,
    # or the model paints an evenly lit room with a torch in it.
    if not strongest.get("fills_room") and \
            normalize_light(place.get("light")) in ("dark", "dim"):
        fragment += ("; the light source is the only illumination and the room "
                     "beyond it is dark")
    return [fragment]


def _wall_phrase(wall, outdoors=False):
    if wall in _WALL_WORD:
        return ("to the %s" % _WALL_WORD[wall]) if outdoors \
            else "%s wall" % _WALL_WORD[wall]
    if wall == "free":
        return "standing out in the open" if outdoors \
            else "standing free of the walls"
    return ""


def _brief_sentences(place):
    """The walls and openings of a brief as prompt fragments, then the
    camera. One fragment per wall that has anything on it or through it.

    An open place's brief carries the same two groupings under `ground` and
    `ways` (`room_brief`), and is rendered in the vocabulary an outdoors has:
    a bearing is a side and not a wall, a passable edge is where the ground
    carries on, and the floor the camera leaves empty is the ground."""
    outdoors = "ground" in place or "ways" in place or "sky" in place
    walls = place.get("ground") or place.get("walls") or {}
    openings = place.get("ways") or place.get("openings") or {}
    height_word = _OPEN_HEIGHT_WORD if outdoors else _HEIGHT_WORD
    footprint_word = _OPEN_FOOTPRINT_WORD if outdoors else _FOOTPRINT_WORD
    way_word = _OPEN_WAY_WORD if outdoors else {
        "open": "an opening", "open_door": "an open doorway",
        "closed_door": "a closed door", "window": "a window",
        "bars": "a barred opening", "membrane": "a curtained way",
        "one_way_window": "a dark pane"}
    out = []
    for wall in BRIEF_WALL_ORDER + ("unplaced",):
        items = []
        for anchor in walls.get(wall) or []:
            words = str(anchor.get("desc") or "")
            qualifiers = [q for q in (height_word.get(anchor.get("height")),
                                      footprint_word.get(anchor.get("footprint")))
                          if q]
            if qualifiers:
                words += " (%s)" % ", ".join(qualifiers)
            items.append(words)
        for opening in openings.get(wall) or []:
            what = opening.get("name") or way_word.get(
                opening.get("barrier"), "a way through")
            if opening.get("vertical"):
                what += " leading %s" % opening["vertical"]
            items.append(what)
        if not items:
            continue
        where = _wall_phrase(wall, outdoors)
        out.append(("%s: %s" % (where, ", ".join(items))) if where
                   else ", ".join(items))
    sky = place.get("sky") or {}
    phrase = _EXPOSURE_PHRASE.get(sky.get("exposure"))
    if phrase:
        out.append(phrase)
    camera = place.get("camera")
    if camera:
        out.append("seen from %s looking %s, %s, the middle of the %s empty"
                   % (camera.get("from"), camera.get("looking"),
                      camera.get("framing"),
                      "ground" if outdoors else "floor"))
    return out


def compose_prompt(place, style=None, flavour=""):
    """A deterministic image prompt from the whitelisted place projection.

    Used as-is when no `backdrop_prompt` model is configured, and as the input
    to that agent when one is. Deterministic on purpose: the feature must work,
    and be testable, with no extra model call at all.
    """
    parts = []
    if place.get("name"):
        parts.append(str(place["name"]))
    if place.get("proportion"):
        parts.append(str(place["proportion"]))
    if place.get("desc"):
        parts.append(str(place["desc"]))
    # FROM THE WALLS OUTWARD: what stands on each wall and what opens in it,
    # then where the picture is taken from, with the middle of the floor
    # left empty for the text. The brief is structured so the agent card can
    # compose rather than guess (`backdrop_prompt.txt`).
    parts.extend(_brief_sentences(place))
    if place.get("look"):
        parts.append("in the manner of the district: %s" % place["look"])
    if place.get("overlays"):
        parts.append(", ".join(str(o) for o in place["overlays"]))
    if place.get("weather"):
        parts.append(", ".join(str(w) for w in place["weather"]))
    if place.get("time"):
        parts.append("time: %s" % place["time"])
    # Lighting, in words an image model acts on. Omitted at "lit", which is the
    # default and needs no instruction -- saying "normally lit" would only
    # compete with whatever the description already implies. A `lighting`
    # sentence in the brief (the light field's slot) is used in place of the
    # level word when present; it is never computed here.
    if place.get("lighting"):
        parts.append(str(place["lighting"]))
    else:
        lighting = _LIGHT_PROMPT.get(normalize_light(place.get("light")))
        if lighting:
            parts.append(lighting)
    parts.extend(_source_lighting(place))
    if flavour:
        parts.append(flavour)
    for key in ("tone",):
        if (style or {}).get(key):
            parts.append("%s: %s" % (key, style[key]))
    parts.append(_BACKDROP_STYLE)
    if (style or {}).get("avoid"):
        parts.append("avoid: %s" % style["avoid"])
    return " | ".join(p for p in parts if p)


# What a REVISION asks for, as opposed to a generation. The two read the same
# spatial state and use it in opposite directions: a generation prompt has to
# describe the whole place, because nothing exists yet and every omission is
# something the model will invent. A revision prompt has to describe the
# CHANGE, because the place already exists in the image it is handed, and every
# detail restated is a detail the model is invited to redraw differently.
#
# Handing the generation prompt to an edit endpoint -- which is what the first
# version of this did -- is the whole feature defeated: "a stone courtyard,
# flagstones, a well, overcast" tells the model to draw a stone courtyard, and
# it happily draws a different one.
_REVISION_PREFACE = (
    "Revise the supplied image of this exact place. Keep its architecture, "
    "layout, materials, furnishings, camera angle and framing EXACTLY as they "
    "are -- this is the same room, a moment later, not a new view of it. "
    "Change only what follows")
_REVISION_CLOSE = (
    "Do not add, remove or rearrange anything else. No people.")

# The fields that describe a room's STATE rather than its fabric: what a
# revision is allowed to talk about. `name`/`desc` are deliberately absent --
# they are the fabric, they are already in the picture, and restating them is
# how a revision turns back into a generation.
_REVISION_STATE_KEYS = ("overlays", "weather", "ground")


def compose_revision(place, style=None, previous=None):
    """The prompt for editing a room's existing image into its new state.

    `previous` is the place projection the anchor image was drawn from, when it
    is known; without it every state field is treated as new, which is
    conservative in the right direction (it restates the weather rather than
    silently assuming the picture already has it).
    """
    changes = []
    for key in _REVISION_STATE_KEYS:
        value = place.get(key)
        if not value:
            continue
        if (previous or {}).get(key) == value:
            continue          # already true of the image; saying so risks a redraw
        if isinstance(value, (list, tuple)):
            value = ", ".join(str(v) for v in value)
        changes.append("%s: %s" % (key, value))
    lighting = _LIGHT_PROMPT.get(normalize_light(place.get("light")))
    if lighting and (previous or {}).get("light") != place.get("light"):
        changes.append(lighting)
        changes.extend(_source_lighting(place))
    if place.get("time") and (previous or {}).get("time") != place.get("time"):
        changes.append("time of day: %s" % place["time"])
    if not changes:
        # Nothing about the state has moved, so the only honest instruction is
        # "the same room again" -- which is what a caller with an anchor and no
        # delta should be asking for.
        changes.append("nothing; reproduce the same room faithfully")
    parts = ["%s: %s." % (_REVISION_PREFACE, "; ".join(changes)), _REVISION_CLOSE]
    if (style or {}).get("avoid"):
        parts.append("avoid: %s" % style["avoid"])
    return " ".join(parts)


def refine_prompt(draft, place):
    """Optionally rewrite the deterministic draft with the `backdrop_prompt`
    model. Returns the draft unchanged if no model is configured or the call
    fails -- this is a nicety, never a dependency."""
    try:
        from llm.providers import resolve_role_candidates
        resolve_role_candidates("backdrop_prompt")
    except Exception:
        return draft
    try:
        from agents.common import _agent_json
        from language_runtime import DEFAULT_LANGUAGE
        from llm.prompts import get_prompt
        out = _agent_json("backdrop_prompt", "backdrop_prompt",
                          # Pinned to English: this produces an IMAGE-MODEL PROMPT, which
                          # the backends are trained on in English, not reader-facing
                          # prose. Same reasoning as ambience.py.
                          get_prompt("backdrop_prompt", DEFAULT_LANGUAGE),
                          {"place": place, "draft": draft}, temperature=0.6)
        refined = str((out or {}).get("prompt") or "").strip()
        return refined or draft
    except Exception:
        return draft


# Generation is slow and costs real money, and the same signature is very
# easy to request twice at once: two turns in the same room become visible
# together, the player scrolls back and forth, a second browser tab is open.
# A per-signature lock makes the second caller WAIT for the first and then
# take the cache hit instead of paying for the identical picture twice.
#
# This dict used to be kept forever -- "one small entry per distinct room-state
# seen in a process lifetime", pruned by nothing, because pruning it would race
# with the waiters. The premise was right and the conclusion was not: a thread
# blocked on a lock leaves no evidence it wants that lock, so the holder cannot
# tell if anyone is behind it, but a waiter that counts itself in before it
# releases the guard IS that evidence. `outofband.KeyedLocks` does exactly that
# and drops an entry only at zero. Measured on the old code: 500 distinct
# signatures left 500 entries standing with no work in flight.
_GEN_LOCKS = outofband.KeyedLocks()


def _generation_lock(key):
    """Exclusive use of one signature, for as long as the `with` block runs."""
    return _GEN_LOCKS.hold(key)


# --- continuity ------------------------------------------------------------
#
# A room's SECOND picture should be its first one with the light changed, not a
# fresh invention of the same place. Left to plain text-to-image, every state
# of a room -- lit, dark, wet, wrecked -- is generated from scratch, and they
# come back with different architecture, different furniture and a different
# window. Handing the model the room's existing image fixes that.
#
# The image handed over is the room's ANCHOR: the first one that ever succeeded
# for that room, not the most recent. Editing the most recent would compound
# every artifact down a chain of edits until the tenth state of a room is a
# photocopy of a photocopy; editing the anchor keeps every variant one step
# from the same original.

_ANCHOR_INDEX = "rooms.json"


def _anchor_path(chat_id):
    return os.path.join(BACKDROP_DIR, str(chat_id), _ANCHOR_INDEX)


def room_anchor(chat_id, room_id):
    """The image every state of this room is a variant of, and the projection
    it was drawn from -- (path, place) or (None, {}).

    The projection matters as much as the picture: a revision prompt has to say
    what CHANGED, and it can only do that against what the anchor already
    shows.

    Walks the branch lineage like `cached_backdrop` does, so a branch inherits
    its parent's rooms rather than re-inventing them at the fork.
    """
    if not room_id:
        return None, {}
    for cid in [chat_id] + branch_lineage(chat_id):
        try:
            with open(_anchor_path(cid), "r", encoding="utf-8") as fh:
                index = json.load(fh)
        except (OSError, ValueError):
            continue
        entry = (index or {}).get(str(room_id))
        if isinstance(entry, str):        # the first shape: signature alone
            entry = {"signature": entry}
        if not isinstance(entry, dict) or not entry.get("signature"):
            continue
        path = cached_backdrop(cid, entry["signature"])
        if path:
            return path, (entry.get("place") or {})
    return None, {}


def set_room_anchor(chat_id, room_id, signature, place=None):
    """Remember this image as the room's anchor, if it has none yet. Written
    once and never rewritten: an anchor that drifted would defeat its purpose."""
    if not room_id or not signature:
        return
    path = _anchor_path(chat_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            index = json.load(fh)
        if not isinstance(index, dict):
            index = {}
    except (OSError, ValueError):
        index = {}
    if index.get(str(room_id)):
        return
    index[str(room_id)] = {"signature": signature, "place": place or {}}
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def _continuity_enabled():
    """Off unless the host has explicitly switched it on.

    Not a default, because it changes HOW every picture after the first is
    made: an edit of the room's first image rather than a fresh generation.
    That is the point when it works, and when a provider's edit endpoint is
    poor it quietly degrades every backdrop in the story -- which is not
    something to discover from a default. It also cannot be verified from here:
    the endpoint's existence is checkable, the quality of what it returns is
    not.
    """
    from core.db import get_setting

    value = str(get_setting("backdrop_continuity") or "").strip().casefold()
    return value in ("1", "on", "true", "yes")


def generate_backdrop(chat_id, turn_idx, player_name=None, style=None,
                      force=False, work=None):
    """Produce (or serve from cache) the backdrop for a turn.

    Returns {path, signature, room, prompt, cached}, or None when there is no
    room to depict and when `work` was cancelled -- in both of those cases
    there is no image and none was promised. The prompt is handed to the image
    generator automatically -- composing and generating are one operation from
    the caller's point of view.

    `work` is the queue's handle when this is running out of band, and None for
    every direct blocking caller. It is only ever read, at the step boundaries
    below; nothing here can be cancelled mid-flight.
    """
    from llm.providers import edit_image, generate_image

    req = build_backdrop_request(chat_id, turn_idx, player_name, style)
    if not req:
        return None
    if req["cached"] and not force:
        return {"path": req["cached"], "signature": req["signature"],
                "room": req["room_name"], "prompt": None, "cached": True}

    with _generation_lock((chat_id, req["signature"])):
        # Re-check inside the lock: whoever held it may have just written
        # exactly the image this call was about to pay for.
        existing = cached_backdrop(chat_id, req["signature"])
        if existing and not force:
            return {"path": existing, "signature": req["signature"],
                    "room": req["room_name"], "prompt": None, "cached": True}

        # Between steps, never mid-flight. Everything past this line costs
        # money or minutes, and the commonest way to arrive here already
        # cancelled is the one the lock above creates: several callers queued
        # on one signature, released one at a time, for a picture nobody is
        # looking at any more.
        if outofband.stopped(work):
            return None

        # Computed HERE, past every cache check and inside the lock, because it
        # is the expensive part of the old request dict and only a call that is
        # actually going to draw needs it. `req.get` is not a fallback for a
        # missing key -- the key is gone; this is the one place it is made.
        flavour = arrival_flavour(chat_id, turn_idx, req.get("room"),
                                  player_name)
        prompt = refine_prompt(
            compose_prompt(req["place"], style, flavour), req["place"])
        # Same room, new state: modify the picture that already exists rather
        # than inventing the place again. Any failure here -- a provider with
        # no edits endpoint, a model that refuses one, a corrupt anchor -- is a
        # reason to generate normally, never a reason to have no backdrop.
        anchor, anchor_place = (room_anchor(chat_id, req.get("room"))
                                if _continuity_enabled() else (None, {}))
        # The second boundary, and the one that matters most: `refine_prompt`
        # may itself have been a model call, and the generation below is the
        # expensive half. Nothing is checked after it -- bytes already paid for
        # are written to the cache even by cancelled work, because the cache is
        # content-addressed by signature and throwing them away buys nothing
        # while costing the next request the whole generation again.
        if outofband.stopped(work):
            return None
        data = None
        # THE FALLBACK WAS CORRECT AND INVISIBLE. Any failure here is a reason
        # to generate normally, as the comment above says -- but a bare `except`
        # that set `data = None` left an edit which was TRIED AND FAILED with
        # exactly the trace of one that was never attempted: no log line, no
        # field, nothing. Asked "is the editing suite working", nobody could
        # answer from the artefacts, because a room holding several images looks
        # identical whether continuity is running or silently falling back on
        # every beat.
        #
        # These three say which happened. `edit_attempted` separates a shut gate
        # from an open one, `edit_used` says whether the returned bytes are a
        # revision or a fresh generation, and `edit_error` names the failure
        # that was previously swallowed whole.
        edit_attempted = bool(anchor)
        edit_used = False
        edit_error = ""
        if anchor:
            # A DIFFERENT prompt, not the same one: a generation describes the
            # whole place because nothing exists yet, a revision describes only
            # what moved because the place is already in the image it is given.
            # See compose_revision.
            revision = compose_revision(req["place"], style, anchor_place)
            try:
                with open(anchor, "rb") as fh:
                    data = edit_image(revision, fh.read())
                prompt = revision
                edit_used = data is not None
            except Exception as exc:
                # Type and message, not a traceback: this is a routine
                # provider-shaped failure and the point is to be countable
                # across turns, not to be debugged from one line.
                edit_error = "%s: %s" % (type(exc).__name__, exc)
                logger.info(
                    "backdrop edit failed, generating instead: chat=%s room=%s "
                    "error=%s", chat_id, req.get("room"), edit_error)
                data = None
        if data is None:
            data = generate_image(prompt)

        path = backdrop_path(chat_id, req["signature"], req.get("room"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".part"
        with open(tmp, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)      # atomic: a reader never sees a half image
        # The first image a room ever gets becomes the one every later state of
        # it is edited from.
        set_room_anchor(chat_id, req.get("room"), req["signature"],
                        req.get("place"))
    return {"path": path, "signature": req["signature"],
            "room": req["room_name"], "prompt": prompt, "cached": False,
            "edit_attempted": edit_attempted, "edit_used": edit_used,
            **({"edit_error": edit_error} if edit_error else {})}


# --- out-of-band generation queue -----------------------------------------
#
# Nothing may WAIT on an image. generate_backdrop() blocks for the length of a
# generation -- tens of seconds, up to the provider timeout of three minutes --
# and a route that calls it directly holds a server worker for that whole time,
# for a picture the reader is not waiting on anyway: the prose is already on
# screen. A caller asks for a backdrop, gets "ready" or "pending" straight
# back, and a worker thread produces it.
#
# The queue is per-signature, like the generation lock it sits above: two
# requests for the same picture produce one worker, and a request for a room
# already being drawn simply joins it.
#
# The queue itself is `outofband.Queue`, shared with ambience.py, because both
# tables this used to keep grew with the key space rather than with the work:
# `_IN_FLIGHT` pruned itself, but `_LAST_ERROR` only ever lost an entry when
# somebody asked for that exact signature again, which a reader who never walks
# back into that room never does. See that module for the measurement and for
# why this is not `jobs.py` yet.

_QUEUE = outofband.Queue("backdrop")


def backdrop_status(chat_id, signature):
    """'ready' | 'pending' | 'error' | 'absent' for one signature."""
    if cached_backdrop(chat_id, signature):
        return "ready"
    return _QUEUE.status(signature)


def backdrop_error(signature):
    """The last failure for this signature, or None.

    Kept because the alternative is a picture that never appears and never
    explains itself -- out-of-band work that fails silently is worse than work
    that fails loudly.
    """
    return _QUEUE.error(signature)


def cancel_backdrops(chat_id):
    """Stop the generations in flight for one chat. Returns how many were asked.

    Cooperative and BETWEEN steps: a generation already inside a provider call
    finishes that call, and stops at the next boundary in `generate_backdrop`.
    Nothing is killed mid-flight, because a half-written image on disk is worse
    than a wasted one.
    """
    return _QUEUE.cancel_group(chat_id)


def request_backdrop(chat_id, turn_idx, player_name=None, style=None,
                     force=False):
    """Ensure this turn's backdrop exists, generating in the background.

    Returns {signature, status, room} and NEVER blocks on the image. A retry
    after a failure is explicit: the error is cleared here, when someone asks
    again, rather than expiring on a timer.
    """
    req = build_backdrop_request(chat_id, turn_idx, player_name, style)
    if not req:
        return None
    signature = req["signature"]
    if req["cached"] and not force:
        return {"signature": signature, "status": "ready",
                "room": req["room_name"]}

    # `force` SUPERSEDES rather than joins. Asking for a regeneration while one
    # is already running used to return "pending" and quietly drop the
    # instruction -- the caller then got the very image they had asked to
    # replace, from a queue that reported success.
    _QUEUE.submit(
        signature,
        lambda work: generate_backdrop(chat_id, turn_idx, player_name, style,
                                       force=force, work=work),
        group=chat_id, supersede=force)
    return {"signature": signature, "status": "pending",
            "room": req["room_name"]}
