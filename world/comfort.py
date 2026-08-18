# comfort.py
"""Ambient comfort from surfaces: what the WORLD contributes to a body's ease.

`resolve_hedonic` (psychology_runtime.py) carries bounded pain and pleasure,
and pain has a deterministic world-side floor -- injury and bad air propose
pain whether or not the model mentions them. Pleasure had no symmetric
counterpart: a character on a featherbed felt exactly what a character on
flagstones felt unless the model happened to say so. This module is that
counterpart (docs/design/DESIGN_SURFACE_COMFORT.md): a small, bounded, read-only fact
about what a body is VERIFIABLY doing right now -- stationed at, near, or in
contact with something in a closed comfort vocabulary -- fed into
resolve_hedonic as a pleasure-LEVEL floor and never anything else. The two
hard rules (comfort never feeds `charge`; comfort habituates) are enforced in
resolve_hedonic itself, where the state lives.

Derivation reads only structural scene state: `scene.contacts`,
`scene.stations`, room anchors, the body's own entity `state.posture`, and
entity kind/name/description tokens. Never prose. The lexicon is identifier
recognition against a deliberately small closed vocabulary, with the same
honesty every affordance in this codebase carries: it recognizes a bed it can
name and is silent about upholstery it cannot, exact tokens only (so "fur"
never fires on "furnace"), and anything story-specific belongs in authored
lore, not in this list.

Lives in its own module rather than spatial.py -- which derives a different
kind of fact and was under concurrent bearing/orientation work when this was
written -- and rather than psychology_runtime.py, which is deliberately
import-free pure state math and must not grow a scene dependency.

SEAM, now taken up: the design's most interesting effect -- a remembered warm
corner pulling a tired body back at need -- lives in place purpose
(`affords.rest {basis: witnessed}` on a place-graph node, surfaced through
recalled places and mediated by a decision). `place_purpose.witness_affords`
reads `rest_affording` as exactly that witnessed-basis fact. Nothing here
writes it, and comfort must never become navigational pull directly: the pull
is a remembered fact the character may act on or ignore, never a gradient in
the hedonic engine.
"""

from __future__ import annotations

import re

from world.spatial import contacts_of, room_of

# The absolute ceiling on world-contributed comfort, shared with
# psychology_runtime's ambient handling. 0.3 ** 1.3 ~= 0.21 absorption --
# a comfortable character still thinks clearly.
COMFORT_CEILING = 0.3

_LEVEL_LYING = 0.3     # lying on a soft support
_LEVEL_SEATED = 0.2    # seated on / in contact with a soft support
_LEVEL_NEAR = 0.1      # standing by warmth or beside a soft feature

# --- the closed vocabulary -------------------------------------------------
#
# Exact tokens, never prefixes: prefix matching is how "fur" becomes
# "furniture" and "furnace". Small and generic on purpose -- the same
# lexicon-creep failure mode place purpose has. It will want to grow into an
# unversioned ontology of furniture; refuse it.

_SOFT_TOKENS = frozenset({
    "bed", "beds", "featherbed", "featherbeds", "bedroll", "bedrolls",
    "bunk", "bunks", "cot", "cots", "couch", "couches", "sofa", "sofas",
    "settee", "settees", "divan", "divans", "armchair", "armchairs",
    "cushion", "cushions", "cushioned", "pillow", "pillows", "pillowed",
    "fur", "furs", "blanket", "blankets", "quilt", "quilts",
    "hammock", "hammocks", "mattress", "mattresses",
})

_WARMTH_TOKENS = frozenset({
    "hearth", "hearths", "fireplace", "fireplaces", "brazier", "braziers",
    "campfire", "campfires", "stove", "stoves",
})
# "fire" alone is deliberately absent: a burning building carries the token
# too, and identifier recognition cannot tell warmth from catastrophe.
# Warm water needs its qualifier adjacent for the same reason -- a cold
# spring and a hot iron share the bare nouns.
_WARM_QUALIFIERS = frozenset({"warm", "hot", "heated"})
_WARM_MEDIA = frozenset({
    "spring", "springs", "bath", "baths", "pool", "pools",
    "water", "waters",
})

_LYING_TOKENS = frozenset({
    "lying", "lies", "lain", "reclining", "reclined", "sprawled",
    "supine", "prone", "stretched", "sleeping", "asleep", "dozing",
})
_SITTING_TOKENS = frozenset({
    "sitting", "seated", "sat", "curled", "slumped", "lounging",
})

# Contact manners that mean the surface is SUPPORTING the body rather than
# the body doing something to it (spatial's _CONTACT_KEY_MANNERS vocabulary).
_SUPPORT_MANNERS = frozenset({
    "rest", "lean", "press", "touch", "lie", "sit", "hold",
})


def _tokens(*texts):
    out = []
    for text in texts:
        out.extend(t for t in re.split(r"[^a-z0-9]+",
                                       str(text or "").casefold()) if t)
    return out


def _soft(tokens):
    return any(t in _SOFT_TOKENS for t in tokens)


def _warm(tokens):
    if any(t in _WARMTH_TOKENS for t in tokens):
        return True
    return any(a in _WARM_QUALIFIERS and b in _WARM_MEDIA
               for a, b in zip(tokens, tokens[1:]))


def _ci_eq(a, b):
    return str(a or "").strip().casefold() == str(b or "").strip().casefold()


def _entity_record(scene, name):
    """The entity record `name` refers to (by id, name, or alias), or None."""
    target = str(name or "").strip().casefold()
    if not target:
        return None, None
    for eid, ent in ((scene or {}).get("entities") or {}).items():
        if not isinstance(ent, dict):
            continue
        labels = [eid, ent.get("name"), *(ent.get("aliases") or [])]
        if any(str(lb or "").strip().casefold() == target for lb in labels):
            return eid, ent
    return None, None


def _is_body(scene, eid, ent, name):
    """A body is never furniture, whatever its description says it wears.

    Same measured split _is_body_entity uses for dock edges: bodies are the
    things with `attire` or `scales` records (plus `vitals`, which only bodies
    carry) -- checked so a character described "in a fur cloak" cannot read as
    a comfort surface to whoever is touching them.
    """
    keys = [name, eid]
    if isinstance(ent, dict):
        keys.append(ent.get("name"))
        keys.extend(ent.get("aliases") or [])
    for source in ("attire", "scales", "vitals"):
        table = (scene or {}).get(source) or {}
        if not isinstance(table, dict):
            continue
        for key in keys:
            key = str(key or "").strip().casefold()
            if key and any(str(k).strip().casefold() == key for k in table):
                return True
    return False


def _station_of(scene, name):
    """`name`'s station record, with room_of's key tolerance. {} when none."""
    stations = (scene or {}).get("stations") or {}
    if not isinstance(stations, dict):
        return {}
    if name in stations and isinstance(stations[name], dict):
        return stations[name]
    for k, v in stations.items():
        if isinstance(v, dict) and _ci_eq(k, name):
            return v
    return {}


def _posture_of(scene, name):
    """'lying' | 'sitting' | '' from pose, then legacy entity state.

    `scene.poses` is the cross-character authority, including player personas
    that have no scene entity. Entity state remains a compatibility fallback.
    Both are read by exact token -- never the description paragraph.
    """
    poses = (scene or {}).get("poses") or {}
    pose = next((value for key, value in poses.items()
                 if _ci_eq(key, name) and isinstance(value, dict)), {}) \
        if isinstance(poses, dict) else {}
    pose_tokens = _tokens(pose.get("posture"))
    if any(t in _LYING_TOKENS for t in pose_tokens):
        return "lying"
    if any(t in _SITTING_TOKENS for t in pose_tokens):
        return "sitting"

    _eid, ent = _entity_record(scene, name)
    if not isinstance(ent, dict):
        return ""
    state = ent.get("state") if isinstance(ent.get("state"), dict) else {}
    # `position` as well as `posture`: the Director writes the arrangement into
    # whichever of the two it reaches for, and the live record that led here
    # was `position: "seated_on_bed_edge"` -- already in this vocabulary, and
    # never looked at. Same exact-token pass, still never the description.
    tokens = _tokens(state.get("posture"), state.get("position"))
    if any(t in _LYING_TOKENS for t in tokens):
        return "lying"
    if any(t in _SITTING_TOKENS for t in tokens):
        return "sitting"
    return ""


def _derive(scene, name):
    """(level, source, resting) for what `name`'s body is verifiably doing.

    Non-mutating; reads the settled scene only. `resting` is the narrow
    lying-on-a-soft-support fact tick_vitals spends.
    """
    scene = scene if isinstance(scene, dict) else {}
    label = str(name or "").strip()
    room_id = room_of(scene, label) if label else None
    if not room_id:
        return 0.0, "", False

    posture = _posture_of(scene, label)
    best, source, resting = 0.0, "", False

    def consider(level, src, lying_support=False):
        nonlocal best, source, resting
        src = str(src or "").strip()
        if lying_support:
            resting = True
        if src and level > best:
            best, source = level, src

    # Contact: the strongest evidence -- the body is against the thing.
    for contact in contacts_of(scene, label):
        actor = str(contact.get("actor") or "")
        other = contact.get("target") if _ci_eq(actor, label) else actor
        manner = str(contact.get("manner") or "touch").strip().casefold()
        if manner not in _SUPPORT_MANNERS:
            continue
        eid, ent = _entity_record(scene, other)
        display = str((ent or {}).get("name") or other or "").strip()
        if _is_body(scene, eid, ent, other):
            continue
        tokens = _tokens(other, eid, (ent or {}).get("kind"),
                         (ent or {}).get("name"),
                         (ent or {}).get("description"))
        if _soft(tokens):
            if posture == "lying":
                consider(_LEVEL_LYING, display, lying_support=True)
            else:
                consider(_LEVEL_SEATED, display)
        elif _warm(tokens):
            consider(_LEVEL_NEAR, display)

    # Station AT an anchor: seated on the cushioned corner bench the room
    # itself names, or standing at the hearth.
    station = _station_of(scene, label)
    room = ((scene.get("rooms") or {}).get(room_id)) or {}
    anchors = room.get("anchors") if isinstance(room, dict) else {}
    anchors = anchors if isinstance(anchors, dict) else {}
    at = station.get("at")
    if at and at in anchors:
        anchor = anchors.get(at) or {}
        desc = str((anchor if isinstance(anchor, dict) else {}).get("desc")
                   or "").strip()
        display = desc or str(at).replace("_", " ")
        tokens = _tokens(at, desc)
        if _soft(tokens):
            if posture == "lying":
                consider(_LEVEL_LYING, display, lying_support=True)
            elif posture == "sitting":
                consider(_LEVEL_SEATED, display)
            else:
                consider(_LEVEL_NEAR, display)
        elif _warm(tokens):
            consider(_LEVEL_NEAR, display)

    # Station NEAR entities: beside the brazier, next to the couch. Nearness
    # without contact is the standing-near tier whatever the thing is.
    for other in station.get("near") or []:
        eid, ent = _entity_record(scene, other)
        if ent is None:
            continue
        if _is_body(scene, eid, ent, other):
            continue
        tokens = _tokens(other, eid, ent.get("kind"), ent.get("name"),
                         ent.get("description"))
        if _soft(tokens) or _warm(tokens):
            consider(_LEVEL_NEAR, str(ent.get("name") or other).strip())

    return round(min(best, COMFORT_CEILING), 4), source, resting


def comfort_level(scene, name):
    """(level 0.0..COMFORT_CEILING, source string) of ambient comfort for
    `name`, derived from the settled scene. (0.0, "") when nothing in the
    closed vocabulary is verifiably stationed-at, near, or in contact --
    including a hearth merely somewhere in the room, because unstationed
    nearness is not a fact this can honestly assert."""
    level, source, _resting = _derive(scene, name)
    return level, source


def rest_affording(scene, name):
    """Is this body lying on a soft support -- the narrow fact tick_vitals
    spends as passive stamina recovery, so rest works without the Director
    remembering to declare it. Deliberately stricter than comfort: sitting by
    the fire is pleasant but it is not rest."""
    _level, _source, resting = _derive(scene, name)
    return resting
