"""Scene backdrops: a generated image of the room the player is standing in.

EXPERIMENTAL. Runs entirely outside the turn pipeline -- image generation takes
seconds to tens of seconds and must never sit between the player and their
prose.

Three rules shape everything here.

**1. The prompt comes from the player's PERCEPTION VIEW, not the objective
scene.** `scene.rooms[room].desc` is the omniscient record: it contains the
concealed door, the watcher behind the crates, the thing the narrator
deliberately withheld. Rendering that as a backdrop would leak, in a picture,
exactly what the prose spent a pipeline stage protecting. The player's own view
(`perception_outcome.views["player"]`) is the slice the narrator is already
allowed to render, so it is the only legitimate source.

**2. Backdrops depict the room EMPTY -- no people, ever.** This is a hard rule,
not a style preference. It removes the residual leak (you cannot render a person
the viewer has not met if you render no people at all), it avoids uncanny
likenesses of characters the reader has imagined for themselves, and it is what
makes per-room caching correct: people move constantly, architecture does not.

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

from db import q, wget

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
    rows = q(
        "SELECT turn_idx, blob FROM checkpoints "
        "WHERE chat_id=? AND turn_idx<=? ORDER BY turn_idx DESC LIMIT ?",
        (chat_id, turn_idx, max(1, min(int(lookback), 8))))
    arrival = turn_idx
    for row in rows:
        try:
            world = (json.loads(row["blob"]) or {}).get("world") or {}
            scene = world.get("scene")
            if isinstance(scene, str):
                scene = json.loads(scene)
        except (ValueError, TypeError):
            continue
        if not isinstance(scene, dict):
            continue
        if _room_of_player(scene, player_name) == room_id:
            arrival = row["turn_idx"]
        else:
            break
    return arrival


def build_backdrop_request(chat_id, turn_idx, player_name=None, style=None):
    """Everything needed to generate (or serve from cache) one backdrop.

    Returns {room, signature, cached, source} -- `source` being the
    perception-derived, people-stripped setting text an image prompt is written
    from. Returns None when there is no room to depict.
    """
    scene = wget(chat_id, "scene", {}) or {}
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
        # The arrival beat describes the place; a mid-scene beat describes
        # people talking in it.
        "source": _setting_only(player_view_for_turn(
            chat_id, arrival_turn_for_room(chat_id, turn_idx, room_id,
                                           player_name))),
        "time": scene.get("time") or "",
        "location": scene.get("location") or "",
    }
