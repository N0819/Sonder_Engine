"""Opening, action-onset, and outcome perception agents."""

from __future__ import annotations

import contextvars
import copy
import json
import re
from concurrent.futures import ThreadPoolExecutor

from character_schema import (
    character_appearance,
    character_name,
    character_senses,
    persona_appearance,
    persona_name,
    persona_senses,
)
from db import wget
from prompts import get_prompt
from scene import (
    NON_AWAKE_GATED,
    active_disguises,
    appearance_of,
    apply_awareness_diff,
    awareness_map,
    awareness_of,
    disguise_known_to,
    disguised_visible_appearance,
    get_scene,
    is_player_speaker,
    persona_of,
    senses_of,
    sheet_state,
)
import os

import affect
from spatial import (
    hiding_holders_of,
    _body_interior_holder,
    ambient_scope,
    containment_conceals,
    crossing_visible_from,
    egocentric_frame,
    entity_arc,
    entity_side,
    has_visual,
    effective_light,
    visual_level_between,
    hear_level,
    merge_scene_with_diff,
    proximity_rel,
    room_layout,
    room_of,
    scent_level,
    spatial_facts,
    spatial_rel,
    visible_adjacent_rooms,
)


def _addresses(intended_target, observer_name):
    """True when a dialogue line's intended_target names this observer. The
    target may be a single name or a list; comparison is casefolded. Used to
    route a comm-channel transmission to the party it was addressed to, across
    a physical barrier (see the medium:'comm' handling in perception_outcome)."""
    if not intended_target or not observer_name:
        return False
    targets = intended_target if isinstance(intended_target, (list, tuple)) \
        else [intended_target]
    on = str(observer_name).casefold()
    return any(str(t).casefold() == on for t in targets)


def _dialogue_hear_level(entry, rel, observer_name):
    """Audibility of one dialogue entry to an observer.

    Ordinary spatial hearing (hear_level) decides first. It only ever gets
    OVERRIDDEN in one direction -- a line it would DROP ('none', out of earshot)
    is rescued to 'full' when the line is a TRANSMISSION addressed to THIS
    observer: a combadge/radio/intercom carries the voice across the physical
    barrier that ordinary hearing can't. A line already audible is never
    altered, so same-room and open-door hearing are untouched.

    A transmission is recognised by either signal:
      - the director marked it medium:'comm' (explicit), or
      - it plainly NAMES this observer (intended_target) at a spoken volume
        while they are out of earshot -- you do not hold a by-name exchange with
        someone in another room without a channel, so treating it as ambient
        sound and dropping it is the TR-2 bug. This shape-based floor keeps the
        guarantee from depending on the director remembering to tag every line.

    The comm path carries only the VOICE; the caller sets can_see separately (a
    transmission grants no sight)."""
    base = hear_level(rel, entry.get("volume", "normal"))
    if base != "none":
        return base
    if _addresses(entry.get("intended_target"), observer_name) and (
        str(entry.get("medium") or "").lower() == "comm"
        or str(entry.get("volume", "normal")).lower() in ("normal", "loud", "shout")
    ):
        return "full"
    return base


def _perceiver_spatial_facts(scene, observer, sources):
    """Env-gated (SPATIAL_SCAFFOLD=1) deterministic ground-truth spatial facts
    for a perceiver -- the same scaffold given to the narrator, applied at the
    perception stage so the VIEW itself is FOV-clean (a rear source rendered as
    sound, not sight). Off by default -> {} (baseline behavior)."""
    if not os.environ.get("SPATIAL_SCAFFOLD"):
        return {}
    names = [s.get("name") for s in sources if s.get("name")]
    facts = spatial_facts(scene, observer, names)
    return {"spatial_facts": facts} if facts else {}


# Sensory-channel cues in priority order, matched as whole words against ONE
# atom rather than a whole view -- an unanchored substring scan over a page of
# prose relabels everything ("paint" matched "pain", one quoted line made a
# page of body sensation 'hearing"), and a single channel cannot describe a
# beat that arrives through several at once.
_CHANNEL_CUES = (
    ("interoception", (
        r"\bpain\b", r"\bache[sd]?\b", r"\baching\b", r"\bnausea\b",
        r"\bdizzy\b", r"\bexhausted\b", r"\bstarving\b", r"\bwounded\b",
        r"\bwounds\b", r"\byour wound\b",
        r"\bbreathless\b", r"\bcannot breathe\b", r"\bout of breath\b",
        r"\bheartbeat\b", r"\byour (?:pulse|heart|lungs|chest|stomach|"
        r"belly|throat|muscles|nerves)\b",
    )),
    ("touch", (
        r"\btouch(?:es|ed|ing)?\b", r"\bpressure\b", r"\bgrip(?:s|ped|ping)?\b",
        r"\bagainst your\b", r"\bgrips? your\b", r"\bholds? your\b",
        r"\bpress(?:es|ed|ing)? (?:into|against) you\b", r"\bwarmth\b",
        r"\bskin\b",
    )),
    ("hearing", (
        r"\byou hear\b", r"\bsays?\b", r"\bsaid\b", r"\bvoice\b",
        r"\bshout(?:s|ed|ing)?\b", r"\bwhisper(?:s|ed|ing)?\b",
        r"\bmuffled\b", r"\balarm\b", r"\bfootsteps\b", r"\bsounds?\b",
        r"\bsilence\b",
    )),
    ("smell", (
        r"\bsmell(?:s|ed|ing)?\b", r"\bscent\b", r"\bstench\b", r"\bodou?rs?\b",
    )),
    ("sight", (
        r"\byou see\b", r"\bwatch(?:es|ed|ing)?\b", r"\blight\b",
        r"\bshadows?\b", r"\bglow(?:s|ing)?\b", r"\bcolou?rs?\b",
    )),
)

_INTENSITY_CUES = (
    r"\bexplosions?\b", r"\bgunshots?\b", r"\bscream(?:s|ed|ing)?\b",
    r"\bcannot breathe\b", r"\bcritical\b", r"\bsevere\b", r"\bfires?\b",
    r"\balarms?\b", r"\bstruck\b", r"\bagony\b", r"\bblinding\b",
    r"\bdeafening\b", r"\boverwhelming\b", r"\bviolent(?:ly)?\b",
)

_SUDDENNESS_CUES = (
    r"\bsuddenly\b", r"\bwithout warning\b", r"\blunges?\b", r"\bfalls?\b",
    r"\bsnaps?\b", r"\berupts?\b", r"\bgunshots?\b", r"\bexplosions?\b",
    r"\ball at once\b", r"\bjerks?\b",
)

_AMBIGUITY_CUES = (
    r"\bmuffled\b", r"\bfragments?\b", r"\bunclear\b", r"\bindistinct\b",
    r"\bblurred\b", r"\bvague(?:ly)?\b", r"\bbarely\b", r"\bfaint(?:ly)?\b",
    r"\bcan(?:no|')t tell\b", r"\bsomething\b", r"\bsomeone\b",
    r"\ba shape\b", r"\ba voice\b", r"\bmight be\b",
)

# An event AIMED at the perceiver, not merely witnessed by them. The old rule
# recognised four verbs and 'at/toward you', so most contact and every form of
# direct address read as not-directed-at-self -- the observer was told an event
# landing on their own body was somebody else's business.
_SELF_DIRECTED = re.compile(
    r"\b(?:at|to|toward|towards|from)\s+you\b"
    r"|\b(?:against|into|onto|over|around|through)\s+(?:you|your)\b"
    r"|\b(?:grips?|grabs?|holds?|strikes?|touches|presses?|pins?|pulls?"
    r"|shoves?|hits?|catches|seizes?|reaches for|closes on|lands on"
    r"|wraps around)\s+(?:you|your)\b"
    r"|\byou are\s+(?:being\s+)?(?:\w+(?:ed|en)|struck|hit|shot|torn|thrown"
    r"|caught|dragged|pinned|held|bound)\b"
    r"|\byour name\b",
    re.I,
)

# Closing quotes and brackets ride with the sentence they end.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])[\"'”’)\]]*\s+")

# Atoms per view. High enough that a busy beat still decomposes, low enough
# that a character payload stays readable.
_MAX_OBSERVATION_ATOMS = 8

# Sentences per atom, so a long stretch of one-channel prose still arrives as
# several observations rather than one undifferentiated block.
_MAX_SPAN_SENTENCES = 3


def _cue_hits(cues, folded):
    return sum(1 for cue in cues if re.search(cue, folded))


def _atom_channel(folded):
    for channel, cues in _CHANNEL_CUES:
        if _cue_hits(cues, folded):
            return channel
    return "mixed"


def _observation_spans(text):
    """Split one view into (channel, text) spans: consecutive sentences sharing
    a channel are one atom, and spans are merged smallest-first until the view
    fits the atom budget."""
    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]
    if not sentences:
        return []
    spans = []
    for sentence in sentences:
        channel = _atom_channel(sentence.casefold())
        if (spans and spans[-1][0] == channel
                and len(spans[-1][1]) < _MAX_SPAN_SENTENCES):
            spans[-1][1].append(sentence)
        else:
            spans.append([channel, [sentence]])
    while len(spans) > _MAX_OBSERVATION_ATOMS:
        idx = min(range(len(spans)),
                  key=lambda i: len(" ".join(spans[i][1])))
        into = idx - 1 if idx else 1
        if spans[into][0] != spans[idx][0]:
            spans[into][0] = "mixed"
        target, source = sorted((into, idx))
        spans[target][1].extend(spans[source][1])
        spans.pop(source)
    return [(channel, " ".join(parts)) for channel, parts in spans]


def _observations_from_clean_views(clean_views):
    """Project final, scrubbed prose views into structured observations.

    This deliberately accepts *only* the post-gate view map. It never reads the
    Director event, raw perception-model observations, manifests, private tell
    grounds, canonical identity roster, or another body's vitals. Structured
    perception therefore cannot become a side channel: its text is byte-for-
    byte a view the perceiver was already allowed to receive, and its metadata
    is derived from that text alone.

    The axes are GRADED by cue density rather than tripped by a single hit.
    One hedging word in a long view is not an ambiguous perception, and the
    all-or-nothing form pinned every real view to the ambiguous end -- which
    the character agent then reads as reason to doubt what it plainly
    perceived.
    """
    out = {}
    for raw_pid, raw_view in (clean_views or {}).items():
        pid = str(raw_pid)
        text = str(raw_view or "").strip()
        atoms = []
        for index, (channel, span) in enumerate(_observation_spans(text)):
            folded = span.casefold()
            ambiguity = min(1.0, 0.15 + 0.2 * _cue_hits(_AMBIGUITY_CUES, folded))
            atoms.append({
                "observation_id": f"current:{pid}:{index}",
                "perceiver_id": pid,
                "source_atom_id": "current",
                "channel": channel,
                "fidelity": "ambiguous" if ambiguity >= 0.5 else "rendered",
                "observed": {"text": span},
                "intensity": min(
                    1.0, 0.35 + 0.2 * _cue_hits(_INTENSITY_CUES, folded)),
                "suddenness": min(
                    1.0, 0.1 + 0.25 * _cue_hits(_SUDDENNESS_CUES, folded)),
                "ambiguity": ambiguity,
                # Own-body state is about the perceiver by definition; nothing
                # else in a second-person view needs a cue to say so.
                "directed_at_self": channel == "interoception" or bool(
                    _SELF_DIRECTED.search(span)),
            })
        out[pid] = atoms
    return out

from .common import (
    _agent_json,
    _append_micro_view,
    _append_once,
    _contextual_rooms,
    _perceptible_entities,
    _dedupe_view_sentences,
    _ensure_environment,
    _fallback_perception_views,
    _inject_action,
    _inject_dialogue,
    _appearance_as_prose,
    _inject_visible_actor,
    _normalise_views,
    _resolve_player_room,
    _room_notes_from_lore,
    _scrub_unknown_identities,
    _scrub_invented_dialogue,
    _scrub_undeclared_player_speech,
    _compose_residue_view,
    _recognizes,
    _significant_name_tokens,
    observable_action_text,
    player_speech_lines,
    _strip_identity_tokens,
    _unknown_actor_label,
    cast_room,
    character_room,
    character_scene_keys,
)


def _observer_scene_payload(scene, perceiver):
    """Project objective scene state to one observer before any model call.

    This is intentionally stricter than an output scrub: relations that name a
    hidden body never enter another observer's context in the first place.
    """
    name = str(perceiver.get("name") or "")
    room_id = perceiver.get("room")
    visible_rooms = {
        str(item.get("room_id"))
        for item in (perceiver.get("visible_rooms") or [])
        if isinstance(item, dict) and item.get("room_id")
    }
    allowed_rooms = ({str(room_id)} if room_id else set()) | visible_rooms
    rooms = {}
    for rid in allowed_rooms:
        raw = (scene.get("rooms") or {}).get(rid)
        if not isinstance(raw, dict):
            continue
        projected = copy.deepcopy(raw)
        # F6: an adjacency to a room this observer cannot see keeps its
        # BARRIER and loses its destination. Dropping the edge outright was
        # over-correction in the other direction: a closed door is a thing in
        # the room, plainly there to anyone standing in it, and a payload that
        # omits it tells the observer the room has no way out. What they have
        # not earned is the name of what is behind it.
        adjacent = []
        for edge in (projected.get("adjacent") or []):
            if not isinstance(edge, dict):
                continue
            if str(edge.get("to")) in allowed_rooms:
                adjacent.append(edge)
                continue
            blind = {k: v for k, v in edge.items()
                     if k not in ("to", "to_name", "name", "notes", "desc")}
            blind["to"] = None
            adjacent.append(blind)
        projected["adjacent"] = adjacent
        rooms[rid] = projected

    visible_names = {
        str(other) for other in (scene.get("positions") or {})
        if str(other) != name
        and visual_level_between(scene, name, str(other)) != "none"
    }
    contacts = [
        copy.deepcopy(contact)
        for contact in (scene.get("contacts") or [])
        if isinstance(contact, dict)
        and (
            name in (str(contact.get("actor") or ""),
                     str(contact.get("target") or ""))
            or (
                str(contact.get("actor") or "") in visible_names
                and str(contact.get("target") or "") in visible_names
            )
        )
    ]
    scales = {
        key: value for key, value in (scene.get("scales") or {}).items()
        if str(key) == name or str(key) in visible_names
    }
    # A6: `contained` is the concealment ledger itself -- a body hidden in a bag
    # is named as hidden in that bag. An observer gets their own record (they
    # know what they are inside, and what they are carrying) plus any carrying
    # that is happening in plain sight between two bodies they can both see.
    # The holder is nested under an "in" key, so reading the VALUE as a name is
    # what the first version did and it silently matched nothing -- the filter
    # fell closed by accident, which is the right outcome reached the wrong way
    # and would have re-opened the moment the shape changed.
    contained = {}
    for key, value in (scene.get("contained") or {}).items():
        holder = str(
            (value or {}).get("in") if isinstance(value, dict) else value or ""
        ).strip()
        subject = str(key)
        if subject == name or holder == name:
            contained[key] = value
        elif subject in visible_names and holder in visible_names:
            contained[key] = value
    return {
        "location": scene.get("location"),
        "time": scene.get("time"),
        "rooms": rooms,
        "entities": _perceptible_entities(scene, [name]),
        "contacts": contacts,
        "scales": scales,
        "contained": contained,
        "light": {
            rid: effective_light(scene, rid) for rid in allowed_rooms
        },
    }


# Concurrency for the per-observer perception fan-out. Capped rather than
# one-thread-per-perceiver: a crowded room would otherwise open a dozen
# simultaneous completions against the provider on every one of the three
# passes.
_PERCEPTION_FANOUT_WORKERS = 4


def _per_observer_model_views(perceivers, payload_for):
    """Run perception with one physically scoped payload per observer.

    A shared call necessarily exposes the union of every observer's secrets to
    every generated view. Separate calls make the information boundary
    structural; post-hoc scrubs remain defense in depth.
    """
    def _one(perceiver):
        payload = payload_for(perceiver)
        payload["perceivers"] = [perceiver]
        payload["output_reminder"] = (
            "Return exactly one view, keyed by this perceiver's id."
        )
        out = _agent_json(
            "perception",
            "perception",
            get_prompt("perception"),
            payload,
            temperature=0.4,
        )
        raw = out.get("views") if isinstance(out, dict) else {}
        normalized = _normalise_views(raw, [perceiver])
        return str(perceiver["id"]), normalized.get(str(perceiver["id"]))

    if not perceivers:
        return {}

    # Splitting one shared call into N made the information boundary structural,
    # but run in sequence it also made a perception pass N times as slow, three
    # times a turn. The observers are genuinely independent -- each builds its
    # own payload from committed scene state and returns only its own view --
    # so this is the same shape as narrator_extra's per-persona fan-out.
    #
    # context.run is load-bearing for the same reason it is there: pool workers
    # do NOT inherit the submitting thread's contextvars, so without it
    # providers.cancel_event/token_sink read back as None and an in-flight abort
    # cannot interrupt these calls. A fresh copy per job -- one Context cannot
    # be entered by two threads at once.
    jobs = [
        (lambda p=p, cv=contextvars.copy_context(): cv.run(_one, p))
        for p in perceivers
    ]
    views = {}
    with ThreadPoolExecutor(
            max_workers=min(len(jobs), _PERCEPTION_FANOUT_WORKERS)) as pool:
        for pid, value in pool.map(lambda f: f(), jobs):
            if value:
                views[pid] = value
    return views


def _concealed_from_perceiver(entry, perceiver):
    refs = {
        str(value).strip().casefold()
        for value in (entry.get("conceal_from") or [])
        if str(value or "").strip()
    }
    return bool(
        "*" in refs
        or str(perceiver.get("name") or "").casefold() in refs
        or str(perceiver.get("id") or "").casefold() in refs
        or f"character:{perceiver.get('id')}".casefold() in refs
    )

def _ubiquitous_names(sc):
    """Bodiless voices in this scene (ship AI, station PA), casefolded.

    Imported lazily: perception must not take a hard dependency on scene.py's
    import graph for what is a small, optional lookup."""
    try:
        from scene import ubiquitous_speaker_names
        return ubiquitous_speaker_names(sc)
    except Exception:
        return frozenset()


def _source_channels(sc, perceiver_name, perceiver_room, sources):
    """spatial_to_sources / visual_channel_to_sources for ONE perceiver.

    Concealment by containment belongs here rather than at the call sites. A
    carried body has no position of its own -- the engine derives it from its
    carrier's -- so `spatial_rel` alone reports `same_room` for a body sealed
    inside something standing in the room, and `same_room` answers sight
    before any barrier is consulted.

    The action-onset pass patched that in one place (see perception_act,
    where the same containment_conceals call is made inline). Every OTHER
    pass asked the unpatched question, so a body shut inside another was
    visually available to the whole room for the outcome pass and at scene
    opening. Observed live: an outcome view rendering an enclosed body's
    fine visual detail -- ear and tail colour, a throat moving "visibly" --
    to the very body enclosing it, with the full appearance string pasted on
    the end by the deterministic actor-describer, which is gated on exactly
    this map.

    The visual channel uses `visual_level_between` (per-body light-aware)
    rather than `has_visual(rel)` (room-level ambient light only). A torch
    held by the observer illuminates the target's position even when the
    room itself is dark -- `has_visual` reads `rel["light"]` which is
    `effective_light` of the room (ambient only), so it would return False
    for a torch-bearer in a dark room. `visual_level_between` calls
    `light_at(scene, target)` which accounts for per-body spot sources.
    Containment concealment is still respected: `visual_level_between`
    checks `containment_conceals` internally, and the `concealed` flag is
    also set on `rel` for the spatial_to_sources map so `_in_plain_view`
    and other consumers still see it.

    Returns the two keys to splat into a perceiver entry, so the answer is
    computed once and cannot drift between them.
    """
    rels = {}
    for s in sources:
        rel = spatial_rel(sc, s["room"], perceiver_room)
        if containment_conceals(sc, perceiver_name, s["name"]):
            rel = {**rel, "concealed": True}
        # One-way: the perceiver is inside THIS source, so the source's voice
        # is conducted through the mass around them rather than transmitted
        # through a barrier. hear_level reads it; sight is untouched.
        holder = _body_interior_holder(sc, perceiver_name)
        if holder and holder.casefold() == str(s["name"]).strip().casefold():
            rel = {**rel, "inside_source": True}
        rels[s["name"]] = rel
    return {
        "spatial_to_sources": rels,
        "visual_channel_to_sources": {
            n: (visual_level_between(sc, perceiver_name, n) != "none"
                if room_of(sc, perceiver_name) is not None
                else has_visual(rels[n]))
            for n in rels
        },
        "scent_channel_to_sources": {n: scent_level(r) for n, r in rels.items()},
    }


def _in_plain_view(rel, vis):
    """Is this source available to SIGHT for this perceiver.

    `same_room` was being OR'd with the visual channel at the deterministic
    injection sites, which reinstated exactly the bypass containment
    concealment exists to close: an enclosed actor reads as same_room with
    everyone standing around its carrier. Concealment is consulted first
    now; `has_visual` already returns False for a concealed rel, so a
    concealed source is never in plain view by either arm.
    """
    if rel.get("concealed"):
        return False
    return bool(rel.get("same_room")) or bool(vis)


def _ambient_location_for(sc, room_id):
    """Per-perceiver ambient/location scoping by nesting depth (item 5,
    coarse): the outermost place whose ambience legitimately reaches this
    room. Open to the world -> the scene's location as usual. Sealed
    inside a nested interior (a vehicle mid-transit, a closed elevator)
    -> only the enclosure itself; the outer location's name/ambience must
    not color that perceiver's view. Derived from scene containment
    (spatial.ambient_scope) only -- never from lorebook links."""
    if not room_id:
        return sc.get("location")
    _, open_to_world = ambient_scope(sc, room_id)
    if open_to_world:
        return sc.get("location")
    room = (sc.get("rooms") or {}).get(room_id) or {}
    eid = room.get("parent_entity")
    ent = (sc.get("entities") or {}).get(eid) if eid else None
    label = ((ent or {}).get("name") if isinstance(ent, dict) else None) \
        or eid or room.get("name") or room_id
    return (f"inside {label} (sealed interior -- the outer location's "
            "ambience does not reach here)")

def _identity_roster(p_name, p_appearance, cast):
    """Every identity in play this beat, with the forms (name + uid/aliases)
    and appearance the identity scrub needs: the player plus each cast
    member. Callers extend it with extra players / background speakers."""
    roster = [{"name": p_name, "appearance": p_appearance, "aliases": []}]
    for c in cast:
        sh, _, _ = sheet_state(c)
        keys = character_scene_keys(sh)
        roster.append({
            "name": character_name(sh),
            "appearance": character_appearance(sh),
            "aliases": keys[1:],
        })
    return roster

def _observed_pronouns(chat_id, cast):
    """Canonical pronouns for each cast member a view may refer to in the third
    person, so a view doesn't guess a character's gender from their name and
    flip it between beats (W6).

    A character under an ACTIVE DISGUISE is excluded: their canonical pronouns
    are part of the identity the disguise conceals, and stating them in a view
    an unaware observer receives would out them -- the exact leak the disguise
    machinery above exists to prevent. Their pronouns come from the disguised
    appearance instead, like every other visible feature.
    """
    disguised = active_disguises(chat_id) or {}
    out = {}
    for c in (cast or []):
        sh, _, _ = sheet_state(c)
        name = character_name(sh)
        if not name or str(name).casefold() in disguised:
            continue
        pronouns = ((sh.get("identity") or {}).get("pronouns") or {}
                    if isinstance(sh, dict) else {})
        clean = {k: pronouns[k] for k in ("subject", "object", "possessive")
                 if isinstance(pronouns, dict) and pronouns.get(k)}
        if clean:
            out[name] = clean
    return out

def _pronouns_for_perceiver(all_pronouns, perceiver, known):
    """The slice of `_observed_pronouns` one observer has earned.

    The per-observer split replaced the shared cast_pronouns map with an empty
    dict, which closed the leak (a stranger's canonical pronouns are part of
    the identity they have not been given) by deleting the field -- so the
    perception prompt's PRONOUNS rule could never fire for anyone, and every
    view was back to guessing a character's gender from their name and flipping
    it between beats, which is the bug _observed_pronouns exists to fix.
    Scoping to what this observer recognizes keeps both properties: a
    recognized character keeps stable pronouns, an unrecognized one is
    described by what is visibly there."""
    name = str(perceiver.get("name") or "")
    recognized = set(known.get(name) or []) | {name}
    return {
        who: pronouns for who, pronouns in (all_pronouns or {}).items()
        if _recognizes(who, recognized)
    }


def _scrub_view_for(ctx, stage, view, perceiver_name, known, roster):
    """Apply the deterministic identity floor to one perceiver's view:
    every roster identity the perceiver does not recognize (and is not) is
    scrubbed outside quoted spans. Surfaces a pipeline warning per leak --
    the original bug was quiet, which is how it went unnoticed."""
    recognized = set(known.get(perceiver_name) or [])
    unknown = [s for s in roster
               if s["name"] != perceiver_name
               and not _recognizes(s["name"], recognized)]
    view, leaked = _scrub_unknown_identities(
        view,
        allowed_forms=[perceiver_name, *recognized],
        unknown_sources=unknown,
    )
    if leaked:
        ctx.warnings.append(
            f"{stage}: scrubbed unearned identity {leaked} "
            f"from the view of {perceiver_name}")
    return view

def _behind_rooms(scene, observer):
    """Room ids at the observer's back (the way they came), from their
    egocentric frame. Approximate field of view: an observer does not receive
    NEW VISUAL detail from a room behind them -- they get sound/other channels
    and what they already remember, but not fresh sight (you don't watch the
    room you just walked out of unless you turn). Empty when the observer has
    no movement history, so nothing is gated. See the perception FOV clause."""
    frame = egocentric_frame(scene, observer)
    return [e.get("to") for e in frame.get("behind") or [] if e.get("to")]


def _focus_target(scene, observer):
    """The NAME of the source the observer is attending (their focus), when
    focus rests on a co-located entity/character. Perception gives a focused
    source full visual detail (faces, hands, text, small objects) while an
    in-view but non-focused source is PERIPHERY -- presence, gross motion and
    identity only, no foveal detail. None when focus is an edge (a direction,
    not a source) or unset, in which case no periphery gating applies."""
    f = ((scene.get("orientation") or {}).get(observer) or {}).get("focus") or {}
    if f.get("kind") in ("entity", "target") and f.get("ref"):
        return str(f["ref"])
    return None


def _proximity_to_sources(scene, observer, sources):
    """Per CO-LOCATED source: {tier: within_reach|near|across, side:
    left|right|None, arc: front|rear|None} -- the observer's within-room
    distance, hand-side, and whether the source is in their facing FRONT or REAR
    (blind-spot) arc (Phase 3 FOV). Cross-room sources are omitted. Empty when
    nothing derivable, so absence reads exactly like the pre-Phase-2 payload."""
    out = {}
    for s in sources:
        name = s.get("name")
        if not name or name == observer:
            continue
        tier = proximity_rel(scene, observer, name)
        if tier is None:
            continue
        out[name] = {"tier": tier, "side": entity_side(scene, observer, name),
                     "arc": entity_arc(scene, observer, name)}
    return out


def _behind_sources(scene, observer, sources):
    """CO-LOCATED source names in the observer's REAR arc -- the within-room
    blind spot (Phase 3). Mirrors _behind_rooms for same-room people: a source
    here gives the observer NO NEW VISUAL detail (a silent approach/gesture is
    unseen), though sound still carries. Empty when facing/anchors give no
    basis, so nothing is gated by default (FOV fails open)."""
    return [s.get("name") for s in sources
            if s.get("name") and s.get("name") != observer
            and entity_arc(scene, observer, s.get("name")) == "rear"]


def _tell_acuity(sheet):
    """Numeric visual/auditory acuity for physical-tell delivery."""
    if not isinstance(sheet, dict):
        return 0.4
    senses = (
        character_senses(sheet)
        if ("psychology" in sheet or "core" in sheet)
        else persona_senses(sheet)
        if "narration" in sheet
        else sheet.get("senses") or []
    )
    rank = {
        "absent": 0.0, "none": 0.0, "impaired": 0.2, "poor": 0.25,
        "ordinary": 0.4, "normal": 0.4, "keen": 0.65,
        "heightened": 0.75, "exceptional": 0.9,
    }
    values = []
    for sense in senses if isinstance(senses, list) else []:
        if not isinstance(sense, dict):
            continue
        channel = str(sense.get("channel") or "").casefold()
        if channel not in ("vision", "hearing", "general"):
            continue
        label = str(sense.get("acuity") or "ordinary").casefold()
        values.append(rank.get(label, 0.4))
    return max(values) if values else 0.4


def _delivered_manifest(ctx, scene, observer, sources, known, cast_by_name,
                        observer_sheet=None):
    """Per SOURCE this observer can read: {surface_demeanor, cues:[cue,...]} --
    the interior-depth payoff (Phase 4). A character's `manifest` (surface
    demeanor + physical tells) is authored by that character; the ENGINE decides
    which cues reach THIS observer here, before the LLM call, exactly like the
    dialogue-injection backstop. A tell is delivered iff (a) the observer can
    receive its channel -- a visual tell needs sight (same-visual-channel, not
    in the rear blind spot); a voice/breath tell needs to be audible (same
    room) -- AND (b) affect.tell_gate: subtlety <= acuity + familiarity +
    attention. MEANING and the character's own labels never cross; only the
    observable cue text does."""
    out = {}
    focus = _focus_target(scene, observer)
    behind = set(_behind_sources(scene, observer, sources))
    o_room = room_of(scene, observer)
    for s in sources:
        sname = s.get("name")
        cid = cast_by_name.get(sname) if sname else None
        if not sname or sname == observer or cid is None:
            continue
        manifest = (ctx.character_results.get(cid) or {}).get("manifest") or {}
        demeanor = manifest.get("surface_demeanor")
        tells = [t for t in (manifest.get("tells") or [])
                 if isinstance(t, dict) and t.get("cue")]
        if not demeanor and not tells:
            continue
        rel = spatial_rel(scene, s.get("room"), o_room)
        # Per-BODY, so a source standing in a torch's pool is visible while the
        # rest of the dark room is not -- the room-level answer cannot see that.
        visible = (visual_level_between(scene, observer, sname) != "none"
                   and sname not in behind)
        audible = bool(rel.get("same_room"))
        acuity = _tell_acuity(observer_sheet)
        familiarity = 0.45 if (observer in (known.get(sname) or [])
                               or sname in (known.get(observer) or [])) else 0.15
        attention = 0.4 if focus == sname else 0.15
        cues = []
        for t in tells:
            chan = str(t.get("channel") or "").lower()
            reachable = visible or (chan in ("voice", "breath") and audible)
            if reachable and affect.tell_gate(t, acuity, familiarity, attention):
                cues.append(t.get("cue"))
        entry = {}
        if visible and demeanor:
            entry["surface_demeanor"] = demeanor
        if cues:
            entry["cues"] = cues
        if entry:
            out[sname] = entry
    return out


def _subject_disguise_context(chat_id, subject_name, true_appearance, known_map):
    """Resolve a subject's active physical_disguise into perception inputs.

    Returns (visible_appearance, disguise_payload_or_None, known_to_or_None):
    - visible_appearance: what EVERY observer visually perceives -- the
      disguised outward form when a disguise is active (a concealed feature is
      not seen even by someone who knows it is there), else the true
      appearance unchanged.
    - disguise_payload: the block handed to the perception LLM so it can give
      observers in known_to the concealed truth as KNOWLEDGE (never as vision)
      and preserve the subject's real capabilities; None when no disguise.
    - known_to: casefolded names that legitimately know the truth (for the
      leak tripwire), or None.

    Feeding the disguised appearance is the primary, fail-safe fix: the LLM is
    never handed the concealed features, so it cannot render them. The payload
    and tripwire are the knowledge layer and QA around that.
    """
    disguise = active_disguises(chat_id).get(str(subject_name or "").casefold())
    if not disguise:
        return true_appearance, None, None
    known_to = disguise_known_to(disguise, subject_name, known_map)
    visible = disguised_visible_appearance(true_appearance, disguise)
    payload = {
        "active": True,
        "outward_visible_appearance": visible,
        "concealed_truth": disguise.get("description") or "",
        "known_to": sorted(known_to),
        "capability_note": (
            "The disguise conceals APPEARANCE only. The subject's real senses "
            "and abilities are unchanged -- e.g. concealed ears still hear."),
        "instruction": (
            "Every observer VISUALLY perceives only outward_visible_appearance; "
            "never describe a concealed feature as seen. An observer whose name "
            "is in known_to additionally KNOWS (does not see) the concealed_truth "
            "and may act on it; an observer not in known_to has no awareness of it."),
    }
    return visible, payload, known_to


def _disguise_leak_check(ctx, stage, views, perceivers, subject_name,
                         concealed_terms, known_to):
    """Deterministic fidelity tripwire (a WARNING, never a scrubber). Flags an
    UNAWARE perceiver whose view names one of the disguised subject's concealed
    features. Scoped to that subject's own terms, so unrelated lore (a
    'Nine-Tailed Fox' task-force name) is never touched. The real fix is
    upstream -- feeding the disguised appearance so correct text is generated
    -- this only catches a model that leaked anyway."""
    if not concealed_terms:
        return
    known = known_to or set()
    for p in perceivers:
        pid = str(p["id"])
        if pid.casefold() == "player":
            continue  # the player is the subject / always knows
        if str(p.get("name") or "").casefold() in known:
            continue
        v = str(views.get(pid) or "").lower()
        for t in concealed_terms:
            t = str(t).strip().lower()
            if t and re.search(rf"\b{re.escape(t)}\b", v):
                ctx.warnings.append(
                    f"{stage}: disguise leak -- '{t}' (a concealed feature of "
                    f"{subject_name}) surfaced in the view of {p.get('name')}")
                break


def _observer_facing_sequence(sequence):
    """Project a declared action sequence into what OTHER perceivers may be
    handed. Each action element carries only its intent-free `observable`
    surface (via observable_action_text) as `attempt`, with the causal-intent
    ledger (intended_effects/asserted_effects) and the actor's own framing
    (verb, raw attempt) removed; a mental element (observable "") is dropped
    entirely, being imperceptible. Speech/event elements pass through unchanged
    (their concealment is handled separately). This keeps the perception filter
    from ever RECEIVING the actor's purpose ('runes of slow and soften',
    'channel divine heritage') -- honoring the barrier rather than handing over
    hidden intent with an instruction to ignore it (the very pattern the engine
    forbids for character agents)."""
    out = []
    for e in sequence or []:
        if not isinstance(e, dict):
            continue
        if e.get("type") != "action":
            out.append(e)
            continue
        surface = observable_action_text(e)
        if not surface:
            continue
        out.append({
            "type": "action",
            "event_id": e.get("event_id", ""),
            "attempt": surface,
            "visibility": e.get("visibility", "overt"),
            "conceal_from": e.get("conceal_from") or [],
            "targets": e.get("targets") or [],
            "stage": e.get("stage", "immediate"),
        })
    return out


def perception_establish(ctx, nonce):
    chat = ctx.chat
    est = ctx.director_establish or {}
    sc = get_scene(chat["id"], chat)
    diff = est.get("state_diff") or {}
    sc = merge_scene_with_diff(sc, diff)

    pers = persona_of(chat)
    known = wget(chat["id"], "known", {})
    # persona_of returns the normalized native shape (identity.name,
    # embodiment.visible.summary), not flat "name"/"appearance" keys --
    # this was the one remaining call site in perception.py still using
    # the flat accessor, same class of bug already fixed in
    # perception_act/perception_outcome below. Since this runs on every
    # opening turn (director_establish -> perception_establish -> ...),
    # it meant the player's actual name/appearance was silently never
    # used on turn 0 -- always "the player" with no real appearance.
    p_name = pers.get("name") or persona_name(pers)
    p_appearance = _appearance_as_prose(appearance_of(
        p_name, pers.get("appearance") or persona_appearance(pers), sc))

    p_room = _resolve_player_room(sc, pers, None, ctx.cast, ctx.get("input"))
    ctx["_player_room"] = p_room
    p_rdata = (sc.get("rooms") or {}).get(p_room) if p_room else None

    sensory_events = est.get("sensory_events") or []
    entity_states = est.get("entity_states") or {}
    p_state = entity_states.get(p_name) or {}

    sources = []
    for c in ctx.cast:
        sh, _, _ = sheet_state(c)
        r = character_room(sc, sh)
        if r:
            sources.append({"name": character_name(sh), "room": r})

    perceivers = [{
        "id": "player", "name": p_name, "room": p_room,
        "room_name": (p_rdata or {}).get("name") or p_room or "an unspecified area",
        "room_notes": ((p_rdata or {}).get("notes") or _room_notes_from_lore(p_room, ctx, sc)),
        "ambient_location": _ambient_location_for(sc, p_room),
        "visible_rooms": visible_adjacent_rooms(sc, p_room),
        "senses": senses_of(pers), "attention": "engaged",
        "knows_identity": True,
        "entity_state": p_state,
        **_source_channels(sc, p_name, p_room, sources),
        "proximity_to_sources": _proximity_to_sources(sc, p_name, sources),
        "behind_sources": _behind_sources(sc, p_name, sources),
        "room_layout": room_layout(sc, p_name),
        "behind_rooms": _behind_rooms(sc, p_name),
        "focus_target": _focus_target(sc, p_name),
        **_perceiver_spatial_facts(sc, p_name, sources),
    }]

    for c in ctx.cast:
        sh, act, _ = sheet_state(c)
        r = character_room(sc, sh)
        rdata = (sc.get("rooms") or {}).get(r) if r else None
        c_sources = [s for s in sources if s["name"] != character_name(sh)]
        perceivers.append({
            "id": c["id"], "name": character_name(sh), "room": r,
            "room_name": (rdata or {}).get("name") or r or "an unspecified area",
            "room_notes": ((rdata or {}).get("notes") or _room_notes_from_lore(r, ctx, sc)),
            "ambient_location": _ambient_location_for(sc, r),
            "visible_rooms": visible_adjacent_rooms(sc, r),
            "senses": senses_of(sh), "attention": act.get("goal") or "ambient",
            "knows_identity": p_name in (known.get(character_name(sh)) or []),
            "entity_state": entity_states.get(character_name(sh)) or {},
            **_source_channels(sc, character_name(sh), r, c_sources),
            "proximity_to_sources": _proximity_to_sources(sc, character_name(sh), c_sources),
            "behind_sources": _behind_sources(sc, character_name(sh), c_sources),
            "room_layout": room_layout(sc, character_name(sh)),
        })

    declared = {
        "actor_id": "OPENING", "actor_name": p_name,
        "actor_room": p_room,
        "actor_room_name": (p_rdata or {}).get("name") or p_room,
        "actor_present_appearance": p_appearance,
        "entity_state": p_state,
        "sensory_events": sensory_events,
        "player_seed": ctx.get("input") or "",
        "sequence": [], "player_speech": [],
        "speech": None, "speech_volume": "normal",
        "action_attempt": None, "visibility": "overt",
        "conceal_from": [], "targets": [],
    }

    # Consciousness gate (rare at opening, but a scenario may start someone
    # unconscious/asleep): overlay the establish diff onto committed conditions.
    amap = apply_awareness_diff(awareness_map(chat["id"]), diff)
    for p in perceivers:
        p["awareness"] = awareness_of(amap, p["name"])
    awake_perceivers = [p for p in perceivers
                        if p.get("awareness") not in NON_AWAKE_GATED]

    # One canonical pronoun map per pass, sliced to each observer's
    # recognition below -- see _pronouns_for_perceiver.
    all_pronouns = _observed_pronouns(chat["id"], ctx.cast)

    payload = {
        "declared_act": declared,
        "cast_pronouns": {},  # scoped per observer in the payload closure below
        "scene_opening": True,
        "note": "This is a scene opening. Each perceiver perceives their surroundings "
                "and their own initial state. The player's entity_state contains their "
                "opening posture and activity. Sensory_events are objective environmental "
                "signals — filter them by spatial relation and senses for each perceiver.",
        "output_reminder": "You MUST return a view for EVERY perceiver, keyed by 'id'.",
        "variant_seed": nonce,
    }

    def _opening_payload(perceiver):
        scoped = copy.deepcopy(payload)
        scoped["cast_pronouns"] = _pronouns_for_perceiver(
            all_pronouns, perceiver, known)
        scoped["scene"] = _observer_scene_payload(sc, perceiver)
        scoped["declared_act"]["player_seed"] = (
            declared["player_seed"]
            if str(perceiver["id"]) == "player"
            else ""
        )
        if str(perceiver["id"]) != "player":
            can_see_player = (
                visual_level_between(sc, perceiver["name"], p_name) != "none"
            )
            if not perceiver.get("knows_identity"):
                label = _unknown_actor_label(p_name, p_appearance)
                scoped["declared_act"]["actor_name"] = label
                scoped["declared_act"]["actor_id"] = "UNKNOWN"
            if not can_see_player:
                scoped["declared_act"]["actor_present_appearance"] = ""
        return scoped

    raw_views = _per_observer_model_views(
        awake_perceivers, _opening_payload)
    if not raw_views:
        raw_views = _fallback_perception_views(awake_perceivers, [], known=known)
    clean_views = _normalise_views(raw_views, awake_perceivers)

    roster = _identity_roster(p_name, p_appearance, ctx.cast)
    for p in perceivers:
        pid = str(p["id"])
        if p.get("awareness") in NON_AWAKE_GATED:
            clean_views[pid] = _compose_residue_view(p["awareness"])
            continue
        view = clean_views.get(pid)
        if not view:
            parts = [f"You are in {p.get('room_name')}."]
            if p.get("room_notes"):
                parts.append(p["room_notes"])
            es = p.get("entity_state") or {}
            if es.get("posture"):
                parts.append(f"You are {es['posture']}.")
            if es.get("activity"):
                parts.append(f"You are {es['activity']}.")
            if es.get("held_items"):
                parts.append(f"You hold: {', '.join(es['held_items'])}.")
            view = " ".join(parts)
        view = _scrub_view_for(
            ctx, "perception_establish", view, p["name"], known, roster)
        clean_views[pid] = _dedupe_view_sentences(view) or None

    return {
        "views": clean_views,
        "observations": _observations_from_clean_views(clean_views),
    }

def perception_act(ctx, nonce):
    chat = ctx.chat
    interp = ctx.director_interpret
    sc = get_scene(chat["id"], chat)
    pers = persona_of(chat)
    known = wget(chat["id"], "known", {})
    action = interp.get("action")
    if not isinstance(action, dict):
        action = {}

    p_room = ctx.get("_player_room")
    if p_room is None:
        p_room = _resolve_player_room(sc, pers, interp, ctx.cast, ctx.input)
        ctx["_player_room"] = p_room

    p_rdata = (sc.get("rooms") or {}).get(p_room) if p_room else None
    p_name = pers.get("name") or persona_name(pers)
    p_appearance = _appearance_as_prose(appearance_of(
        p_name, pers.get("appearance") or persona_appearance(pers), sc))
    # A physical disguise conceals the actor's real appearance from observers:
    # p_visible is what is actually SEEN (disguised form when active), fed to
    # both the LLM and the deterministic injection below so a concealed feature
    # is never rendered as perceived.
    p_visible, p_disguise, p_disguise_known = _subject_disguise_context(
        chat["id"], p_name, p_appearance, known)
    p_disguise_terms = (active_disguises(chat["id"]).get(str(p_name).casefold())
                        or {}).get("concealed_terms") or []

    speech_elems = [
        e for e in (interp.get("sequence") or [])
        if e.get("type") == "speech" and e.get("text")
    ]
    if not speech_elems and interp.get("speech"):
        speech_elems = [{"type": "speech", "text": interp["speech"],
                         "volume": interp.get("speech_volume", "normal"), "tone": ""}]

    # Observer-facing action text is the intent-free `observable` surface, never
    # the actor's intent-laden `attempt` -- a mental beat (observable "") is
    # skipped so it never reaches the empty-view fallback below.  Concealed
    # actions are also skipped: action_desc feeds the deterministic
    # _ensure_environment fallback that runs for EVERY perceiver, and a
    # concealed action's observable surface must not reach perceivers it is
    # hidden from (mirroring the action_elems filter below).
    action_desc = ""
    for e in (interp.get("sequence") or []):
        if e.get("type") == "action" and e.get("visibility") != "concealed":
            surface = observable_action_text(e)
            if surface:
                action_desc = surface
                break

    # Concealed speech elements are withheld from the perceiver payload for
    # the same reason as concealed actions: player_speech is embedded in
    # action_onset (declared_act) which goes to the perception LLM, and a
    # concealed line's text must not reach perceivers it is hidden from.
    # The conceal_from list is preserved in the concealed_actions metadata
    # below so the LLM still knows a concealed line existed.
    overt_player_speech = [
        {"text": e.get("text"), "volume": e.get("volume", "normal"),
         "tone": e.get("tone", ""),
         "visibility": e.get("visibility", "overt"),
         "conceal_from": e.get("conceal_from") or []}
        for e in speech_elems
        if e.get("visibility") != "concealed"
    ]

    # The sequence handed to the perception LLM is the observer-facing
    # projection: intent-free surfaces only, intent ledger stripped, mental
    # beats dropped. action_attempt (the scalar mirror) follows the same
    # surface -- action.get("attempt") is the actor's raw framing and, being
    # the FIRST element, is frequently the mental beat ("remember the runes").
    # Concealed actions are filtered OUT of the sequence entirely: every
    # perceiver in this call is a non-actor (the actor is the player), so a
    # concealed action's observable surface has no legitimate audience here.
    # The concealed action metadata is preserved in the concealed_actions
    # list on the payload (see perception_outcome's equivalent).
    observer_sequence = [
        e for e in _observer_facing_sequence(interp.get("sequence"))
        if e.get("visibility") != "concealed"
    ]
    observer_action_attempt = next(
        (e["attempt"] for e in observer_sequence
         if e.get("type") == "action" and e.get("attempt")), None)

    # Build the concealed_actions metadata list (mirrors perception_outcome):
    # the LLM is told a concealed action existed and who it is hidden from,
    # without receiving the observable surface in the main sequence.
    concealed_actions = []
    for e in (interp.get("sequence") or []):
        if e.get("type") == "action" and e.get("visibility") == "concealed":
            concealed_actions.append({
                "actor": p_name,
                "attempt": observable_action_text(e),
                "conceal_from": e.get("conceal_from") or [],
            })
    for e in speech_elems:
        if e.get("visibility") == "concealed":
            concealed_actions.append({
                "actor": p_name,
                "attempt": e.get("text"),
                "conceal_from": e.get("conceal_from") or [],
            })

    # Determine whether the scalar speech fields are concealed.  When the
    # primary speech is concealed, passing the raw text as an unmarked scalar
    # would leak it to every perceiver; withhold the text and mark it.
    raw_speech = interp.get("speech")
    raw_speech_volume = interp.get("speech_volume") or "normal"
    primary_speech_concealed = any(
        e.get("visibility") == "concealed" and e.get("text") == raw_speech
        for e in speech_elems
    )

    # Build action onset for reaction eligibility
    action_onset = {
        "actor_id": "PLAYER",
        "actor": p_name,
        "actor_name": p_name,
        "actor_room": p_room,
        "actor_room_name": (p_rdata or {}).get("name") or p_room,
        "actor_present_appearance": p_visible,
        "sequence": observer_sequence,
        "player_speech": overt_player_speech,
        "speech": "" if primary_speech_concealed else raw_speech,
        "speech_volume": raw_speech_volume,
        "speech_concealed": primary_speech_concealed,
        "action_attempt": observer_action_attempt,
        "visibility": action.get("visibility", "overt"),
        "conceal_from": action.get("conceal_from") or [],
        "targets": action.get("targets") or [],
        "commitment": action.get("commitment", "contestable"),
    }
    if p_disguise:
        action_onset["subject_disguise"] = p_disguise

    perceivers = []
    flow = interp.get("flow")
    if not isinstance(flow, dict):
        flow = {}
        
    for c in ctx.cast:
        if c["id"] not in flow.get("reactors", []):
            continue
        sh, act, _ = sheet_state(c)
        r = character_room(sc, sh)
        rel = spatial_rel(sc, p_room, r)
        # The actor may be part-way through a boundary this observer is
        # standing behind -- going through a doorway is watched from the room
        # behind rather than vanishing the instant the position field changed.
        # Floors sight at `shapes`; it never grants more than the light allows.
        if crossing_visible_from(sc, r, p_name):
            rel = {**rel, "crossing": True}
        # A carried body's position derives to its carrier's, so an enclosed
        # actor reads as `same_room` with everyone around the carrier -- which
        # answers sight before barrier or light is consulted.
        if containment_conceals(sc, character_name(sh), p_name):
            rel = {**rel, "concealed": True}
        rdata = (sc.get("rooms") or {}).get(r) if r else None

        perceivers.append({
            "id": c["id"], "name": character_name(sh), "room": r,
            "room_name": (rdata or {}).get("name") or r or "an unspecified area",
            "room_notes": ((rdata or {}).get("notes") or _room_notes_from_lore(r, ctx, sc)),
            "ambient_location": _ambient_location_for(sc, r),
            "visible_rooms": visible_adjacent_rooms(sc, r),
            "senses": senses_of(sh),
            "attention": act.get("goal") or "ambient",
            "spatial_to_actor": rel,
            "visual_channel_to_actor": has_visual(rel),
            "scent_channel_to_actor": scent_level(rel),
            "proximity_to_actor": proximity_rel(
                sc, character_name(sh), p_name),
            "knows_identity": p_name in (known.get(character_name(sh)) or []),
            "behind_rooms": _behind_rooms(sc, character_name(sh)),
            "focus_target": _focus_target(sc, character_name(sh)),
        })

    # Input-side hygiene (defense-in-depth under the output scrub below):
    # when NO perceiver in this call recognizes the player, the model has
    # no legitimate use for the canonical name at all -- handing it over
    # anyway ("actor_name": "Hinami") is exactly the "objective state
    # copied into a context with an instruction to ignore it" pattern the
    # engine forbids for character agents, and is why even strong models
    # wrote the name into stranger views.
    # Strip identity from the VISIBLE (disguise-adjusted) appearance, never the
    # true one -- otherwise a disguised subject's concealed features leak into
    # the stranger-facing safe form.
    # Consciousness gate: a non-awake reactor is excluded from the LLM call and
    # gets a deterministic residue below (P3 also drops them from flow.reactors
    # upstream; this is defense-in-depth). Onset conditions read the committed
    # map -- a knockout THIS beat resolves later, so the reactor is awake now.
    amap = awareness_map(chat["id"])
    for p in perceivers:
        p["awareness"] = awareness_of(amap, p["name"])
    awake_perceivers = [p for p in perceivers
                        if p.get("awareness") not in NON_AWAKE_GATED]

    p_appearance_safe = _strip_identity_tokens(p_visible, [p_name])
    if awake_perceivers and not any(p.get("knows_identity") for p in awake_perceivers):
        neutral = _unknown_actor_label(p_name, p_visible)
        action_onset = {**action_onset, "actor": neutral,
                        "actor_name": neutral,
                        "actor_present_appearance": p_appearance_safe}
    # The same argument as the identity strip above, for the OTHER thing this
    # payload hands over unconditionally. When no perceiver in this call has a
    # visual channel to the actor, none of them has any legitimate use for what
    # the actor LOOKS like -- and handing it over anyway is the exact pattern
    # the block above forbids: objective state copied into a context with an
    # implicit instruction not to use it.
    #
    # Observed live: the player inside a sealed interior room with no
    # adjacency to the room its owner was standing in, and
    # the perceiver's view came back "You see A tall figure in a grey
    # travelling coat, hood raised.;
    # clothing state: ..." -- the appearance string verbatim, capital and
    # trailing fragment included, for a body that was not visible at all.
    #
    # The deterministic injector was already gated on has_visual and correctly
    # stayed silent; this closes the channel that bypassed it. What the
    # perceiver CAN still feel (weight, movement, contact) is unaffected --
    # this removes only the look of a body nobody can see.
    if awake_perceivers and not any(
            p.get("visual_channel_to_actor") for p in awake_perceivers):
        action_onset = {**action_onset, "actor_present_appearance": "",
                        "actor_not_visible": True}

    # One canonical pronoun map per pass, sliced to each observer's
    # recognition below -- see _pronouns_for_perceiver.
    all_pronouns = _observed_pronouns(chat["id"], ctx.cast)

    payload = {
        "declared_act": action_onset,
        "concealed_actions": [],
        "cast_pronouns": {},  # scoped per observer in the payload closure below
        "note": (
            "a private thought exists but its contents are withheld"
            if interp.get("private_thought") else "no private thought"
        ),
        "output_reminder": "You MUST return a view for EVERY perceiver, keyed by 'id'.",
        "variant_seed": nonce,
    }

    def _act_payload(perceiver):
        scoped = copy.deepcopy(payload)
        scoped["cast_pronouns"] = _pronouns_for_perceiver(
            all_pronouns, perceiver, known)
        scoped["scene"] = _observer_scene_payload(sc, perceiver)
        declared_for_observer = scoped["declared_act"]
        if not perceiver.get("knows_identity"):
            neutral = _unknown_actor_label(p_name, p_visible)
            declared_for_observer["actor"] = neutral
            declared_for_observer["actor_name"] = neutral
            declared_for_observer["actor_id"] = "UNKNOWN"
        if not perceiver.get("visual_channel_to_actor"):
            declared_for_observer["actor_present_appearance"] = ""
            declared_for_observer["actor_not_visible"] = True
        authorized = []
        authorized_concealed = []
        for event in _observer_facing_sequence(interp.get("sequence")):
            if event.get("visibility") != "concealed":
                authorized.append(event)
                continue
            # An empty conceal_from means hidden from every non-actor. A
            # populated list is an explicit excluded audience.
            if (
                event.get("conceal_from")
                and not _concealed_from_perceiver(event, perceiver)
            ):
                authorized.append(event)
                authorized_concealed.append({
                    "actor": declared_for_observer.get("actor"),
                    "kind": event.get("type"),
                    "surface": event.get("attempt") or event.get("text") or "",
                })
        declared_for_observer["sequence"] = authorized
        declared_for_observer["player_speech"] = [
            event for event in authorized if event.get("type") == "speech"
        ]
        declared_for_observer["speech"] = next(
            (
                event.get("text") for event in authorized
                if event.get("type") == "speech"
            ),
            "",
        )
        scoped["concealed_actions"] = authorized_concealed
        return scoped

    clean_views = _per_observer_model_views(
        awake_perceivers, _act_payload)

    # Deterministic action delivery uses the intent-free `observable` surface,
    # NOT the raw attempt. Each element is tagged with its surface here; a
    # mental beat (observable "") is dropped so it is never injected into any
    # observer's view (an observer cannot perceive "remember the runes").
    action_elems = []
    for e in (interp.get("sequence") or []):
        if e.get("type") != "action":
            continue
        surface = observable_action_text(e)
        if surface:
            action_elems.append({**e, "_surface": surface})
    # Mirror the action_elems concealment filter for speech: a speech
    # element marked visibility:'concealed' must never reach the blanket
    # hear_level-based injection below, which has no concept of an
    # excluded audience.  The perception LLM also receives only overt
    # speech/actions in the declared_act payload above (concealed entries
    # are listed separately in concealed_actions metadata), so both the
    # deterministic and LLM channels agree: a concealed line reaches only
    # the perceivers the conceal_from list excludes.
    audible_speech_elems = list(speech_elems)

    # Each perceiver's own name/alias forms, so the action backstop renders
    # them in second person inside their OWN view: the player's declared
    # observable is authored in third person and names its targets, so
    # "reaches toward Dr. Moon" reached Dr. Moon's own view naming her.
    # See agents/common.py's _self_second_person.
    self_forms_by_name = {}
    for c in ctx.cast:
        _sh = json.loads(c["sheet"])
        self_forms_by_name[character_name(_sh)] = character_scene_keys(_sh)

    onset_targets = {str(t).casefold() for t in (action.get("targets") or [])}
    onset_loud = any(str(e.get("volume", "")).lower() in ("loud", "shout")
                     for e in audible_speech_elems)
    for p in perceivers:
        pid = str(p["id"])
        if p.get("awareness") in NON_AWAKE_GATED:
            p_name_cf = p["name"].casefold()
            cause = (amap.get(p_name_cf) or {}).get("cause", "").lower()
            pain = any(w in cause for w in
                       ("injur", "wound", "blood", "hurt", "struck", "broke", "burn"))
            clean_views[pid] = _compose_residue_view(
                p["awareness"], targeted=(p_name_cf in onset_targets),
                loud_event=onset_loud, pain=pain)
            continue
        rel = p.get("spatial_to_actor") or {}
        vis = p.get("visual_channel_to_actor", False)
        knows_identity = bool(p.get("knows_identity"))
        display = p_name if knows_identity else _unknown_actor_label(p_name, p_visible)
        view = clean_views.get(pid)
        view = _ensure_environment(view, p, display, rel, vis, action_desc)

        if vis:
            # For a stranger, the pasted appearance summary must itself be
            # name-stripped -- persona summaries routinely lead with the
            # canonical name, which made this deterministic injection a
            # leak channel of its own.
            visible_description = (
                p_appearance_safe
                if not knows_identity
                else display
            )
            view = _inject_visible_actor(
                view,
                display=display,
                appearance=visible_description,
                relation=rel,
            )

        delivered = set()
        for e in audible_speech_elems:
            if e.get("visibility") == "concealed" and (
                not e.get("conceal_from")
                or _concealed_from_perceiver(e, p)
            ):
                continue
            level = hear_level(
                rel, e.get("volume", "normal"),
                proximity=p.get("proximity_to_actor"),
            )
            view = _inject_dialogue(
                view, display, e.get("text"),
                level, e.get("volume", "normal"),
                _in_plain_view(rel, vis),
                conducted=bool(rel.get("inside_source")),
            )
        can_see = _in_plain_view(rel, vis)
        for e in action_elems:
            if e.get("visibility") == "concealed" and (
                not e.get("conceal_from")
                or _concealed_from_perceiver(e, p)
            ):
                continue
            if entity_arc(sc, p["name"], p_name) == "rear":
                continue
            view = _inject_action(
                view, display, e["_surface"], can_see,
                event_id=e.get("event_id"), delivered=delivered,
                self_forms=self_forms_by_name.get(p["name"]) or [p["name"]],
            )
        # Deterministic identity floor, LAST: the LLM's free prose was
        # never checked against knows_identity, so a model that wrote the
        # player's canonical name into a stranger's view walked straight
        # past the gate above. Quoted speech survives verbatim (a name
        # introduced aloud this beat is legitimate sensory signal;
        # recognition itself only flips at commit).
        if not knows_identity:
            view, leaked = _scrub_unknown_identities(
                view,
                allowed_forms=[p["name"]],
                unknown_sources=[{"name": p_name,
                                  "appearance": p_visible}],
            )
            if leaked:
                ctx.warnings.append(
                    f"perception_act: scrubbed unearned identity {leaked} "
                    f"from the view of {p['name']}")
        clean_views[pid] = _dedupe_view_sentences(view) or None

    _disguise_leak_check(ctx, "perception_act", clean_views, perceivers,
                         p_name, p_disguise_terms, p_disguise_known)
    return {
        "views": clean_views,
        "observations": _observations_from_clean_views(clean_views),
    }

def _touch_only_sources(scene, perceiver_name, spatial_to_sources,
                        visual_channel_to_sources):
    """Return the set of source names who are touch-only for this perceiver.

    A source is touch-only when the perceiver cannot SEE it (no visual
    channel) but CAN feel it -- the two bodies are in physical contact
    (scene.contacts) or one is contained within the other (scene.contained).

    This is the structural basis for surface-translation: the resolved_event
    prose names the acts a touch-only source is performing, and the
    perception LLM -- able to feel the body but not see it -- resolves those
    acts through the touch channel, effectively learning what the hidden
    body is doing from the omniscient prose.  _surface_translate_event
    replaces those act-naming sentences with neutral surface-sensation
    descriptions so only motion/pressure reaches the perceiver.
    """
    if not scene or not perceiver_name:
        return set()
    p_cf = str(perceiver_name).casefold()
    # --- contact-based touch channel ---
    contacts = scene.get("contacts") or []
    contact_names = set()
    for c in contacts:
        if not isinstance(c, dict):
            continue
        actor = str(c.get("actor") or "").strip()
        target = str(c.get("target") or "").strip()
        if actor.casefold() == p_cf:
            contact_names.add(target)
        elif target.casefold() == p_cf:
            contact_names.add(actor)
    # --- containment-based touch channel ---
    # Read through spatial's resolver, not scene["contained"] alone: a scene
    # can also express one body inside another as a ROOM parented to that body,
    # and reading the ledger directly made that form deliver NO touch at all --
    # the body around them felt nothing, which is the wrong half of "concealed
    # but felt" to lose. hiding_holders_of understands both forms.
    containment_names = set(hiding_holders_of(scene, perceiver_name))
    for other in (scene.get("positions") or {}):
        if str(other).casefold() != p_cf and perceiver_name in hiding_holders_of(
                scene, other):
            containment_names.add(str(other))
    contained = scene.get("contained") or {}
    if isinstance(contained, dict):
        for subject, record in contained.items():
            holder = str(
                record.get("in") if isinstance(record, dict) else record
                or ""
            ).strip()
            s_name = str(subject).strip()
            if s_name.casefold() == p_cf and holder:
                containment_names.add(holder)
            elif holder.casefold() == p_cf and s_name:
                containment_names.add(s_name)
    touch_candidates = {n for n in (contact_names | containment_names)
                        if n and n.casefold() != p_cf}
    # A touch-only source: in spatial range, no visual channel, in physical contact.
    out = set()
    for name in touch_candidates:
        if name in spatial_to_sources and not visual_channel_to_sources.get(name, False):
            out.add(name)
    return out


def _surface_translate_event(event_text, touch_only_sources):
    """Replace act-naming sentences for touch-only sources with surface-sensation prose.

    The resolved_event text is omniscient: it names what every actor is
    doing ("she curls her fingers to rub her clit").  A perceiver who can
    FEEL a source but not SEE it receives this text through the touch
    channel and the perception LLM translates the named act into felt
    sensation -- effectively learning the hidden body's exact actions from
    prose that was supposed to be filtered by channel.

    This function structurally withholds the act-naming language: sentences
    that describe actions BY a touch-only source are replaced with a neutral
    surface-sensation description that conveys only motion and pressure at
    the contact surface, never what the hidden body is doing or why.

    General by design -- works for any touch-only situation: a body held in
    a hand, sealed in a container, pressed against a wall, etc.
    """
    if not event_text or not touch_only_sources:
        return event_text

    # Free prose cannot be security-matched reliably: a later sentence may use
    # a pronoun or paraphrase the act. Fail closed for the whole omniscient
    # event and let the deterministic touch/contact facts supply the surface.
    return "You register motion and pressure at the contact surface."


# A sentence that opens with a bare pronoun continues the previous sentence's
# subject rather than naming one of its own.
_PRONOUN_SUBJECT = re.compile(
    r"^[\"'“‘(\[]*\s*(?:he|she|they|it|his|her|hers|their|theirs|its|him|them)\b",
    re.I,
)

_REDACTED_NOTICE = "[Some parts of the event are not perceptible to you.]"


def _redact_concealed_from_event(event_text, concealed_for_this_perceiver):
    """Strip sentences describing concealed actions out of the omniscient
    resolved_event before it reaches one perceiver's payload.

    This is a structural redaction rather than an instruction to the perception
    model, and it is the load-bearing guarantee for concealment -- so its
    limits matter more than its mechanism.

    A sentence goes if it names a concealed actor, OR if it continues a redacted
    sentence with a bare pronoun subject. The continuation rule is the whole
    point: the name-only test this replaced passed the audit's own worked
    example straight through -- "Mara turns to the shelf. She slips the vial
    into her sleeve." redacted sentence one and delivered sentence two, which
    is the sentence carrying the secret. A sentence that names a DIFFERENT
    actor ends the continuation, so an unrelated beat that merely follows a
    concealed one is not swallowed.

    What still escapes: a paraphrase that gives the concealed act a fresh
    explicit subject ("the vial disappears into a sleeve") names nobody and
    reads as a new subject, so nothing here catches it. Prose matching cannot
    close that -- the structural answer is to carry the actor's id on the event
    element and redact on identity, never on text (pipeline_audit.md, cross-seam
    pattern 1). Until the Director emits that, this is a floor, not a proof, and
    the perception prompt's own instruction remains the second layer.

    Deliberately over-redacts in one direction: a concealed actor's OVERT acts
    in the same beat are stripped too, because "this sentence names Mara" does
    not say which of Mara's acts it describes. Losing an overt beat is a
    degradation; delivering a concealed one is a leak, and the two are not
    equally bad.
    """
    if not event_text or not concealed_for_this_perceiver:
        return event_text

    concealed_names = {
        str((entry or {}).get("actor") or "").strip().casefold()
        for entry in concealed_for_this_perceiver
        if str((entry or {}).get("actor") or "").strip()
    }
    if not concealed_names:
        return event_text

    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(event_text) if s.strip()]
    if not sentences:
        # A single unpunctuated clause cannot be split, so there is no safe
        # subset to keep.
        return _REDACTED_NOTICE

    kept = []
    continuing = False
    for sentence in sentences:
        folded = sentence.casefold()
        names_concealed = any(
            re.search(rf"\b{re.escape(name)}\b", folded)
            for name in concealed_names
        )
        if names_concealed:
            continuing = True
            continue
        if continuing and _PRONOUN_SUBJECT.match(sentence):
            continue
        continuing = False
        kept.append(sentence)

    return " ".join(kept) if kept else _REDACTED_NOTICE

def perception_outcome(ctx, nonce):
    chat = ctx.chat
    sc = get_scene(chat["id"], chat)
    pers = persona_of(chat)
    known = wget(chat["id"], "known", {})
    res = ctx.get("director_resolve", {})
    interp = ctx.get("director_interpret", {})
    reactors = set((interp.get("flow") or {}).get("reactors") or [])

    # Room dedup runs BEFORE this stage's merge (Phase-2 re-scope of the
    # Phase-1 one-beat skew): commit will deterministically rekey/redirect
    # colliding minted room keys, and it is a pure function of the stored
    # scene + registry + diff -- all unchanged between here and commit --
    # so running it on a COPY of the diff yields the exact same renames.
    # Without this, perception_outcome rendered the pre-dedup key for one
    # beat while the committed world carried the canonical one. Local
    # import: commit.py must stay ignorant of agent modules (facade rule),
    # so the dependency points this way only (same precedent as commit's
    # own _is_player).
    from commit import dedup_minted_rooms

    diff = copy.deepcopy(res.get("state_diff") or {})
    dedup_minted_rooms(chat["id"], sc, diff)
    prev_scene = sc
    sc = merge_scene_with_diff(sc, diff)

    # Refresh per-character orientation (came_from/focus/facing) on the merged
    # scene. infer_* run at COMMIT, which is AFTER the narrator -- so without
    # this, the FOV/egocentric derivations below AND the narrator's spatial
    # frame would use LAST beat's facing/came_from on exactly the movement beats
    # they exist for (a room just entered, rendered with the prior heading; the
    # deterministic spatial_facts contradicting the correct view). Pure and
    # deterministic given (prev_scene, sc) -- commit re-runs them to the same
    # result. Stashed on ctx so the narrator derives its spatial_frame/
    # spatial_facts from this same oriented scene, not the stale committed KV.
    try:
        from spatial_frames import infer_came_from, infer_focus, infer_facing
        _o_names = [character_name(json.loads(c["sheet"])) for c in ctx.cast]
        infer_came_from(chat["id"], ctx.turn.frame_id, prev_scene, sc, _o_names)
        infer_focus(chat["id"], ctx.turn.frame_id, prev_scene, sc, res, _o_names)
        infer_facing(chat["id"], ctx.turn.frame_id, prev_scene, sc, _o_names)
    except Exception as _oe:  # orientation is best-effort here; commit is authoritative
        ctx.warnings.append(f"perception_outcome: orientation refresh skipped ({_oe})")
    ctx._extra["outcome_scene"] = sc

    # Prefer re-resolving against the just-merged (post-resolution) scene
    # over reusing ctx["_player_room"]: that value was cached during the
    # action-onset pass (perception_act), before this turn's movement was
    # validated/applied by director_resolve. Reusing it unconditionally
    # would keep describing the player's pre-move surroundings after a
    # successful move, or the (rejected) destination after a blocked one.
    # Only fall back to the cached value when the scene genuinely has no
    # resolvable position for the player (e.g. positions were never
    # tracked for them).
    p_room = _resolve_player_room(sc, pers, interp, ctx.cast, ctx.input) \
        or ctx.get("_player_room")
    ctx["_player_room"] = p_room

    p_name = pers.get("name") or persona_name(pers)
    p_appearance_true = _appearance_as_prose(appearance_of(
        p_name, pers.get("appearance") or persona_appearance(pers), sc))
    # Conceal a disguised subject's real appearance in every observer's outcome
    # view: p_appearance becomes the disguised (visible) form, so present_
    # appearances and the deterministic injection below never expose concealed
    # features. The knowledge layer (who KNOWS the truth) rides the payload.
    p_appearance, p_disguise, p_disguise_known = _subject_disguise_context(
        chat["id"], p_name, p_appearance_true, known)
    p_disguise_terms = (active_disguises(chat["id"]).get(str(p_name).casefold())
                        or {}).get("concealed_terms") or []

    # background_react (agents/background.py) is a separate, later stage
    # in the plan -- its output is merged in HERE rather than by mutating
    # res["dialogue_log"] in place, because director_resolve's own step/
    # variant was already persisted before background_react ran; mutating
    # the shared dict afterward would desync the persisted director_resolve
    # step from what perception/narrator actually rendered, and a rerun
    # from this step onward would silently lose the background reaction.
    br = ctx.get("background_react") or {}
    _fired = br.get("reactions")
    if _fired is None:  # legacy single-entry shape
        _fired = ([{"name": br.get("name"), "dialogue_log_entry": br["dialogue_log_entry"],
                    "action": br.get("action", "")}]
                  if br.get("fired") and br.get("dialogue_log_entry") else [])
    else:
        _fired = [r for r in _fired if isinstance(r, dict) and r.get("dialogue_log_entry")]
    br_entries = [r["dialogue_log_entry"] for r in _fired]

    raw_dlog = list(res.get("dialogue_log") or [])
    raw_dlog.extend(br_entries)
    enriched_dlog = []
    for d in raw_dlog:
        speaker = d.get("speaker", "?")
        if is_player_speaker(speaker, chat):
            sp_room = p_room
        else:
            sp_room = cast_room(sc, speaker, ctx.cast)
        enriched_dlog.append({
            "speaker": speaker, "exact_quote": d.get("exact_quote", ""),
            "volume": d.get("volume", "normal"),
            "intended_target": d.get("intended_target"),
            "tone": d.get("tone", ""), "speaker_room": sp_room,
            "visibility": d.get("visibility", "overt"),
            "conceal_from": d.get("conceal_from") or [],
            # medium:'comm' carries a transmitted line to its addressed party
            # across a physical barrier (see the perception_outcome injection).
            "medium": d.get("medium"),
        })

    # The model receives no raw dialogue transcript. Every spoken line,
    # including player and concealed speech, is delivered below through the
    # deterministic per-observer hearing/concealment gate.
    npc_dlog = list(enriched_dlog)

    # ...but the no-LLM fallback is NOT that gate. _fallback_perception_views
    # admits a line on same-room alone -- no concealment check, no hear_level --
    # so handing it the full log would render every concealed line verbatim to
    # every co-located perceiver on exactly the turns where the model failed.
    # It also has no per-observer vantage to decide a partial conceal_from, so
    # it fails closed on the whole class, and drops the player's own lines the
    # way it always did.
    fallback_dlog = [
        d for d in enriched_dlog
        if d.get("visibility") != "concealed"
        and not is_player_speaker(d.get("speaker", ""), chat)
    ]

    sources = [{"name": p_name, "room": p_room}]
    for _e in br_entries:
        sources.append({"name": _e.get("speaker"), "room": cast_room(sc, _e.get("speaker"), ctx.cast)})
    concealed = []
    for a in (interp.get("actions") or
              ([interp["action"]] if interp.get("action") else [])):
        if isinstance(a, dict) and a.get("visibility") == "concealed":
            concealed.append({"actor": p_name,
                              "attempt": observable_action_text(a),
                              "conceal_from": a.get("conceal_from") or []})
    for d in enriched_dlog:
        if d.get("visibility") == "concealed":
            concealed.append({"actor": d.get("speaker"), "attempt": d.get("exact_quote"),
                              "conceal_from": d.get("conceal_from") or []})

    for c in ctx.cast:
        d = ctx.character_results.get(c["id"])
        sh = json.loads(c["sheet"])
        if d and (d.get("sequence") or d.get("speech") or d.get("action")):
            sources.append({"name": character_name(sh),
                            "room": character_room(sc, sh)})
        for a in ((d or {}).get("actions") or []):
            if a.get("visibility") == "concealed":
                concealed.append({"actor": character_name(sh),
                                  "attempt": observable_action_text(a),
                                  "conceal_from": a.get("conceal_from") or []})
        reaction = ctx.reaction_results.get(c["id"])
        for a in ((reaction or {}).get("actions") or
                  [e for e in ((reaction or {}).get("sequence") or [])
                   if isinstance(e, dict) and e.get("type") == "action"]):
            if isinstance(a, dict) and a.get("visibility") == "concealed":
                concealed.append({
                    "actor": character_name(sh),
                    "attempt": observable_action_text(a),
                    "conceal_from": a.get("conceal_from") or [],
                })

    appearances = {p_name: p_appearance}

    # Additional human players: each gets a real perceiver entry at their
    # OWN tracked position (room_of, same lookup used for NPCs and the
    # primary player) -- not hardcoded to the primary player's room. Only
    # fall back to the primary player's room when the extra player has no
    # tracked position yet (e.g. they were only just attached and have
    # never been placed anywhere). They're a genuine dialogue/action source
    # for everyone else's view too, exactly like an NPC -- not a silent
    # observer.
    #
    # Every extra player is appended to `sources` HERE, before any
    # perceiver's spatial_to_sources / visual_channel_to_sources maps are
    # computed below -- previously the primary player's perceiver was built
    # first (so it had no channel to any co-player at all), and each extra
    # player's perceiver was built as its own source-append happened (so
    # extra A had no channel to extra B, only vice versa).
    other_players = interp.get("other_players") or {}
    extra_entries = []
    for extra in ctx.extra_players:
        pid_key = str(extra["persona_id"])
        e_name = extra["name"]
        e_room = room_of(sc, e_name) or p_room
        sources.append({"name": e_name, "room": e_room})
        appearances[e_name] = _appearance_as_prose(appearance_of(
            e_name, extra.get("appearance") or f"{e_name}, a person of unremarkable appearance.", sc))
        entry = other_players.get(pid_key) or {}
        for e in (entry.get("sequence") or []):
            if e.get("type") == "action" and e.get("attempt") and e.get("visibility") == "concealed":
                concealed.append({"actor": e_name, "attempt": e.get("attempt"),
                                  "conceal_from": e.get("conceal_from") or []})
        extra_entries.append((extra, pid_key, e_name, e_room))

    p_rdata = (sc.get("rooms") or {}).get(p_room) if p_room else None
    # name -> cast id, so perception can pull each present character's authored
    # `manifest` (surface demeanor + tells) and gate delivery per observer.
    cast_by_name = {character_name(json.loads(c["sheet"])): c["id"] for c in ctx.cast}

    perceivers = [{
        "id": "player", "name": p_name, "room": p_room,
        "room_name": (p_rdata or {}).get("name") or p_room or "an unspecified area",
        "room_notes": ((p_rdata or {}).get("notes") or _room_notes_from_lore(p_room, ctx, sc)),
        "ambient_location": _ambient_location_for(sc, p_room),
        "visible_rooms": visible_adjacent_rooms(sc, p_room),
        "senses": senses_of(pers), "attention": "engaged",
        "knows_identity": True,
        **_source_channels(sc, p_name, p_room, sources),
        "proximity_to_sources": _proximity_to_sources(sc, p_name, sources),
        "behind_sources": _behind_sources(sc, p_name, sources),
        "room_layout": room_layout(sc, p_name),
        "behind_rooms": _behind_rooms(sc, p_name),
        "focus_target": _focus_target(sc, p_name),
        "source_manifest": _delivered_manifest(
            ctx, sc, p_name, sources, known, cast_by_name, pers),
        **_perceiver_spatial_facts(sc, p_name, sources),
    }]

    for extra, pid_key, e_name, e_room in extra_entries:
        e_rdata = (sc.get("rooms") or {}).get(e_room) if e_room else None
        perceivers.append({
            "id": f"extra:{pid_key}", "name": e_name, "room": e_room,
            "room_name": (e_rdata or {}).get("name") or e_room or "an unspecified area",
            "room_notes": ((e_rdata or {}).get("notes") or _room_notes_from_lore(e_room, ctx, sc)),
            "ambient_location": _ambient_location_for(sc, e_room),
            "visible_rooms": visible_adjacent_rooms(sc, e_room),
            "senses": senses_of(extra), "attention": "engaged",
            "knows_identity": True,
            **_source_channels(sc, e_name, e_room, sources),
            "proximity_to_sources": _proximity_to_sources(sc, e_name, sources),
            "behind_sources": _behind_sources(sc, e_name, sources),
            "room_layout": room_layout(sc, e_name),
            "behind_rooms": _behind_rooms(sc, e_name),
            "focus_target": _focus_target(sc, e_name),
            "source_manifest": _delivered_manifest(
                ctx, sc, e_name, sources, known, cast_by_name, extra),
            **_perceiver_spatial_facts(sc, e_name, sources),
        })

    for c in ctx.cast:
        sh, act, _ = sheet_state(c)
        r = character_room(sc, sh)
        appearances[character_name(sh)] = _appearance_as_prose(appearance_of(
            character_name(sh), character_appearance(sh), sc))
        rdata = (sc.get("rooms") or {}).get(r) if r else None
        perceivers.append({
            "id": c["id"], "name": character_name(sh), "room": r,
            "room_name": (rdata or {}).get("name") or r or "an unspecified area",
            "room_notes": ((rdata or {}).get("notes") or _room_notes_from_lore(r, ctx, sc)),
            "ambient_location": _ambient_location_for(sc, r),
            "visible_rooms": visible_adjacent_rooms(sc, r),
            "senses": senses_of(sh),
            "attention": act.get("goal") or "ambient",
            "knows_identity": p_name in (known.get(character_name(sh)) or []),
            **_source_channels(sc, character_name(sh), r, sources),
            "proximity_to_sources": _proximity_to_sources(sc, character_name(sh), sources),
            "behind_sources": _behind_sources(sc, character_name(sh), sources),
            "room_layout": room_layout(sc, character_name(sh)),
            "behind_rooms": _behind_rooms(sc, character_name(sh)),
            "focus_target": _focus_target(sc, character_name(sh)),
            "source_manifest": _delivered_manifest(
                ctx, sc, character_name(sh), sources, known, cast_by_name, sh),
        })

    # Consciousness gate: overlay THIS beat's just-resolved awareness
    # conditions (a knockout resolves before perception_outcome commits) onto
    # the committed map, then tag every perceiver. A non-awake mind (asleep/
    # sedated/unconscious) is EXCLUDED from the LLM call entirely -- it cannot
    # leak a view it was never asked to write -- and receives a deterministic
    # residue below instead. 'dazed' stays in the call (present but degraded).
    amap = apply_awareness_diff(awareness_map(chat["id"]), diff)
    for p in perceivers:
        p["awareness"] = awareness_of(amap, p["name"])
    awake_perceivers = [p for p in perceivers
                        if p.get("awareness") not in NON_AWAKE_GATED]

    resolved_event_text = res.get("resolved_event", "")
    _br_actions = [f"{r.get('name')}: {r['action']}" for r in _fired if r.get("action")]
    if _br_actions:
        resolved_event_text = (resolved_event_text + " " + "; ".join(_br_actions)).strip()

    # STRUCTURAL CONCEALED-ACTION REDACTION
    # The resolved_event prose is omniscient -- it describes ALL actions,
    # including those marked visibility:"concealed".  Passing it unfiltered
    # into the perception payload leaks concealed act details through the
    # LLM's touch/proprioception channel (the model writes the concealed
    # act into the enclosing perceiver's view as subtle body cues).
    #
    # Fix: build a per-perceiver redacted copy.  A concealed action is
    # redacted for every perceiver EXCEPT the actor who performed it (the
    # actor knows their own action).  The per-perceiver copy rides the
    # perceiver dict as ``resolved_event``; the payload's top-level
    # ``resolved_event`` is the globally-redacted version (all concealed
    # actions stripped) so it can never leak even if the model ignores
    # per-perceiver fields.
    for p in awake_perceivers:
        concealed_from_p = [
            c for c in concealed
            if c.get("actor") != p["name"]
        ]
        redacted = _redact_concealed_from_event(
            resolved_event_text, concealed_from_p)
        # STRUCTURAL TOUCH-ONLY SURFACE TRANSLATION
        # After concealed-action redaction, also replace act-naming sentences
        # for sources the perceiver can FEEL but not SEE (touch channel only).
        # Without this, the resolved_event prose names the hidden body's acts
        # and the perception LLM resolves them through touch -- effectively
        # learning what the unseen body is doing from omniscient text.
        touch_only = _touch_only_sources(
            sc, p["name"],
            p.get("spatial_to_sources") or {},
            p.get("visual_channel_to_sources") or {},
        )
        if touch_only:
            redacted = _surface_translate_event(redacted, touch_only)
        p["resolved_event"] = redacted

    # Top-level resolved_event: redact ALL concealed actions (most-redacted
    # version).  Per-perceiver fields override this for actors who should
    # see their own concealed actions.
    _global_redacted = _redact_concealed_from_event(resolved_event_text, concealed)


    # What each source LOOKS like, handed to the model for every source at
    # once. The action-onset pass already strips this when nobody can see the
    # actor (see perception_act's `actor_not_visible`); the outcome pass never
    # got the equivalent, so an enclosed perceiver's payload carried the full
    # appearance of the body enclosing them and the model wrote it into the
    # view -- detail no deterministic gate had pasted. Prompt wording is the
    # wrong instrument here: this module's own comment on the identity strip
    # says why -- objective state copied into a context with an instruction to
    # ignore it is the pattern that made strong models leak in the first place.
    #
    # A source is EXCLUDED FROM ITS OWN TEST: it can always "see" itself, which
    # would keep every appearance alive no matter who else is present, and a
    # perceiver has no use for their own appearance in a second-person view.
    #
    # The question is asked directly rather than read off the perceivers'
    # `visual_channel_to_sources` maps, because those cover only `sources` --
    # the cast who ACTED this beat -- while `appearances` is keyed by the whole
    # cast. Reading the maps would strip the appearance of any bystander who
    # merely stood there, which is a behaviour change well beyond this leak.
    # Same helper, so the answer cannot drift from the one the views use.
    visible_appearances = dict(appearances or {})
    if awake_perceivers and appearances:
        appearance_sources = [{"name": n, "room": room_of(sc, n)}
                              for n in appearances]
        reachable = set()
        for p in awake_perceivers:
            chan = _source_channels(
                sc, p["name"], p.get("room"), appearance_sources,
            )["visual_channel_to_sources"]
            reachable.update(n for n, ok in chan.items()
                             if ok and n != p.get("name"))
        visible_appearances = {n: t for n, t in appearances.items()
                               if n in reachable}

    # One canonical pronoun map per pass, sliced to each observer's
    # recognition below -- see _pronouns_for_perceiver.
    all_pronouns = _observed_pronouns(chat["id"], ctx.cast)

    payload = {
        "resolved_event": _global_redacted,
        "dialogue_order": res.get("dialogue_order"),
        "dialogue_log": [],
        "sources": sources,
        "present_appearances": visible_appearances,
        "concealed_actions": [],
        "cast_pronouns": {},  # scoped per observer in the payload closure below
        "output_reminder": (
            "You MUST return a view for EVERY perceiver in the perceivers list, "
            "keyed by their 'id' field exactly as given."
        ),
        "variant_seed": nonce,
    }

    def _outcome_payload(perceiver):
        scoped = copy.deepcopy(payload)
        scoped["cast_pronouns"] = _pronouns_for_perceiver(
            all_pronouns, perceiver, known)
        scoped["resolved_event"] = perceiver.get("resolved_event") or ""
        scoped["scene"] = _observer_scene_payload(sc, perceiver)
        spatial_channels = perceiver.get("spatial_to_sources") or {}
        visual_channels = perceiver.get("visual_channel_to_sources") or {}
        scoped["sources"] = [
            source for source in sources
            if source.get("name") == perceiver.get("name")
            or source.get("name") in spatial_channels
        ]
        scoped["present_appearances"] = {
            name: appearance
            for name, appearance in appearances.items()
            if name != perceiver.get("name")
            and visual_channels.get(name)
        }
        if p_disguise and (
            perceiver.get("name") == p_name
            or str(perceiver.get("name") or "").casefold()
            in (p_disguise_known or set())
        ):
            scoped["subject_disguise"] = p_disguise
        return scoped

    raw_views = _per_observer_model_views(
        awake_perceivers, _outcome_payload)
    if not raw_views:
        raw_views = _fallback_perception_views(
            awake_perceivers, fallback_dlog, known=known)
    clean_views = _normalise_views(raw_views, awake_perceivers)

    # Identity roster for the deterministic scrub below: every named
    # source/appearance in play this beat, with the uid/alias forms a
    # scene may also carry for cast members.
    cast_aliases = {}
    for c in ctx.cast:
        sh = json.loads(c["sheet"])
        cast_aliases[character_name(sh)] = character_scene_keys(sh)[1:]
    ident_roster = [
        {"name": nm, "appearance": ap, "aliases": cast_aliases.get(nm) or []}
        for nm, ap in appearances.items()
    ]
    for s in sources:
        if s.get("name") and all(r["name"] != s["name"] for r in ident_roster):
            ident_roster.append(
                {"name": s["name"], "appearance": None, "aliases": []})

    # Every perceiver's own name/alias forms, so the deterministic action
    # backstop below can render THEM in second person inside their OWN view
    # instead of pasting the actor's third-person surface verbatim (which
    # named the perceiver and broke the view's person). See
    # agents/common.py's _self_second_person.
    self_forms_by_name = {
        nm: [nm, *(cast_aliases.get(nm) or [])] for nm in appearances
    }
    self_forms_by_name[p_name] = [
        p_name, *((pers.get("identity") or {}).get("aliases") or [])]

    # Only the LAST overt sub-action of each actor's sequence represents
    # their terminal, currently-visible state. Earlier sub-actions (e.g.
    # "stand up", "walk across the room") may have happened before any
    # barrier made them visible to a given perceiver, and this pass has no
    # per-stage room/barrier snapshot to check -- only the post-resolution
    # end state. Injecting every sub-action under that end-state visibility
    # would retroactively grant sight through what was, at the time, a
    # closed door or wall.
    # Delivered as the intent-free `observable` surface, never the raw attempt;
    # a mental beat (observable "") is skipped, so the "last overt action" is
    # the last PERCEIVABLE one (a terminal "remember the runes" does not become
    # what observers see the actor do).
    last_overt_by_actor = {}
    for e in (interp.get("sequence") or []):
        if e.get("type") == "action" and e.get("visibility") != "concealed":
            surface = observable_action_text(e)
            if surface:
                last_overt_by_actor[p_name] = {"actor": p_name, "attempt": surface}
    for c in ctx.cast:
        d = ctx.character_results.get(c["id"])
        sh = json.loads(c["sheet"])
        cname = character_name(sh)
        for e in ((d or {}).get("sequence") or []):
            if e.get("type") == "action" and e.get("visibility") != "concealed":
                surface = observable_action_text(e)
                if surface:
                    last_overt_by_actor[cname] = {"actor": cname, "attempt": surface}

    # DIALOGUE-FIDELITY FLOOR: the complete set of lines actually spoken this
    # beat. Any quoted line in ANY perceiver's view presented as speech whose
    # body is not (a generous substring/fragment match of) one of these is
    # invented -- the perception LLM confabulates memory/backstory callbacks,
    # and director_resolve's resolved_event PROSE can itself carry a line its
    # own dialogue_log backstop already dropped (live t42: a fabricated
    # "trapped under the rubble" player line reached Dr. Moon's view via the
    # prose even though dialogue_log was clean).
    spoken_lines = list(player_speech_lines(interp))
    spoken_lines += [d.get("exact_quote") for d in enriched_dlog]
    for _rmap in (ctx.character_results, ctx.reaction_results):
        for _d in (_rmap or {}).values():
            if not isinstance(_d, dict):
                continue
            for _e in (_d.get("sequence") or []):
                if _e.get("type") == "speech" and _e.get("text"):
                    spoken_lines.append(_e["text"])
            if _d.get("speech"):
                spoken_lines.append(_d["speech"])
    for _entry in (interp.get("other_players") or {}).values():
        for _e in ((_entry or {}).get("sequence") or []):
            if _e.get("type") == "speech" and _e.get("text"):
                spoken_lines.append(_e["text"])

    for p in perceivers:
        pid = str(p["id"])
        # Consciousness gate: a non-awake mind gets ONLY the deterministic
        # residue -- no LLM view (it was excluded from the call), no injection
        # backstops (they would re-create the leak at zero temperature). The
        # residue becomes its fragmentary memory of the beat (commit mints
        # memory from the view), which is the right recovered impression.
        if p.get("awareness") in NON_AWAKE_GATED:
            p_name_cf = p["name"].casefold()
            loud_event = any(
                str(d.get("volume", "")).lower() in ("loud", "shout")
                for d in npc_dlog)
            targeted = any(
                str(d.get("intended_target") or "").casefold() == p_name_cf
                for d in enriched_dlog)
            cause = (amap.get(p_name_cf) or {}).get("cause", "").lower()
            pain = any(w in cause for w in
                       ("injur", "wound", "blood", "hurt", "struck", "broke", "burn"))
            clean_views[pid] = _compose_residue_view(
                p["awareness"], targeted=targeted,
                loud_event=loud_event, pain=pain)
            continue
        spatial = p.get("spatial_to_sources") or {}
        visual = p.get("visual_channel_to_sources") or {}
        # Per-source recognition: whether THIS perceiver (player or NPC)
        # has actually been introduced to each speaker/actor. A perceiver
        # may recognize some sources and not others, so this cannot be a
        # single scalar the way action-onset "knows_identity" is.
        recognized_sources = set(known.get(p["name"]) or [])
        view = clean_views.get(pid)
        if not view:
            parts = [f"You are in {p.get('room_name')}."]
            if p.get("room_notes"):
                parts.append(p["room_notes"])
            view = " ".join(parts)
        # Track actors whose full appearance description has already been
        # surfaced in THIS view during this pass, so a second mention (a
        # dialogue line after an action, or vice versa) refers back to them
        # instead of re-pasting the whole appearance paragraph again.
        described_this_pass = set()
        _ubiq = _ubiquitous_names(sc)
        for d in npc_dlog:
            d_speaker = d.get("speaker", "?")
            if d_speaker == p["name"]:
                continue
            # Concealed dialogue must not reach a perceiver it is
            # concealed from -- mirroring the onset-pass gate.  A line
            # with visibility:'concealed' and no conceal_from list is
            # concealed from everyone except the speaker.
            if d.get("visibility") == "concealed":
                cf = [str(c).casefold() for c in (d.get("conceal_from") or [])]
                if not cf or p["name"].casefold() in cf:
                    continue
            rel = spatial.get(d_speaker)
            if rel is None:
                sp_room = d.get("speaker_room") or room_of(sc, d_speaker)
                if sp_room is None and str(d_speaker).strip().casefold() in _ubiq:
                    # A bodiless voice (ship AI, station PA) has no room, and
                    # spatial_rel(None, ...) yields barrier='unknown' ->
                    # hear_level 'none', so the Director could voice the ship's
                    # computer and NOBODY would hear it. Treat it as present.
                    rel = {"same_room": True, "barrier": "open",
                           "distance": "near",
                           "note": "bodiless voice, present throughout"}
                else:
                    rel = spatial_rel(sc, sp_room, p.get("room"))
                    # This fallback builds its own rel and so misses the
                    # concealment `_source_channels` applies to the map above.
                    if containment_conceals(sc, p["name"], d_speaker):
                        rel = {**rel, "concealed": True}
            can_see = _in_plain_view(rel, visual.get(d_speaker, False))
            if d_speaker in recognized_sources:
                display = d_speaker
            else:
                # A full appearance description is its own complete,
                # self-terminated paragraph. Gluing a dialogue/action clause
                # directly onto it as if it were the same sentence's subject
                # produces a run-on ("...guarded demeanor Pushes through the
                # door..."). Surface the appearance once as its own addition,
                # then refer to the actor with a short label for the actual
                # clause -- two clean sentences instead of one broken one.
                # Only do this when the perceiver can actually SEE the
                # speaker: a voice heard over a comm channel or through a
                # wall is audible without being visible, and _inject_dialogue
                # below already renders that case as "You hear X says..."
                # without a display name -- pasting a full visual appearance
                # onto an unseen voice would hallucinate sight the perceiver
                # doesn't have. Name-stripped first: appearance summaries
                # routinely lead with the canonical name this perceiver is
                # not entitled to.
                appearance_text = _strip_identity_tokens(
                    appearances.get(d_speaker),
                    [d_speaker, *(cast_aliases.get(d_speaker) or [])],
                ) or None
                if can_see and d_speaker not in described_this_pass:
                    if appearance_text:
                        view = _append_once(view, appearance_text, marker=appearance_text)
                    described_this_pass.add(d_speaker)
                # The LABEL is derived from the same appearance and was built
                # regardless of can_see, so gating only the paragraph above
                # left a compressed version of it going through: an unseen
                # voice still rendered as "the tall woman in a long grey coat
                # says ...". A perceiver who cannot see the speaker has no
                # visual referent for them at all -- what they have is a voice.
                display = (_unknown_actor_label(d_speaker, appearance_text)
                           if can_see else "a voice")
            # COMM CHANNEL: a line marked medium:'comm' reaches its addressed
            # party across any physical barrier (see _dialogue_hear_level). It
            # carries the VOICE, never SIGHT -- can_see is left untouched, so
            # _inject_dialogue renders "You hear X say...". A co-located
            # bystander is unaffected: not the addressed party, so they fall
            # through to ordinary spatial hearing.
            level = _dialogue_hear_level(d, rel, p["name"])
            view = _inject_dialogue(view, display, d.get("exact_quote"),
                                    level, d.get("volume", "normal"), can_see,
                                    conducted=bool(rel.get("inside_source")))
        for act in last_overt_by_actor.values():
            if act["actor"] == p["name"]:
                continue
            rel = spatial.get(act["actor"])
            if rel is None:
                continue
            # Rear-arc backstop (B3): an actor behind the perceiver (in
            # the perceiver's within-room blind spot) is not visible even
            # if _in_plain_view would pass via same_room. The perceiver
            # dict carries behind_sources for exactly this check.
            behind = set(p.get("behind_sources") or [])
            if act["actor"] in behind:
                continue
            can_see = _in_plain_view(rel, visual.get(act["actor"], False))
            if not can_see:
                continue
            if act["actor"] in recognized_sources:
                display = act["actor"]
            else:
                appearance_text = _strip_identity_tokens(
                    appearances.get(act["actor"]),
                    [act["actor"], *(cast_aliases.get(act["actor"]) or [])],
                ) or None
                if act["actor"] not in described_this_pass:
                    if appearance_text:
                        view = _append_once(view, appearance_text, marker=appearance_text)
                    described_this_pass.add(act["actor"])
                display = _unknown_actor_label(act["actor"], appearance_text)
            view = _inject_action(
                view, display, act["attempt"], can_see,
                self_forms=self_forms_by_name.get(p["name"]) or [p["name"]])
        # Deterministic identity floor, LAST (see perception_act): the
        # model's free prose is scrubbed per-source against THIS
        # perceiver's recognized set; quoted speech survives verbatim.
        view = _scrub_view_for(
            ctx, "perception_outcome", view, p["name"], known, ident_roster)
        # PLAYER-SPEECH AUTHORITY (perception layer): the player's OWN view must
        # not put words in the player's mouth. Drop any player-attributed quote
        # the player did not declare this beat (the perception LLM sometimes
        # invents one, often echoing a past player line). NPC lines the player
        # legitimately heard (npc_dlog) are protected.
        if pid == "player":
            view, _leaked = _scrub_undeclared_player_speech(
                view,
                declared_bodies=player_speech_lines(interp),
                protected_bodies=[d.get("exact_quote") for d in npc_dlog],
                cast_names=[r["name"] for r in ident_roster])
            if _leaked:
                ctx.warnings.append(
                    "perception_outcome: dropped undeclared player-attributed "
                    f"speech from the player's view: {_leaked}")
        # DIALOGUE-FIDELITY FLOOR (every view, every speaker): drop any quote
        # presented as speech whose body is not in spoken_lines. This closes
        # the gap the player-only scrub left open -- in an NPC's view the
        # player is referred to by name/descriptor, never "you", so an
        # invented player line there survived the scrub above and propagated
        # into that NPC's next-turn context and memory. Muffled fragments of
        # real lines and quoted environmental text (signage, labels) survive
        # by construction -- see _scrub_invented_dialogue.
        view, _invented = _scrub_invented_dialogue(
            view, spoken_lines, cast_names=[r["name"] for r in ident_roster])
        if _invented:
            ctx.warnings.append(
                "perception_outcome: dropped invented dialogue from view "
                f"'{pid}': {_invented}")
        clean_views[pid] = _dedupe_view_sentences(view) or None

    loop = ctx.interaction_loop or {}
    for round_data in loop.get("rounds") or []:
        for perceiver_id, additions in (round_data.get("delivered_views") or {}).items():
            key = str(perceiver_id)
            if key == "player":
                continue
            current = clean_views.get(key) or ""
            # Interaction-round additions can restate a beat the base view
            # already carries -- same within-view dedupe as the per-perceiver
            # pass above.
            clean_views[key] = _dedupe_view_sentences(
                _append_micro_view(current, additions))

    _disguise_leak_check(ctx, "perception_outcome", clean_views, perceivers,
                         p_name, p_disguise_terms, p_disguise_known)
    return {
        "views": clean_views,
        "observations": _observations_from_clean_views(clean_views),
    }
