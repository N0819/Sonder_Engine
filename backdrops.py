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
import threading

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
_VISUAL_STATE_KEYS = ("overlays", "conditions", "weather")

# scene.time is freeform narrative text, not a clock: live values include
# "Night", "a few seconds", "a few seconds pass", "moments pass". Hashing it
# raw meant the SAME room with an IDENTICAL description produced a different
# cache key on consecutive turns ("a few seconds" vs "a few seconds pass"),
# which would have defeated caching on nearly every beat -- the one thing that
# makes this feature affordable. Only the coarse visual bucket belongs in the
# key: night really does look different from noon, "moments pass" does not.
_TIME_BUCKETS = (
    ("night", ("night", "midnight", "small hours", "after dark", "nocturn")),
    ("evening", ("evening", "dusk", "sunset", "twilight", "nightfall")),
    ("morning", ("morning", "dawn", "sunrise", "daybreak", "first light")),
    ("day", ("noon", "midday", "afternoon", "daylight", "daytime")),
)


def time_bucket(value):
    """Coarse time-of-day for cache keying and prompting, or '' if the text
    says nothing about the light."""
    text = str(value or "").casefold()
    for bucket, words in _TIME_BUCKETS:
        if any(word in text for word in words):
            return bucket
    return ""


def place_desc(room):
    """A room's description with its occupants stripped out.

    The single definition of "what this place looks like", used by BOTH the
    prompt projection and the cache key so the two cannot drift: a key that
    hashes text the prompt never sees would pay for regenerations the picture
    cannot show. Defined here, above its callers, because `visual_signature`
    is the first of them.
    """
    return _setting_only((room or {}).get("desc") or "")


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
        # The PROJECTED description, not the raw one: the cache key has to be a
        # function of what actually reaches the image prompt. Hashing the raw
        # text would regenerate a room because someone was written into (or out
        # of) its description -- a change the picture cannot show.
        "desc": place_desc(room),
        "time": time_bucket(scene.get("time")),
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
    path = backdrop_path(chat_id, signature)
    if os.path.exists(path):
        return path
    for ancestor in branch_lineage(chat_id):
        inherited = backdrop_path(ancestor, signature)
        if os.path.exists(inherited):
            return inherited
    return None


# --- prompt construction ---------------------------------------------------

# Phrases that would put a person in the frame. The image prompt asks for an
# empty room, but a model handed "the Doctor leans toward the LCARS panel"
# will draw the Doctor anyway, so the source text is stripped before it ever
# reaches the prompt rather than relying on the instruction alone -- the same
# belt-and-braces shape used elsewhere in this engine.
_PERSON_CLAUSE = re.compile(
    r"[^.!?]*\b(he|she|they|him|her|them|his|hers|their|"
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
    r"onlookers?|crowds?|people|figures?)\b[^.!?]*[.!?]",
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
    bucket = time_bucket(scene.get("time"))
    if bucket:
        out["time"] = bucket
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


def compose_prompt(place, style=None, flavour=""):
    """A deterministic image prompt from the whitelisted place projection.

    Used as-is when no `backdrop_prompt` model is configured, and as the input
    to that agent when one is. Deterministic on purpose: the feature must work,
    and be testable, with no extra model call at all.
    """
    parts = []
    if place.get("name"):
        parts.append(str(place["name"]))
    if place.get("desc"):
        parts.append(str(place["desc"]))
    if place.get("overlays"):
        parts.append(", ".join(str(o) for o in place["overlays"]))
    if place.get("time"):
        parts.append("time: %s" % place["time"])
    if flavour:
        parts.append(flavour)
    for key in ("genre", "tone"):
        if (style or {}).get(key):
            parts.append("%s: %s" % (key, style[key]))
    parts.append(_BACKDROP_STYLE)
    if (style or {}).get("avoid"):
        parts.append("avoid: %s" % style["avoid"])
    return " | ".join(p for p in parts if p)


def refine_prompt(draft, place):
    """Optionally rewrite the deterministic draft with the `backdrop_prompt`
    model. Returns the draft unchanged if no model is configured or the call
    fails -- this is a nicety, never a dependency."""
    try:
        from providers import resolve_role_candidates
        resolve_role_candidates("backdrop_prompt")
    except Exception:
        return draft
    try:
        from agents.common import _agent_json
        from prompts import get_prompt
        out = _agent_json("backdrop_prompt", "backdrop_prompt",
                          get_prompt("backdrop_prompt"),
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
# The dict is never pruned -- one small entry per distinct room-state seen in
# a process lifetime -- because pruning it would race with the waiters.
_GEN_LOCKS = {}
_GEN_LOCKS_GUARD = threading.Lock()


def _generation_lock(key):
    with _GEN_LOCKS_GUARD:
        lock = _GEN_LOCKS.get(key)
        if lock is None:
            lock = _GEN_LOCKS[key] = threading.Lock()
        return lock


def generate_backdrop(chat_id, turn_idx, player_name=None, style=None,
                      force=False):
    """Produce (or serve from cache) the backdrop for a turn.

    Returns {path, signature, room, prompt, cached}. The prompt is handed to
    the image generator automatically -- composing and generating are one
    operation from the caller's point of view.
    """
    from providers import generate_image

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

        prompt = refine_prompt(
            compose_prompt(req["place"], style, req["flavour"]), req["place"])
        data = generate_image(prompt)

        path = backdrop_path(chat_id, req["signature"])
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".part"
        with open(tmp, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)      # atomic: a reader never sees a half image
    return {"path": path, "signature": req["signature"],
            "room": req["room_name"], "prompt": prompt, "cached": False}


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

_QUEUE_LOCK = threading.Lock()
_IN_FLIGHT = {}          # signature -> True while a worker is generating
_LAST_ERROR = {}         # signature -> str, so a failure is visible, not silent


def backdrop_status(chat_id, signature):
    """'ready' | 'pending' | 'error' | 'absent' for one signature."""
    if cached_backdrop(chat_id, signature):
        return "ready"
    with _QUEUE_LOCK:
        if signature in _IN_FLIGHT:
            return "pending"
        if signature in _LAST_ERROR:
            return "error"
    return "absent"


def backdrop_error(signature):
    """The last failure for this signature, or None.

    Kept because the alternative is a picture that never appears and never
    explains itself -- out-of-band work that fails silently is worse than work
    that fails loudly.
    """
    with _QUEUE_LOCK:
        return _LAST_ERROR.get(signature)


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

    with _QUEUE_LOCK:
        if signature in _IN_FLIGHT:
            return {"signature": signature, "status": "pending",
                    "room": req["room_name"]}
        _IN_FLIGHT[signature] = True
        _LAST_ERROR.pop(signature, None)

    def _work():
        try:
            generate_backdrop(chat_id, turn_idx, player_name, style,
                              force=force)
        except Exception as exc:
            with _QUEUE_LOCK:
                _LAST_ERROR[signature] = "%s: %s" % (type(exc).__name__,
                                                     str(exc)[:300])
        finally:
            with _QUEUE_LOCK:
                _IN_FLIGHT.pop(signature, None)

    threading.Thread(target=_work, name="backdrop-%s" % signature[:8],
                     daemon=True).start()
    return {"signature": signature, "status": "pending",
            "room": req["room_name"]}
