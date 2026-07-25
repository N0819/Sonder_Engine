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

**2. Backdrops depict the room EMPTY -- no people, ever.** Falls out of rule 1
rather than needing enforcement: occupants are never in the projection to begin
with, so a character or a monster cannot reach the image. This also avoids
uncanny likenesses and is what makes per-room caching correct.

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

from db import q, wget_for_frame

# Where generated images live. Deliberately NOT the database: engine.db is
# already ~400MB of text, and a few hundred backdrops would dwarf it while
# making every backup and export drag them along.
BACKDROP_DIR = os.environ.get(
    "FICTION_ENGINE_BACKDROP_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "backdrops"))

# A backdrop is scenery, so the visual signature only tracks what changes how
# the PLACE looks. Overlays and conditions can do that (smoke, darkness,
# wreckage); positions and dialogue cannot.
_VISUAL_STATE_KEYS = ("overlays", "conditions", "time", "weather")


def _room_of_player(scene, player_name):
    positions = (scene or {}).get("positions") or {}
    if player_name and positions.get(player_name):
        return positions[player_name]
    return (scene or {}).get("player_room")


def visual_signature(scene, room_id, style=None):
    """A stable hash of everything that changes how `room_id` LOOKS.

    Deliberately excludes people and speech: a room does not become a different
    picture because someone walked in. Including them would defeat the cache on
    almost every turn, which is the whole reason this feature is affordable.
    """
    scene = scene or {}
    room = ((scene.get("rooms") or {}).get(room_id) or {})
    material = {
        "room": room_id,
        "name": room.get("name") or "",
        "desc": room.get("desc") or "",
        "time": scene.get("time") or "",
        "location": scene.get("location") or "",
        "style": style or {},
    }
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


def backdrop_path(chat_id, signature):
    return os.path.join(BACKDROP_DIR, str(chat_id), "%s.png" % signature)


def cached_backdrop(chat_id, signature):
    """The path to an already-generated backdrop, or None."""
    path = backdrop_path(chat_id, signature)
    return path if os.path.exists(path) else None


# --- prompt construction ---------------------------------------------------

# Phrases that would put a person in the frame. The image prompt asks for an
# empty room, but a model handed "the Doctor leans toward the LCARS panel"
# will draw the Doctor anyway, so the source text is stripped before it ever
# reaches the prompt rather than relying on the instruction alone -- the same
# belt-and-braces shape used elsewhere in this engine.
_PERSON_CLAUSE = re.compile(
    r"[^.!?]*\b(he|she|they|him|her|them|his|hers|their|"
    r"says?|said|asks?|asked|replies|replied|leans?|turns?|looks?|walks?|"
    r"stands?|sits?|smiles?|nods?|whispers?|shouts?|steps?)\b[^.!?]*[.!?]",
    re.I)


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
    stripped = _PERSON_CLAUSE.sub(" ", stripped)
    # Fragments left by removing a quote mid-sentence.
    stripped = re.sub(r"(?<![.!?])\s*\.\.+", " ", stripped)
    # Collapse the runs of bare periods left where consecutive quotes were
    # replaced by sentence breaks.
    stripped = re.sub(r"(?:\s*\.\s*){2,}", " ", stripped)
    stripped = re.sub(r"^[\s.]+", "", stripped)
    stripped = re.sub(r"\s{2,}", " ", stripped).strip()
    return stripped


# Scene fields that describe the PLACE. Everything else -- entities, positions,
# attire, conditions on people -- is omitted by construction, which is the whole
# safety argument: a monster cannot appear in a backdrop built from a
# projection that has no concept of occupants.
# `notes` is deliberately EXCLUDED despite describing the room: it is freeform
# and routinely carries occupants. Real example from live data --
#   "The TARDIS materializes in this room... Hinami and the Doctor are
#    outside it now."
# A whitelist that admits a freeform field is not a whitelist.
_PLACE_FIELDS = ("name", "desc")


def room_projection(scene, room_id):
    """A whitelisted, occupant-free description of one room.

    Deliberately a whitelist rather than a filter: adding a new scene field
    cannot silently start leaking people into backdrops, because anything not
    named here is simply absent.
    """
    scene = scene or {}
    room = ((scene.get("rooms") or {}).get(room_id) or {})
    out = {k: room.get(k) for k in _PLACE_FIELDS if room.get(k)}
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
    if scene.get("time"):
        out["time"] = scene["time"]
    # Adjacency as pure layout: which way the room opens, never who is through
    # the door.
    exits = []
    for edge in (room.get("adjacent") or []):
        if not isinstance(edge, dict):
            continue
        exits.append({k: edge[k] for k in ("barrier", "vertical", "dir")
                      if edge.get(k)})
    if exits:
        out["exits"] = exits
    # Per-room visual overlays (smoke, darkness, wreckage) DO belong: they
    # change what the place looks like. Overlays keyed to a PERSON never reach
    # here because the lookup is by room id.
    overlay = (scene.get("overlays") or {}).get(room_id)
    if overlay:
        out["overlays"] = overlay
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
    # Blobs are ~1MB each, so the lookback is deliberately small -- a cheap
    # per-turn room index would be the right optimization if this ships.
    arrival = turn_idx
    for idx in range(turn_idx, max(-1, turn_idx - max(1, min(int(lookback), 8))), -1):
        scene = scene_after_turn(chat_id, idx)
        if _room_of_player(scene, player_name) == room_id:
            arrival = idx
        else:
            break
    return arrival


def _turn_frame(chat_id, turn_idx):
    row = q("SELECT frame_id FROM turns WHERE chat_id=? AND idx=?",
            (chat_id, turn_idx), one=True)
    return row["frame_id"] if row else None


def scene_after_turn(chat_id, turn_idx):
    """The scene as it stood AFTER `turn_idx` resolved.

    Checkpoints are written BEFORE a turn runs, so checkpoint N is the state
    going INTO turn N -- the state coming out of turn N is checkpoint N+1, or
    the live scene when N is the latest turn. Mixing the two reads a room the
    player has already left, which is exactly how an earlier draft "found" a
    frame-scoping bug that did not exist.
    """
    row = q("SELECT blob FROM checkpoints WHERE chat_id=? AND turn_idx=?",
            (chat_id, turn_idx + 1), one=True)
    if row:
        try:
            world = (json.loads(row["blob"]) or {}).get("world") or {}
            scene = world.get("scene")
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

    Returns {room, signature, cached, source} -- `source` being the
    perception-derived, people-stripped setting text an image prompt is written
    from. Returns None when there is no room to depict.
    """
    scene = scene_after_turn(chat_id, turn_idx)
    room_id = _room_of_player(scene, player_name)
    if not room_id:
        return None
    signature = visual_signature(scene, room_id, style)
    room = ((scene.get("rooms") or {}).get(room_id) or {})
    return {
        "room": room_id,
        "room_name": room.get("name") or room_id,
        "signature": signature,
        "cached": cached_backdrop(chat_id, signature),
        # Structured, occupant-free: this is what an image prompt is written
        # from. Rich (architecture, light, exits, damage) and safe by
        # construction (no entities, no positions, no people).
        "place": room_projection(scene, room_id),
        # Optional atmosphere only, from the ARRIVAL beat (mid-scene prose is
        # people talking; arrival prose describes the place). People and speech
        # are stripped, but this is a supplement -- `place` is the source of
        # record, so a thin or empty flavour string costs nothing.
        "flavour": _setting_only(player_view_for_turn(
            chat_id, arrival_turn_for_room(chat_id, turn_idx, room_id,
                                           player_name))),
        "time": scene.get("time") or "",
        "location": scene.get("location") or "",
    }
