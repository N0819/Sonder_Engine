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
    character_name_from_text,
    character_senses,
    persona_appearance,
    persona_name,
    persona_senses,
)
from db import q, wget
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
    corridor_sightlines,
    hiding_holders_of,
    _body_interior_holder,
    ambient_scope,
    contact_phrase,
    contact_sensation,
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
    normalize_barrier,
    proximity_rel,
    room_layout,
    room_of,
    same_subject,
    scent_level,
    spatial_facts,
    spatial_rel,
    visible_adjacent_rooms,
)


_RAPID_MOVEMENT_VERBS = frozenset({
    "run", "sprint", "flee", "dash", "bolt", "race", "charge",
})


def _declares_rapid_movement(value):
    """Whether one structured declaration says the actor moves rapidly."""
    sequence = value if isinstance(value, list) else (value or {}).get("sequence")
    for event in sequence or []:
        if not isinstance(event, dict) or event.get("type") != "action":
            continue
        verb = str(event.get("verb") or "").strip().casefold()
        words = str(
            event.get("attempt") or event.get("observable") or ""
        ).strip().casefold().split()
        if verb in _RAPID_MOVEMENT_VERBS or (
            words and words[0].rstrip("s") in _RAPID_MOVEMENT_VERBS
        ):
            return True
    return False


def _open_route_within(scene, start_room, end_room, max_hops=2):
    """True only across a short route of fully open air/doorway edges."""
    if not start_room or not end_room or start_room == end_room:
        return False
    neighbors = {}
    for room_id, room in (scene.get("rooms") or {}).items():
        if not isinstance(room, dict):
            continue
        for edge in room.get("adjacent") or []:
            if not isinstance(edge, dict):
                continue
            target = edge.get("to")
            if not target or normalize_barrier(edge.get("barrier")) not in {
                "open", "open_door",
            }:
                continue
            neighbors.setdefault(room_id, set()).add(target)
            neighbors.setdefault(target, set()).add(room_id)

    frontier = [(start_room, 0)]
    seen = {start_room}
    while frontier:
        room_id, hops = frontier.pop(0)
        if hops >= max_hops:
            continue
        for target in neighbors.get(room_id, ()):
            if target == end_room:
                return True
            if target not in seen:
                seen.add(target)
                frontier.append((target, hops + 1))
    return False


def _ci_value(mapping, name):
    wanted = str(name or "").strip().casefold()
    for key, value in (mapping or {}).items():
        if str(key).strip().casefold() == wanted:
            return value
    return None


def _mutually_near(stations, first, second):
    first_station = _ci_value(stations, first)
    second_station = _ci_value(stations, second)
    if not isinstance(first_station, dict) or not isinstance(second_station, dict):
        return False
    first_near = {
        str(value).strip().casefold()
        for value in (first_station.get("near") or [])
    }
    second_near = {
        str(value).strip().casefold()
        for value in (second_station.get("near") or [])
    }
    return (
        str(second).strip().casefold() in first_near
        and str(first).strip().casefold() in second_near
    )


def _previous_open_group_continuity(
        ctx, scene, actor_name, observer_name, observer_id,
        actor_room, observer_room):
    """Rescue hearing from one already-corrupted pre-turn checkpoint.

    Older resolver output could put two ordinary walkers in different path
    rooms while its same state diff explicitly kept them mutually ``near``.
    Reroll restores that contradiction before the repaired resolver gets a
    chance to run, so onset hearing otherwise loses the companion's next line.

    This is evidence recovery, not following or pursuit: both bodies must have
    begun the previous beat co-located, both must have moved, the previous
    result must explicitly keep them mutually near, neither declaration may be
    rapid, neither may stop following, the restored rooms must exactly match
    the contradictory result, and only a two-hop fully-open route qualifies.
    """
    if ctx.turn.idx <= 0 or not _open_route_within(
            scene, actor_room, observer_room, max_hops=2):
        return False

    cache_key = "_previous_open_group_evidence"
    if cache_key not in ctx:
        previous = q(
            "SELECT id FROM turns WHERE chat_id=? AND idx=?",
            (ctx.chat.id, ctx.turn.idx - 1), one=True,
        )
        evidence = {"outputs": {}, "checkpoint": {}}
        if previous:
            rows = q(
                "SELECT s.key,v.content FROM steps s JOIN variants v "
                "ON v.step_id=s.id AND v.active=1 "
                "WHERE s.turn_id=? AND (s.key IN "
                "('director_interpret','interaction_loop','director_resolve') "
                "OR s.key LIKE 'character:%')",
                (previous["id"],),
            )
            for row in rows:
                try:
                    evidence["outputs"][row["key"]] = json.loads(row["content"])
                except (TypeError, ValueError):
                    continue
            checkpoint = q(
                "SELECT blob FROM checkpoints WHERE chat_id=? AND turn_idx=?",
                (ctx.chat.id, ctx.turn.idx - 1), one=True,
            )
            if checkpoint:
                try:
                    evidence["checkpoint"] = json.loads(checkpoint["blob"])
                except (TypeError, ValueError):
                    pass
        ctx[cache_key] = evidence

    evidence = ctx.get(cache_key) or {}
    outputs = evidence.get("outputs") or {}
    previous_resolve = outputs.get("director_resolve") or {}
    state_diff = previous_resolve.get("state_diff") or {}
    positions = state_diff.get("positions") or {}
    stations = state_diff.get("stations") or {}
    actor_result_room = _ci_value(positions, actor_name)
    observer_result_room = _ci_value(positions, observer_name)
    if (
        actor_result_room != actor_room
        or observer_result_room != observer_room
        or not _mutually_near(stations, actor_name, observer_name)
    ):
        return False

    prior_scene = (
        ((evidence.get("checkpoint") or {}).get("world") or {}).get("scene")
        or {}
    )
    prior_positions = prior_scene.get("positions") or {}
    actor_start = _ci_value(prior_positions, actor_name)
    observer_start = _ci_value(prior_positions, observer_name)
    if (
        not actor_start
        or actor_start != observer_start
        or actor_result_room == actor_start
        or observer_result_room == observer_start
    ):
        return False

    previous_interpret = outputs.get("director_interpret") or {}
    if not isinstance(previous_interpret.get("movement"), dict):
        return False
    interaction = outputs.get("interaction_loop") or {}
    character_results = interaction.get("character_results") or {}
    observer_result = (
        character_results.get(str(observer_id))
        or character_results.get(observer_id)
        or outputs.get(f"character:{observer_id}")
        or {}
    )
    if not any(
        isinstance(event, dict) and event.get("type") == "action"
        for event in (observer_result.get("sequence") or [])
    ):
        return False
    if (
        _declares_rapid_movement(previous_interpret)
        or _declares_rapid_movement(observer_result)
    ):
        return False

    pair = {
        str(actor_name).strip().casefold(),
        str(observer_name).strip().casefold(),
    }
    for op in state_diff.get("following_ops") or []:
        if not isinstance(op, dict) or op.get("op") != "stop":
            continue
        if str(op.get("follower") or "").strip().casefold() in pair:
            return False
    follow_op = observer_result.get("follow_op") or {}
    if isinstance(follow_op, dict) and follow_op.get("op") == "stop":
        return False
    return True


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
    # Interoception was a DISTRESS vocabulary -- pain, nausea, wounds, a fixed
    # list of interior organs -- so it fired on 2.4% of 7,508 corpus
    # observations and never once in a story built on sustained physical
    # contact. Interior sensation is interoception whatever its valence, and a
    # body reporting fullness or an interior stretch is reporting it from the
    # one channel that carries it.
    ("interoception", (
        r"\bpain\b", r"\bache[sd]?\b", r"\baching\b", r"\bnausea\b",
        r"\bdizzy\b", r"\bexhausted\b", r"\bstarving\b", r"\bwounded\b",
        r"\bwounds\b", r"\byour wound\b",
        r"\bbreathless\b", r"\bcannot breathe\b", r"\bout of breath\b",
        r"\bheartbeat\b", r"\byour (?:pulse|heart|lungs|chest|stomach|"
        r"belly|throat|muscles|nerves)\b",
        r"\bwithin it\b", r"\bfullness\b", r"\binside you\b",
        r"\bstretch(?:ed|ing)?\b", r"\bclench(?:es|ed|ing)?\b",
        r"\bcramp(?:s|ed|ing)?\b", r"\bspasm(?:s|ed|ing)?\b",
    )),
    # Touch was similarly narrow: grips, presses and skin. It had no word for
    # pressure that is not a grip, for weight, friction, texture, tremor or
    # heat -- so nearly half of every observation the engine made matched no
    # channel cue at all and fell through to `mixed`.
    ("touch", (
        r"\btouch(?:es|ed|ing)?\b", r"\bpressure\b", r"\bgrip(?:s|ped|ping)?\b",
        r"\bagainst your\b", r"\bgrips? your\b", r"\bholds? your\b",
        r"\bpress(?:es|ed|ing)? (?:into|against) you\b", r"\bwarmth\b",
        r"\bskin\b",
        r"\bfriction\b", r"\btexture\b", r"\btremors?\b", r"\btrembl(?:es|ing)\b",
        r"\bweight of\b", r"\bheat of\b", r"\bcontact\b", r"\bagainst it\b",
        r"\bclosed around it\b", r"\bregisters?\b", r"\bcontinuous while\b",
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
    r"|\byour name\b"
    # A continuous-contact clause has the perceiver's own body as its subject
    # ("your shoulder registers ..."), which no agent-first pattern above
    # reaches. Keyed on the deterministic verb rather than on a bare leading
    # "your", because "your companion steps back" is not about the perceiver.
    r"|\byour\s+(?:\w+\s+){0,2}registers?\b",
    re.I,
)

# Closing quotes and brackets ride with the sentence they end.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])[\"'”’)\]]*\s+")

# Does this sentence ASSERT SIGHT -- somebody looking at something, in the
# verbs a view actually uses for it. Read by `_strip_self_narration`'s floor,
# which refuses to leave a perceiver with no sight at all.
#
# Deliberately its own pattern rather than `_atom_channel`'s "sight" cues:
# those classify a whole ATOM for the observation projection, they lean on
# second-person phrasing ("you see") that is by definition absent from the
# third-person views this floor exists for, and widening them would move
# every consumer of that classification.
_SIGHT_ASSERTION = re.compile(
    r"\b(?:sees?|saw|seen|seeing|watch(?:es|ed|ing)?|look(?:s|ed|ing)?\s+at"
    r"|notic(?:e|es|ed|ing)|observ(?:e|es|ed|ing)|glimps(?:e|es|ed|ing)"
    r"|spots?|spotted|makes?\s+out|made\s+out|catch(?:es)?\s+sight\s+of"
    r"|caught\s+sight\s+of|in\s+view|visible|in\s+sight)\b",
    re.I,
)

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


def _contact_already_felt(view, contact, observer_name, scene):
    """Does this view already deliver the sensation of this standing contact?

    Matched on the two BODY PARTS the contact names, because that is the part
    of the record a paraphrase preserves -- a model rendering a tail against a
    thigh will say tail and thigh whatever else it changes -- while the manner
    is exactly what it rewrites.

    Both parts must appear IN ONE SENTENCE, on word boundaries. Scanning the
    whole view for each part separately matched a hip in one clause against a
    hand in another and called a contact between them delivered; unanchored
    substrings matched `hip` inside `ship`. A contact is rendered where both
    of its ends are named together, or it is not rendered.

    Biased toward silence in one direction only: a contact naming no parts at
    all cannot be matched, and is treated as already delivered rather than
    appending a clause about `your body` on every beat of an ordinary embrace.
    """
    if not isinstance(contact, dict):
        return True
    observer = str(observer_name or "").strip()
    if same_subject(scene, str(contact.get("actor") or ""), observer):
        mine = str(contact.get("actor_part") or "")
        theirs = str(contact.get("target_part") or "")
    else:
        mine = str(contact.get("target_part") or "")
        theirs = str(contact.get("actor_part") or "")
    parts = [p.replace("_", " ").strip().casefold()
             for p in (mine, theirs) if str(p or "").strip()]
    if not parts:
        return True
    patterns = [re.compile(r"\b%s\b" % re.escape(part)) for part in parts]
    for sentence in re.split(r"(?<=[.!?])\s+", str(view or "")):
        folded = sentence.casefold()
        if all(pattern.search(folded) for pattern in patterns):
            return True
    return False


def _deliver_standing_sensations(view, observer_name, scene, contacts):
    """Append the sensation of any standing contact the view left unfelt.

    THE DEFECT THIS IS THE FLOOR FOR. The perception contract specifies the
    tactile channel only as a substitute for sight: every mandatory clause is
    conditioned on sight being absent -- in the dark, behind a wall, sealed
    inside something. Two bodies in continuous contact in a lit room have a
    wide-open tactile channel and no clause requiring a word of it, so a view
    written under a token budget renders what is seen and drops what is felt.
    Measured over 7,508 corpus observations before this: 46.8% classified as
    `mixed` because no sensory cue matched them at all, and `interoception`
    accounted for 2.4%.

    A standing contact is neither an event nor inert state. It is a CONTINUOUS
    PERCEPT -- true every beat and felt every beat, until it ends -- and the
    engine had no representation for that, only `event` (rendered once) and
    `state` (mentioned, then inert). This is the third category, delivered
    deterministically so it does not depend on a model cooperating.

    It subtracts nothing and adds only to a party to the contact: a bystander
    watching two other people touch gets no clause, because `contact_sensation`
    returns "" for anyone who is not a party.
    """
    additions = []
    for contact in contacts or []:
        if _contact_already_felt(view, contact, observer_name, scene):
            continue
        clause = contact_sensation(contact, you=observer_name, scene=scene)
        if clause:
            additions.append(clause[0].upper() + clause[1:] + ".")
    if not additions:
        return view
    return _append_once(str(view or ""), " ".join(additions))


def _standing_contacts_for(scene, observer_name):
    """The contacts this perceiver is a party to, first-hand by definition."""
    out = []
    for contact in (scene or {}).get("contacts") or []:
        if not isinstance(contact, dict):
            continue
        if (same_subject(scene, str(contact.get("actor") or ""), observer_name)
                or same_subject(scene, str(contact.get("target") or ""),
                                observer_name)):
            out.append(contact)
    return out


_BODY_DETAIL_GENERIC = frozenset({
    "above", "bare", "below", "between", "body", "exposed", "full", "inner",
    "outer", "skin", "soft", "their", "there", "these", "they", "thigh",
    "thighs", "this", "those", "very", "warm", "with", "within", "your",
})

_SELF_EXPOSED_REGION_CUES = {
    "torso": (
        re.compile(
            r"\byour\b[^.!?\n]{0,28}\b(?:bare|exposed|naked)\b"
            r"[^.!?\n]{0,18}\b(?:chest|breasts?|stomach|abdomen|belly|"
            r"midriff|ribs?|torso)\b", re.I),
        re.compile(
            r"\b(?:chest|breasts?|stomach|abdomen|belly|midriff|ribs?|torso)\b"
            r"[^.!?\n]{0,18}\b(?:bare|exposed|naked)\b", re.I),
    ),
    "groin": (
        re.compile(
            r"\byou\b[^.!?\n]{0,55}\b(?:part|spread|open)\w*\b"
            r"[^.!?\n]{0,35}\b(?:legs|thighs)\b", re.I),
        re.compile(r"\bbetween your\b[^.!?\n]{0,24}\b(?:legs|thighs)\b", re.I),
        re.compile(
            r"\byour\b[^.!?\n]{0,28}\b(?:bare|exposed|naked)\b"
            r"[^.!?\n]{0,18}\b(?:groin|crotch|genitals?|vulva|penis|cock)\b",
            re.I),
    ),
}

_OTHER_EXPOSED_REGION_CUES = {
    "torso": (
        re.compile(
            r"\b(?:her|his|their)\b[^.!?\n]{0,28}\b(?:bare|exposed|naked)\b"
            r"[^.!?\n]{0,18}\b(?:chest|breasts?|stomach|abdomen|belly|"
            r"midriff|ribs?|torso)\b", re.I),
        re.compile(
            r"\b(?:bare|exposed|naked)\b[^.!?\n]{0,18}"
            r"\b(?:chest|breasts?|stomach|abdomen|belly|midriff|ribs?|torso)\b",
            re.I),
    ),
    "groin": (
        re.compile(
            r"\b(?:she|he|they)\b[^.!?\n]{0,55}\b(?:part|spread|open)\w*\b"
            r"[^.!?\n]{0,35}\b(?:her|his|their)?\s*(?:legs|thighs)\b", re.I),
        re.compile(
            r"\b(?:part|spread|open)\w*\b[^.!?\n]{0,35}"
            r"\b(?:her|his|their)\s+(?:legs|thighs)\b", re.I),
        re.compile(
            r"\bbetween (?:her|his|their)\b[^.!?\n]{0,24}\b(?:legs|thighs)\b",
            re.I),
        re.compile(
            r"\b(?:her|his|their)\b[^.!?\n]{0,28}\b(?:bare|exposed|naked)\b"
            r"[^.!?\n]{0,18}\b(?:groin|crotch|genitals?|vulva|penis|cock)\b",
            re.I),
    ),
}


def _bare_body_details(region, surface):
    """Authored bare-surface details carried by one observer-safe region.

    The body-region projection is deliberately prose-shaped for the perception
    model.  This parser reads only the two shapes that projection itself emits:
    a fully bare region (``bare — detail``) or a partially bare zone
    (``midriff: bare — detail``).  Covered-zone and garment descriptions never
    match, so this floor cannot turn a covered chest into anatomy.
    """
    text = str(surface or "").strip()
    if not text:
        return []
    out = []
    for match in re.finditer(
            r"(?:^|;\s*)([a-z_ ]+):\s*bare\s+—\s+(.+?)"
            r"(?=;\s*[a-z_ ]+:|$)", text, re.I | re.S):
        detail = match.group(2).strip()
        if detail:
            out.append((match.group(1).strip().replace("_", " "), detail))
    if out:
        return out
    match = re.match(
        r"^bare\s+—\s+(.+?)(?=;\s*[^;]+\[worn at, covers nothing\]|$)",
        text, re.I | re.S)
    if match and match.group(1).strip():
        return [(str(region or "body region").replace("_", " "),
                 match.group(1).strip())]
    return []


def _authored_detail_already_present(view, detail):
    """Whether the view retained enough distinctive authored wording."""
    view_tokens = set(re.findall(r"[a-z0-9]+", str(view or "").casefold()))
    detail_tokens = []
    for token in re.findall(r"[a-z0-9]+", str(detail or "").casefold()):
        if len(token) >= 4 and token not in _BODY_DETAIL_GENERIC:
            detail_tokens.append(token)
    distinctive = list(dict.fromkeys(detail_tokens))
    if not distinctive:
        return True
    # Two retained concrete traits are enough: prose may legitimately rephrase
    # or compress the card description. One generic region word ("stomach")
    # is not enough, which is exactly the live omission this floor catches.
    required = 1 if len(distinctive) == 1 else 2
    return len(view_tokens.intersection(distinctive)) >= required


def _self_body_detail(detail):
    """An authored third-person body description in a second-person view."""
    text = str(detail or "")
    replacements = (
        (r"\bherself\b", "yourself"), (r"\bHerself\b", "Yourself"),
        (r"\bhers\b", "yours"), (r"\bHers\b", "Yours"),
        (r"\bher\b", "your"), (r"\bHer\b", "Your"),
        (r"\bshe\b", "you"), (r"\bShe\b", "You"),
    )
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)
    return text


def _deliver_foreground_body_details(view, body_regions):
    """Restore authored anatomy the perception model generalized away.

    This is a fidelity floor, not an anatomy dump.  The model first decides
    what the observer notices.  Only when its own view foregrounds an exposed
    surface (for example ``your bare stomach`` or ``you part your legs``) does
    this append the observer-safe authored detail for that region.  The input
    has already crossed garment, darkness, containment, vantage, and identity
    gates in ``observer_body_regions``.
    """
    original = str(view or "")
    additions = []
    rows = [row for row in (body_regions or []) if isinstance(row, dict)]
    paragraphs = [p for p in re.split(r"\n\s*\n", original) if p.strip()]
    for row in rows:
        label = str(row.get("body") or "someone").strip()
        self_view = label.casefold() == "you"
        if self_view:
            relevant_text = original
            cue_map = _SELF_EXPOSED_REGION_CUES
        else:
            relevant_text = "\n".join(
                p for p in paragraphs if label.casefold() in p.casefold())
            cue_map = _OTHER_EXPOSED_REGION_CUES
        if not relevant_text:
            continue
        for region, surface in (row.get("regions") or {}).items():
            patterns = cue_map.get(str(region).casefold()) or ()
            if not patterns or not any(p.search(relevant_text) for p in patterns):
                continue
            for place, detail in _bare_body_details(region, surface):
                if _authored_detail_already_present(original, detail):
                    continue
                rendered = _self_body_detail(detail) if self_view else detail
                subject = (f"Your exposed {place} is visible"
                           if self_view else f"{label}'s exposed {place} is visible")
                addition = f"{subject}: {rendered}".strip()
                if addition[-1:] not in ".!?":
                    addition += "."
                additions.append(addition)
    if not additions:
        return original, []
    return _append_once(original, " ".join(additions)), additions


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
    _action_already_rendered,
    _append_micro_view,
    _append_once,
    _contains_quote,
    _contextual_rooms,
    _perceptible_entities,
    _dedupe_view_sentences,
    _player_name_forms,
    _quote_body,
    _sentence_subjects,
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
    observer_body_regions,
    cast_room,
    character_room,
    character_scene_keys,
)


def _observer_scene_payload(scene, perceiver, body_labels=None):
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
    # Every contact here is STANDING state -- what is true at the top of this
    # beat, not what just happened. The beat's own acts arrive separately, in
    # `declared_act.sequence`. Each carries `standing`, a stative clause the
    # model can lift directly, because the bare {manner: "kiss"} record read as
    # an event and was narrated as one: a kiss recorded several beats earlier
    # kept being delivered as a live advance, and the character answered it.
    contacts = []
    for contact in (scene.get("contacts") or []):
        if not isinstance(contact, dict):
            continue
        if not (
            name in (str(contact.get("actor") or ""),
                     str(contact.get("target") or ""))
            or (
                str(contact.get("actor") or "") in visible_names
                and str(contact.get("target") or "") in visible_names
            )
        ):
            continue
        entry = copy.deepcopy(contact)
        entry["standing"] = contact_phrase(contact, you=name)
        # `standing` is the contact as a third party would state it. `sensation`
        # is what it delivers to THIS perceiver's body, which is a different
        # thing and was previously nowhere in the payload -- so a mind in
        # sustained contact received a diagram of the contact and nothing it
        # felt. Empty for a contact this perceiver is only watching.
        entry["sensation"] = contact_sensation(contact, you=name, scene=scene)
        contacts.append(entry)
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
    payload = {
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
        # What can be read looking STRAIGHT down each passage: that it ends,
        # opens out, or bends. Sight follows the line until the passage turns,
        # a door blocks it, or the dark takes it -- so it grants no knowledge
        # of anything round a corner.
        "sightlines": corridor_sightlines(scene, room_id) if room_id else [],
    }
    body_regions = observer_body_regions(
        scene, name, body_labels or {name: "you"})
    if body_regions:
        payload["body_regions"] = body_regions
    return payload


def _observer_body_labels(perceiver, known, appearances, *, include=()):
    """Canonical body -> observer-safe label for the body-region payload."""
    observer = str(perceiver.get("name") or "")
    recognized = set((known or {}).get(observer) or []) | {observer}
    candidates = dict(appearances or {})
    for name in include or ():
        candidates.setdefault(str(name), "")
    labels = {}
    for body, appearance in candidates.items():
        body = str(body or "").strip()
        if not body:
            continue
        if observer.strip().casefold() == body.casefold():
            labels[body] = "you"
        elif _recognizes(body, recognized):
            labels[body] = body
        else:
            labels[body] = _unknown_actor_label(body, appearance)
    return labels


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


def _inject_onset_speech(view, speech_elems, perceiver, rel, display, can_see):
    """Deliver every player line this observer is allowed to hear.

    This is deliberately safe to call twice. The first pass lets ordinary
    model prose keep its natural ordering; `_inject_dialogue` adds only a line
    that is not already present. The second pass runs after every destructive
    view scrub and is the actual fidelity floor: a scrub must not erase a line
    merely because the model first placed it inside prose the scrub rejected.

    Live (chat 38, turn 125): the Doctor's raw view evidently contained
    ``It's really beautiful...`` inside a sentence narrated from outside the
    Doctor. `_inject_dialogue` saw the quote and avoided a duplicate, then
    `_strip_self_narration` removed that whole sentence. With no final delivery
    check, the Doctor decided the beat having heard only the player's second
    line. A restored earlier line is anchored before the next surviving line,
    with its declared tone, rather than appended after it. Keeping the
    audibility/concealment calculation in one helper prevents the two passes
    from drifting apart.
    """
    events = list(speech_elems or [])

    def _body_match(text, body):
        words = re.split(r"(\s+)", str(body or ""))
        pattern = "".join(r"\s+" if part.isspace() else re.escape(part)
                          for part in words if part)
        return re.search(pattern, str(text or ""), re.I) if pattern else None

    def _clause_start(text, pos):
        """Start of the prose clause containing a later spoken line."""
        inside_quote = False
        start = 0
        for index, char in enumerate(str(text or "")[:pos]):
            if char in '"“”':
                inside_quote = not inside_quote
            elif char in ".!?…" and not inside_quote:
                start = index + 1
        while start < len(text) and text[start].isspace():
            start += 1
        return start

    for index, event in enumerate(events):
        if event.get("visibility") == "concealed" and (
            not event.get("conceal_from")
            or _concealed_from_perceiver(event, perceiver)
        ):
            continue
        level = hear_level(
            rel, event.get("volume", "normal"),
            proximity=perceiver.get("proximity_to_actor"),
        )
        # Compatibility floor for a rerolled checkpoint that predates the
        # near-group position repair.  It grants hearing only; the relation's
        # real spatial fields still govern sight and every other channel.
        if (
            level == "none"
            and rel.get("open_group_continuity")
            and str(event.get("volume") or "normal").casefold()
            in {"normal", "loud", "shout"}
        ):
            level = "full"
        body = _quote_body(event.get("text"))
        if level == "none" or not body or _contains_quote(view, body):
            continue

        # Append is normally sufficient, but if a later declared line already
        # survived the model/scrub path it would put this restored EARLIER line
        # after it. Anchor the missing line immediately before the next
        # surviving line's clause, preserving the player's speech order and
        # therefore its emotional progression.
        next_match = None
        for later in events[index + 1:]:
            next_body = _quote_body(later.get("text"))
            match = _body_match(view, next_body)
            if match:
                next_match = match
                break
        if next_match and level != "fragment":
            delivered = _inject_dialogue(
                "", display, event.get("text"), level,
                event.get("volume", "normal"), can_see,
                conducted=bool(rel.get("inside_source")),
                tone=event.get("tone", ""),
            )
            insert_at = _clause_start(view, next_match.start())
            view = (
                view[:insert_at].rstrip() + " " + delivered + " "
                + view[insert_at:].lstrip()
            ).strip()
        else:
            view = _inject_dialogue(
                view, display, event.get("text"), level,
                event.get("volume", "normal"), can_see,
                conducted=bool(rel.get("inside_source")),
                tone=event.get("tone", ""),
            )
    return view


_DELIVERY_META_RE = re.compile(
    r"^(?:the words? (?:reach|reaches) you(?: clearly)?|"
    r"you hear (?:both|all|the) (?:lines?|words?) (?:in full|clearly))"
    r"[.!?]*$",
    re.I,
)


def _strip_onset_rendering(view, sequence, display):
    """Remove the model's paraphrase of declared onset events.

    The perception model remains useful for selecting ambient sensory detail,
    but it cannot be the authority on the ORDER of an already structured
    player sequence.  A live two-line beat was returned as turn -> first line
    -> second line, even though interpret correctly held first line -> turn ->
    second line.  It also added delivery metacommentary ("The words reach you
    clearly", "You hear both lines in full") that describes the filter rather
    than the fiction.

    Strip only material that can be tied back to a declared speech/action:
    exact quote bodies, the two high-precision delivery-meta shapes above, and
    clauses with the same conservative content overlap `_inject_action` uses
    for duplicate detection.  Mixed environment/action sentences are handled
    clause-by-clause so a trailing turn does not erase the room description.
    The caller then projects the authorized sequence deterministically.
    """
    text = str(view or "").strip()
    if not text:
        return text
    speech_bodies = [
        _quote_body(event.get("text"))
        for event in (sequence or [])
        if isinstance(event, dict) and event.get("type") == "speech"
        and event.get("text")
    ]
    action_surfaces = [
        observable_action_text(event)
        for event in (sequence or [])
        if isinstance(event, dict) and event.get("type") == "action"
        and observable_action_text(event)
    ]

    kept = []
    for sentence in _SENTENCE_SPLIT.split(text):
        sentence = sentence.strip()
        if not sentence:
            continue
        if any(body and _contains_quote(sentence, body)
               for body in speech_bodies):
            continue
        if _DELIVERY_META_RE.fullmatch(sentence.strip()):
            continue

        if any(_action_already_rendered(sentence, display, surface)
               for surface in action_surfaces):
            # A model often tacks the visible act onto a useful environment
            # sentence after a comma: "The console glows..., her ears perk as
            # she turns." Remove just that clause when possible.
            pieces = re.split(r"([,;\u2014\u2013]\s+)", sentence)
            clauses = pieces[::2]
            retained = []
            for index, clause in enumerate(clauses):
                if any(_action_already_rendered(
                        clause, display, surface)
                       for surface in action_surfaces):
                    continue
                if clause.strip():
                    retained.append(clause.strip())
            if retained and len(retained) < len(clauses):
                sentence = ", ".join(retained).strip(" ,;\u2014\u2013")
                if sentence and sentence[-1] not in ".!?\u2026":
                    sentence += "."
            else:
                continue
        if sentence:
            kept.append(sentence)
    return " ".join(kept).strip()


def _self_cannot_see_own_surface(scene, perceiver, actor_name) -> bool:
    """Is this perceiver the actor, AND sealed inside something?

    `observable` is the intent-free surface of an act as seen FROM OUTSIDE,
    and the actor normally receives it in their own view (rewritten to second
    person by `_self_second_person`) because people can see themselves doing
    things. Sealed inside another body that stops being true: the surface then
    describes the OUTSIDE of the enclosure -- how the wall of it moves with
    them -- and there is no channel from inside to that.

    Live, chat 60 t18. The declared observable was "A tiny lump writhes and
    squirms beneath the fabric ... the shirt shifting and bulging", and the
    actor's own view came back "The lump you make writhes and bulges under the
    fabric" -- in darkness, under cloth, with the narrator's own prose two
    clauses earlier saying she could see nothing. The engine handed her an
    outside observer's shot of herself.

    Deliberately keyed on being ENCLOSED rather than on darkness or a failed
    sight check. Being unable to see in the dark does not stop you knowing what
    your own body is doing -- proprioception is not sight, and suppressing an
    actor's own conduct every time the lights went out would be a worse error
    than the one this fixes. What an enclosure removes is specifically the
    outside view of yourself.
    """
    if not scene or not perceiver:
        return False
    name = str(perceiver.get("name") or "").strip()
    if not name or not same_subject(scene, name, actor_name):
        return False
    return bool(hiding_holders_of(scene, name))


def _inject_onset_sequence(view, sequence, perceiver, rel, display, can_see,
                           scene, actor_name, self_forms):
    """Project authorized speech/actions in their declared order."""
    delivered = set()
    continuity_available = bool(rel.get("open_group_continuity"))
    sentence_display = str(display or "")
    if sentence_display:
        sentence_display = sentence_display[:1].upper() + sentence_display[1:]
    for event in sequence or []:
        if not isinstance(event, dict):
            continue
        if event.get("visibility") == "concealed" and (
            not event.get("conceal_from")
            or _concealed_from_perceiver(event, perceiver)
        ):
            continue
        if event.get("type") == "speech":
            speech_rel = rel if continuity_available else {
                **rel, "open_group_continuity": False,
            }
            view = _inject_onset_speech(
                view, [event], perceiver, speech_rel, sentence_display, can_see)
            continue
        if event.get("type") != "action":
            continue
        if _declares_rapid_movement([event]):
            # Speech before the run remains audible; speech after the run gets
            # no continuity floor.  Following is not all-powerful pursuit.
            continuity_available = False
        surface = observable_action_text(event)
        if not surface or entity_arc(
                scene, perceiver.get("name"), actor_name) == "rear":
            continue
        if _self_cannot_see_own_surface(scene, perceiver, actor_name):
            continue
        view = _inject_action(
            view, sentence_display, surface, can_see,
            event_id=event.get("event_id"), delivered=delivered,
            self_forms=self_forms,
        )
    return view


def _ubiquitous_names(sc):
    """Bodiless voices in this scene (ship AI, station PA), casefolded.

    Imported lazily: perception must not take a hard dependency on scene.py's
    import graph for what is a small, optional lookup."""
    try:
        from scene import ubiquitous_speaker_names
        return ubiquitous_speaker_names(sc)
    except Exception:
        return frozenset()


def _saw_across_beat(sc, prev_sc, perceiver_name, source_name, rel):
    """Visual channel to one source, over the whole beat (see _source_channels).

    Per-body and light-aware via `visual_level_between` when the perceiver has
    a position, room-level otherwise. Answered against the outcome scene first;
    only if that says no does the pre-diff scene get asked, so this can add a
    channel the beat closed and can never remove one it opened.
    """
    def _at(scene):
        if not scene:
            return False
        if room_of(scene, perceiver_name) is not None:
            return visual_level_between(scene, perceiver_name, source_name) != "none"
        return has_visual(rel)
    return _at(sc) or _at(prev_sc)


def _source_channels(sc, perceiver_name, perceiver_room, sources, prev_sc=None):
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

    THE BEAT, NOT ITS LAST FRAME. `prev_sc` is the scene as it stood BEFORE
    this turn's diff, and when it is given a source counts as perceptible if it
    was reachable at either end of the beat. Without it an act that closes a
    channel erases the perception of the act itself, because perception only
    ever ran against the outcome scene.

    Live (chat 58, t27): the player ran through the TARDIS's open doors, the
    doors slammed, and the ship went `in_transit` -- which correctly severs the
    interior's exterior edges. All three happened in one beat, so by the time
    the Doctor's view was built the room she had run into was not adjacent to
    anywhere, and his view records the doors closing on an empty doorway. He
    never saw her go in. The same shape covers every act that shuts a channel
    it is seen through: a slammed door, a drawn curtain, stepping into a
    container, a vehicle pulling away.

    Union, not replacement: whichever end of the beat grants MORE is used. A
    body that was never reachable and still is not stays unreachable, so this
    opens nothing that was closed for the whole beat -- it only refuses to
    pretend the beat's own transition never happened.
    """
    rels = {}
    for s in sources:
        rel = spatial_rel(sc, s["room"], perceiver_room)
        if containment_conceals(sc, perceiver_name, s["name"]):
            rel = {**rel, "concealed": True}
        if prev_sc:
            prev_rel = spatial_rel(
                prev_sc,
                room_of(prev_sc, s["name"]) or s["room"],
                room_of(prev_sc, perceiver_name) or perceiver_room)
            if containment_conceals(prev_sc, perceiver_name, s["name"]):
                prev_rel = {**prev_rel, "concealed": True}
            # Only ever upgrades. `has_visual` is the room-level question and
            # is the one that goes false when an edge is severed mid-beat --
            # which is exactly the transition this exists to preserve.
            if has_visual(prev_rel) and not has_visual(rel):
                rel = {**prev_rel, "was_reachable_at_beat_start": True}
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
            n: (_saw_across_beat(sc, prev_sc, perceiver_name, n, rels[n]))
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


# Sentence boundaries, tolerating a closing quote between the terminal
# punctuation and the space ('...to me!?" The voice is...'). A lone
# `(?<=[.!?])\s+` cannot split there, which silently made a whole passage one
# "sentence" and let the self-narration guard pass everything. Two alternated
# lookbehinds rather than an optional group, because Python requires them
# fixed-width -- and this way the quote stays attached to the sentence it
# closes instead of being eaten by the split.
_SENTENCE_SPLIT = re.compile(r'(?<=[.!?])\s+|(?<=[.!?]["\u201d\u2019\'])\s+')


def _strip_self_narration(view, perceiver_name, other_names=(), refusals=None):
    """Drop sentences that narrate the PERCEIVER from outside their own view.

    A view is what one mind receives. It may say "you" and it may describe
    anyone else; what it must never do is stand outside the perceiver and
    report them as a third party -- least of all their own face, which they
    cannot see.

    Live, alpha 6.3: Elyndra's own view read "Elyndra's gaze stays fixed on
    the shifting lump, her teasing smile faltering as she watches the genuine
    terror in that tiny trembling form", in a view that elsewhere said "You
    see Hinami." Both halves are wrong from her side -- she is not watching
    her own smile falter, and she cannot know another mind's terror is
    genuine. Tracing it: `director_resolve` had written "Elyndra's teasing
    smile falters completely at the shrill, panicked cry", and perception
    COPIED the omniscient sentence into her view rather than rendering the
    beat from her frame. Per-observer calls did not prevent it; each observer
    got its own call and this one simply echoed its input.

    Dropping the sentence rather than rewriting it, and dropping only whole
    sentences whose SUBJECT is the perceiver: the rest of the view is
    untouched and still coherent, and no prose is invented to replace what
    goes.

    Subject resolution is pronoun-continuation-aware (`_sentence_subjects`),
    which is how the live case was found. Chat 56 ("Run!") t6, in the PLAYER's
    own view: "She feels her arms still wrapped tightly, her breathing slowing,
    the terror in her eyes beginning to recede." Third person, about the
    perceiver, in a view addressed to them -- the Director's omniscient
    sentence copied through whole, exactly the shape this guard exists to
    catch, and invisible to it because the subject was written as "She". An
    unanchored pronoun still binds to nobody rather than to a guess, so a view
    that never names the perceiver is left alone.

    Both floors below REFUSE to drop rather than dropping less, and a refusal
    is a view knowingly delivered with self-narration still in it. Pass a list
    as `refusals` to hear about it; the default of None keeps the two-tuple
    contract every existing caller and test relies on.
    """
    if not view or not perceiver_name:
        return view, []
    forms = _player_name_forms(perceiver_name)
    if not forms:
        return view, []
    names = [perceiver_name] + [
        n for n in (other_names or []) if n and n != perceiver_name]
    kept, dropped = [], []
    # A closing quote may sit between the terminal punctuation and the space
    # ('...to me!?" The voice is...'), and a naive lookbehind cannot split
    # there -- which silently made a whole passage one "sentence" and let this
    # guard pass everything.
    for stripped, subject in _sentence_subjects(
            str(view), names, split=_SENTENCE_SPLIT):
        if not stripped:
            continue
        if subject == perceiver_name:
            dropped.append(stripped)
        else:
            kept.append(stripped)
    if not dropped:
        return view, []
    # Never empty a view entirely: a perceiver who received something must be
    # told something. If every sentence named them, the view is beyond repair
    # by deletion and is left alone for the refusal to carry.
    if not kept:
        if refusals is not None:
            refusals.append(
                "every sentence named the perceiver, so the view is beyond "
                "repair by deletion and was delivered as written")
        return view, []
    # Never take a perceiver's eyes off the beat either. A view written wholly
    # from outside its own perceiver puts them in the subject slot of exactly
    # the sentences carrying what they SAW -- "The Doctor watches her run
    # across the gravel and throw her arms around the kitsune" -- so a
    # subject-anchored drop removes the framing error and the observation
    # together, and the sentences left standing are the ones about the weather.
    #
    # Live (chat 38, t140): the Doctor stood at the genkan, six feet from an
    # embrace the resolved event says he was watching with bright interest, in
    # a lit-enough room with `shapes` sight to both bodies. Perception wrote
    # his view in the third person, this guard dropped both sight sentences,
    # and his view, his structured observations and his committed memory of
    # that beat all came out sound-only -- a permanent hole in what that mind
    # knows, from a framing slip.
    #
    # The two failures are not equal and the module already says so:
    # `_strip_unreachable_bodies` refuses over-denial on the ground that
    # "silence about someone audibly present is its own lie". Being told about
    # yourself in the third person for one beat is bounded and visible; losing
    # what you saw is neither. So when the drop would leave a view with no
    # assertion of sight in it at all, the view stands and the warning carries
    # it.
    #
    # Narrow on purpose: it keys on the verbs a view actually uses to assert
    # sight, so it is a floor under this specific loss and NOT a general
    # promise that nothing informative is ever dropped (a view phrasing sight
    # as "visual sensors pick up" is still dropped whole -- see
    # test_a_body_named_with_an_article_is_caught_under_another_article).
    if (any(_SIGHT_ASSERTION.search(s) for s in dropped)
            and not any(_SIGHT_ASSERTION.search(s) for s in kept)):
        if refusals is not None:
            refusals.append(
                "dropping self-narration would have left this view with no "
                "sight in it at all, so it was delivered as written: "
                + "; ".join(s[:120] for s in dropped))
        return view, []
    return " ".join(kept), dropped


def _strip_unreachable_bodies(view, perceiver_name, scene, roster):
    """Drop sentences about a body the perceiver has NO sensory channel to.

    A view is the whole information budget one mind receives, and the engine
    already knows who is reachable -- `spatial_rel` answers it for every pair
    on the scene. Nothing consumed that answer when the view was prose, so a
    body could be described in full to an observer with no way to perceive it.

    Live (chat 58, t28): Hinami slammed the TARDIS doors and stood in the
    console room; the Dalek stood outside. `visual_level_between` returns
    'none' for that pair and `spatial_rel` calls it `separated`/`far` -- no
    connecting geometry at all -- and her actions were still narrated into the
    Dalek's view, which then fed the Dalek's own next-turn context.

    Deliberately the HARD case only: no channel whatsoever. A body the
    perceiver cannot SEE but can still hear through a shut door is left alone,
    because dropping it would deny a legitimate perception -- that narrower
    case (sight asserted where only hearing exists) needs sense-cue analysis
    and is not this guard's job. Over-denial here would be the worse failure:
    a view is what a mind gets, and silence about someone audibly present is
    its own lie.

    Same shape as `_strip_self_narration`: whole sentences, subject only,
    nothing invented to replace what goes, and never empties a view.
    """
    if not view or not perceiver_name or not scene:
        return view, []
    names = [r["name"] for r in (roster or []) if r.get("name")]
    unreachable = set()
    for name in names:
        if name == perceiver_name:
            continue
        rel = spatial_rel(scene, cast_room(scene, perceiver_name, []),
                          cast_room(scene, name, []))
        # `separated` means no edge was found between the two rooms; `unknown`
        # means one of them has no room at all. Every other barrier is a real
        # relationship the perceiver may sense across at SOME volume.
        if str(rel.get("barrier") or "").lower() in ("separated", "unknown") \
                and not rel.get("same_room"):
            unreachable.add(name)
    if not unreachable:
        return view, []
    kept, dropped = [], []
    for stripped, subject in _sentence_subjects(
            str(view), names, split=_SENTENCE_SPLIT):
        if not stripped:
            continue
        if subject in unreachable:
            dropped.append(stripped)
        else:
            kept.append(stripped)
    if not dropped or not kept:
        return view, []
    return " ".join(kept), dropped


def _scrub_view_for(ctx, stage, view, perceiver_name, known, roster,
                    scene=None):
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
    refused = []
    view, self_narrated = _strip_self_narration(
        view, perceiver_name, [s["name"] for s in roster], refusals=refused)
    for reason in refused:
        ctx.warnings.append(
            f"{stage}: kept self-narration in the view of "
            f"{perceiver_name} — {reason}")
    for sentence in self_narrated:
        ctx.warnings.append(
            f"{stage}: dropped self-narration from the view of "
            f"{perceiver_name}: {sentence[:120]!r}")
    view, unreachable = _strip_unreachable_bodies(
        view, perceiver_name, scene, roster)
    for sentence in unreachable:
        ctx.warnings.append(
            f"{stage}: dropped a body with no sensory channel from the view "
            f"of {perceiver_name}: {sentence[:120]!r}")
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


def _visible_rooms_for(scene, observer, room_id):
    """`visible_adjacent_rooms`, minus whatever is at this observer's back.

    THE RULE WAS COMPUTED AND THEN NOT APPLIED. `visible_adjacent_rooms` asks a
    question about the ROOM -- it takes no observer at all -- so it reports every
    open-barrier neighbour as in view however the perceiver happens to be turned.
    `_behind_rooms` computes the correction directly above, and its docstring
    states the rule it exists to enforce: "an observer does not receive NEW
    VISUAL detail from a room behind them". Nothing subtracted one from the
    other. Both lists went into the same perceiver payload, naming the same
    room, and the model was left to reconcile them.

    Live, chat 67 t9: Hinami stands on Commercial Lane facing EAST, having come
    from Fountain Plaza, which is west and therefore behind her.
    `visible_rooms` and `behind_rooms` both named `fountain_plaza`, and her view
    came back with "Across the street, a middle-aged man by the fountain watches
    the foreign notes catch the light" -- a person, doing something, in a room
    she was not looking at, who then reappeared the following turn.

    Only SIGHT is gated, which is the whole point: this list exists behind
    `_SIGHT_BARRIERS`, while sound and the other channels ride
    `_source_channels` and are untouched. She can still hear the fountain. And
    `_behind_rooms` is empty when an observer has no movement history, so an
    observer who has not moved is not gated by this at all.
    """
    rooms = visible_adjacent_rooms(scene, room_id)
    behind = {r for r in (_behind_rooms(scene, observer) or []) if r}
    if not behind:
        return rooms
    return [r for r in rooms if r.get("room_id") not in behind]


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


def _co_present_company(scene, observer_name, bodies, known):
    """proximity_to_sources / behind_sources entries for the bodies simply
    STANDING with an observer at the top of the beat.

    The action-onset pass runs BEFORE the interaction loop, so
    `ctx.character_results` is empty and no cast member qualifies as a
    source the way the outcome pass admits them ("did their character step
    produce something"). The only channels that could carry a co-present
    body into a pass-1 payload were therefore the acting player (the
    `*_to_actor` fields), the observer's single `orientation.focus` slot,
    and the contact/scale/containment ledgers -- so two recognised
    characters standing in one lit room did not appear in each other's
    action-onset payloads at all. Because focus is ONE slot, the failure
    looked intermittent and one-directional (chat 63, reported three
    times: Tamamo, focused on the Doctor, sometimes saw him; he, focused
    on a doorway, never saw her).

    Delivered through the two fields the perception prompt already
    describes for co-located people, and as PRESENCE -- a tier, a side, an
    arc -- never anything act-shaped: the contacts ledger already taught
    this module that a bare relation record reads as an event and gets
    narrated as one.

    A roster is also a brand-new channel handing a mind other bodies, and
    the pass-1 output scrub floors only the PLAYER's identity -- so the
    identity floor is applied INPUT-side, per observer, before the payload
    exists:

    - a body `visual_level_between` answers "none" for (unlit, concealed
      by containment, behind a barrier) does not arrive at all;
    - a recognised body arrives under its name, carrying `sight` so a
      "shapes" sighting degrades honestly rather than growing a face;
    - an unrecognised body seen in full arrives as its unknown-actor
      descriptor, built from its disguise-adjusted VISIBLE appearance;
    - an unrecognised body seen only as shapes is a bare figure: its
      appearance summary describes what full sight would show, and a
      silhouette shows none of it;
    - a disguised body whose truth this observer is not in `known_to` for
      is never connected to its name, however well the observer knows
      the name -- that connection is the thing the disguise conceals.
    """
    recognized = known.get(observer_name) or []
    prox, behind = {}, []
    for body in bodies:
        name = body.get("name")
        if not name or name == observer_name:
            continue
        level = visual_level_between(scene, observer_name, name)
        if level == "none":
            continue
        tier = proximity_rel(scene, observer_name, name)
        if tier is None:
            continue            # co-located only, like the field it feeds
        known_to = body.get("disguise_known_to")
        undisguised_to_me = (
            known_to is None
            or str(observer_name).casefold() in known_to)
        if undisguised_to_me and _recognizes(name, recognized):
            label = name
        elif level == "full":
            label = _unknown_actor_label(
                name, body.get("appearance"), body.get("aliases"))
        else:
            label = "an indistinct figure"
        stem, n = label, 2
        while label in prox:    # two strangers can share a descriptor
            label, n = f"{stem} ({n})", n + 1
        entry = {
            "tier": tier,
            "side": entity_side(scene, observer_name, name),
            "arc": entity_arc(scene, observer_name, name),
            "sight": level,
        }
        prox[label] = entry
        if entry["arc"] == "rear":
            behind.append(label)
    return prox, behind


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


# Vertical motion, and nothing else. A beat can legitimately open and close a
# door, or have one body approach while another retreats, so most antonym pairs
# generate false positives -- but a hand cannot rise and descend in the same
# instant, and that is the one that bit. Deliberately narrow: this is a
# tripwire, and a tripwire nobody trusts gets ignored.
_RAISING = re.compile(r"\b(?:lift(?:s|ed|ing)?|rais(?:e|es|ed|ing)|"
                      r"hoist(?:s|ed|ing)?)\b")
_LOWERING = re.compile(r"\b(?:lower(?:s|ed|ing)?|descend(?:s|ed|ing)?)\b")


def _inverted_motion_check(ctx, stage, views, resolved_event):
    """Flag a view that reverses a physical direction the Director resolved.

    Perception's structured observations are re-derived from the scrubbed prose
    view precisely so a second representation cannot widen the information
    budget -- but nothing checks the PROSE against the objective event it is
    supposed to be a view of. A model that rewrites the beat is invisible.

    Measured on chat 52's last beat. Elyndra declared "lowering her steadily
    toward exposed groin"; the Director resolved "begins to lower her hand
    steadily toward the parted robe and hiked skirt", with no form of "lift"
    anywhere in it; and the player's view arrived as "lifting you to eye
    level". The narrator, which renders the view and not the event, then had no
    lowering to describe -- so the beat the story had actually committed to
    never reached the page.

    A WARNING, never a scrubber, for the same reason `_disguise_leak_check` is:
    the fix belongs upstream in what perception is handed, and rewriting a view
    on a regex would be a worse authority than the model it is policing.
    """
    event = str(resolved_event or "").casefold()
    if not event:
        return
    event_lowers = bool(_LOWERING.search(event))
    event_raises = bool(_RAISING.search(event))
    if event_lowers == event_raises:
        return                      # says both, or says neither
    for pid, view in (views or {}).items():
        text = str(view or "").casefold()
        if not text:
            continue
        if event_lowers and _RAISING.search(text) and not _LOWERING.search(text):
            said, saw = "lowering", "raising"
        elif event_raises and _LOWERING.search(text) and not _RAISING.search(text):
            said, saw = "raising", "lowering"
        else:
            continue
        ctx.warnings.append(
            f"{stage}: the view for {pid} describes {saw} where the resolved "
            f"event describes {said} -- perception has reversed a physical "
            "direction the Director committed to.")


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
    from commit import apply_attire_diff
    apply_attire_diff(sc, copy.deepcopy(diff), ctx, est, report=False)

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
        "visible_rooms": _visible_rooms_for(sc, p_name, p_room),
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
            "visible_rooms": _visible_rooms_for(sc, character_name(sh), r),
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
        labels = _observer_body_labels(
            perceiver, known, {p_name: p_appearance},
            include=[perceiver.get("name")])
        scoped["scene"] = _observer_scene_payload(
            sc, perceiver, body_labels=labels)
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

    # Every cast body with a position, whether or not it acts this beat --
    # the raw material for `_co_present_company` (which see): pass 1 has no
    # acting sources yet, so presence must come from who is simply THERE.
    # Appearance is resolved through the disguise context so an unrecognised
    # body's descriptor is built from its outward form, never the truth.
    co_present = []
    for c in ctx.cast:
        b_sh, _, _ = sheet_state(c)
        b_name = character_name(b_sh)
        b_room = character_room(sc, b_sh)
        if not b_name or not b_room:
            continue
        b_true = _appearance_as_prose(appearance_of(
            b_name, character_appearance(b_sh), sc))
        b_visible, _, b_known_to = _subject_disguise_context(
            chat["id"], b_name, b_true, known)
        co_present.append({
            "name": b_name, "room": b_room, "appearance": b_visible,
            "aliases": character_scene_keys(b_sh)[1:],
            "disguise_known_to": b_known_to,
        })

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
        if _previous_open_group_continuity(
                ctx, sc, p_name, character_name(sh), c["id"], p_room, r):
            rel = {**rel, "open_group_continuity": True}
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
        prox_to_others, behind_others = _co_present_company(
            sc, character_name(sh), co_present, known)

        perceivers.append({
            "id": c["id"], "name": character_name(sh), "room": r,
            "room_name": (rdata or {}).get("name") or r or "an unspecified area",
            "room_notes": ((rdata or {}).get("notes") or _room_notes_from_lore(r, ctx, sc)),
            "ambient_location": _ambient_location_for(sc, r),
            "visible_rooms": _visible_rooms_for(sc, character_name(sh), r),
            "senses": senses_of(sh),
            "attention": act.get("goal") or "ambient",
            "spatial_to_actor": rel,
            "visual_channel_to_actor": has_visual(rel),
            "scent_channel_to_actor": scent_level(rel),
            "proximity_to_actor": proximity_rel(
                sc, character_name(sh), p_name),
            "proximity_to_sources": prox_to_others,
            "behind_sources": behind_others,
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
        labels = _observer_body_labels(
            perceiver, known, {p_name: p_visible},
            include=[perceiver.get("name")])
        scoped["scene"] = _observer_scene_payload(
            sc, perceiver, body_labels=labels)
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

    # The structured sequence is the authority on chronology. Scalar speech is
    # retained only as a legacy fallback for stored interpretations predating
    # sequence speech elements.
    onset_sequence = list(interp.get("sequence") or [])
    if speech_elems and not any(
            isinstance(e, dict) and e.get("type") == "speech"
            for e in onset_sequence):
        onset_sequence.extend(speech_elems)

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
                     for e in speech_elems)
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
        # The model supplies ambient sensory prose; the declared event sequence
        # is removed and rebuilt below from structured data. It must not be
        # allowed to reorder two lines around the gesture between them.
        view = _strip_onset_rendering(view, onset_sequence, display)
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

        can_see = _in_plain_view(rel, vis)
        # Deterministic identity floor, LAST: the LLM's free prose was
        # never checked against knows_identity, so a model that wrote the
        # player's canonical name into a stranger's view walked straight
        # past the gate above. Quoted speech survives verbatim (a name
        # introduced aloud this beat is legitimate sensory signal;
        # recognition itself only flips at commit).
        # The roster this scrub enumerates was the PLAYER ALONE -- a
        # one-element list holding the persona -- so no pattern was ever built
        # for a cast name and the scrub could not fire on one. Live, chat 63
        # t165: two co-present bodies, one scrub pass, the warning reporting
        # `scrubbed unearned identity ['Hinami']` while "Tamamo" sat untouched
        # in the same sentence, delivered to an observer with no `known` entry
        # at all. The helper was never wrong; it was asked the wrong question.
        #
        # Same roster the outcome pass builds (see `_scrub_view_for`): every
        # body this observer does not recognise, filtered through `_recognizes`
        # so an alias/uid form counts as recognition. `co_present` is reused
        # rather than rebuilt -- it already resolves each body's
        # disguise-adjusted VISIBLE appearance and its scene aliases, so a
        # disguised body's descriptor is built from its outward form.
        #
        # Gated on the roster being non-empty rather than on `knows_identity`,
        # which is a scalar about the PLAYER only: under the old gate an
        # observer who recognised the player but not a cast member got no scrub
        # at all. Strictly wider -- when `knows_identity` is False the player is
        # in the roster, so this still fires wherever it used to.
        recognized = set(known.get(p["name"]) or [])
        unknown_sources = []
        if not knows_identity:
            unknown_sources.append(
                {"name": p_name, "appearance": p_visible, "aliases": []})
        for body in co_present:
            if body["name"] == p["name"] or _recognizes(
                    body["name"], recognized):
                continue
            unknown_sources.append({
                "name": body["name"],
                "appearance": body.get("appearance"),
                "aliases": body.get("aliases") or [],
            })
        if unknown_sources:
            view, leaked = _scrub_unknown_identities(
                view,
                allowed_forms=[p["name"], *recognized],
                unknown_sources=unknown_sources,
            )
            if leaked:
                ctx.warnings.append(
                    f"perception_act: scrubbed unearned identity {leaked} "
                    f"from the view of {p['name']}")
        # Pass 1 applies the identity floor directly rather than through
        # `_scrub_view_for`, so it needs this explicitly -- and it is the pass
        # that most needs it. The act view is written closest to the Director's
        # own resolved_event, which is omniscient by construction, so an
        # observer's view here is the likeliest place for that omniscience to
        # be copied through intact. Measured on a fresh 4-turn run: 1 of 17
        # views narrated its own perceiver.
        view, self_narrated = _strip_self_narration(
            view, p["name"], [p_name, *self_forms_by_name])
        for sentence in self_narrated:
            ctx.warnings.append(
                f"perception_act: dropped self-narration from the view of "
                f"{p['name']}: {sentence[:120]!r}")
        view = _dedupe_view_sentences(view)
        # Canonical onset projection is LAST. The model decides what ambient
        # detail legitimately reaches this observer; this deterministic pass
        # decides the exact order, wording and declared delivery of the
        # player's speech/actions. That makes speech -> turn -> speech an
        # invariant rather than a prompt preference.
        view = _inject_onset_sequence(
            view, onset_sequence, p, rel, display, can_see,
            sc, p_name,
            self_forms_by_name.get(p["name"]) or [p["name"]],
        )
        # A standing contact is felt on the beat the character DECIDES, not
        # only on the beat it is told about afterwards. Measured in chat 62:
        # the acting view was a median 460 characters against 812 for the
        # outcome view of the same character, and carried no sensation from
        # her own body while three contacts stood -- so she chose her conduct
        # numb and was told what she had felt once the choice was made.
        view = _deliver_standing_sensations(
            view, p["name"], sc, _standing_contacts_for(sc, p["name"]))
        # BODY-DETAIL FIDELITY FLOOR. The observer-scoped payload can carry the
        # exact exposed anatomy and the perception model can still collapse it
        # to generic "bare stomach" / "parted legs" prose. Rebuild the same
        # identity-safe projection and restore only details for regions the
        # MODEL'S OWN VIEW foregrounded; unrelated anatomy remains silent.
        body_labels = _observer_body_labels(
            p, known, {p_name: p_visible}, include=[p.get("name")])
        body_projection = _observer_scene_payload(
            sc, p, body_labels=body_labels).get("body_regions") or []
        view, restored_body_details = _deliver_foreground_body_details(
            view, body_projection)
        for detail in restored_body_details:
            ctx.warnings.append(
                "perception_act: restored foreground body detail omitted "
                f"by the model from view '{pid}': {detail[:120]}")
        clean_views[pid] = view or None

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
    # Every comparison here goes through `same_subject`, not casefold. The same
    # character routinely appears under two spellings at once -- a cast display
    # name and a scene entity id -- and the containment ledger names one while
    # the perceiver arrives as the other. Measured live: an enclosing character
    # was matched as "Elyndra" against a holder recorded as "elyndra_succubus",
    # so the occupant was not a touch candidate, `_surface_translate_event`
    # never fired, and the omniscient resolved_event -- naming the occupant's
    # interoceptive state in as many words -- went into the enclosing
    # character's payload intact. That is the own-body isolation rule breaking
    # on a string comparison: a mind may have its own body state and its own
    # scrubbed observations, never another mind's vitals.
    containment_names = set(hiding_holders_of(scene, perceiver_name))
    for other in (scene.get("positions") or {}):
        if same_subject(scene, str(other), perceiver_name):
            continue
        if any(same_subject(scene, holder, perceiver_name)
               for holder in hiding_holders_of(scene, other)):
            containment_names.add(str(other))
    contained = scene.get("contained") or {}
    if isinstance(contained, dict):
        for subject, record in contained.items():
            holder = str(
                record.get("in") if isinstance(record, dict) else record
                or ""
            ).strip()
            s_name = str(subject).strip()
            if holder and same_subject(scene, s_name, perceiver_name):
                containment_names.add(holder)
            elif s_name and same_subject(scene, holder, perceiver_name):
                containment_names.add(s_name)
    touch_candidates = {n for n in (contact_names | containment_names)
                        if n and not same_subject(scene, n, perceiver_name)}
    # A touch-only source: in spatial range, no visual channel, in physical
    # contact. The candidate may be spelled as an entity id while the source
    # tables are keyed by display name, so resolve rather than index -- the
    # returned name must be the SOURCE table's spelling, because that is what
    # every caller matches against.
    out = set()
    for name in touch_candidates:
        key = name if name in spatial_to_sources else next(
            (s for s in spatial_to_sources if same_subject(scene, s, name)),
            None)
        if key and not visual_channel_to_sources.get(key, False):
            out.add(key)
    return out


def _surface_translate_event(event_text, touch_only_sources):
    """Replace act-naming sentences for touch-only sources with surface-sensation prose.

    The resolved_event text is omniscient: it names what every actor is
    doing ("she curls her fingers around the knife at her belt").  A perceiver who can
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
    element and redact on identity, never on text (docs/UNBUILT.md §3.1, and
    §4.2 for the primitive). Until the Director emits that, this is a floor,
    not a proof, and the perception prompt's own instruction remains the second
    layer.

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
    from commit import apply_attire_diff, dedup_minted_rooms

    diff = copy.deepcopy(res.get("state_diff") or {})
    dedup_minted_rooms(chat["id"], sc, diff)
    prev_scene = sc
    sc = merge_scene_with_diff(sc, diff)
    # Attire is commit-owned and intentionally absent from spatial's generic
    # merge. Preview the exact same canonicalized/region-derived result commit
    # will persist, on copies, before any observer-specific body projection.
    apply_attire_diff(sc, diff, ctx, res, report=False)

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
        _o_names = [character_name_from_text(c["sheet"]) for c in ctx.cast]
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
    cast_by_name = {character_name_from_text(c["sheet"]): c["id"] for c in ctx.cast}

    perceivers = [{
        "id": "player", "name": p_name, "room": p_room,
        "room_name": (p_rdata or {}).get("name") or p_room or "an unspecified area",
        "room_notes": ((p_rdata or {}).get("notes") or _room_notes_from_lore(p_room, ctx, sc)),
        "ambient_location": _ambient_location_for(sc, p_room),
        "visible_rooms": _visible_rooms_for(sc, p_name, p_room),
        "senses": senses_of(pers), "attention": "engaged",
        "knows_identity": True,
        **_source_channels(sc, p_name, p_room, sources, prev_sc=prev_scene),
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
            "visible_rooms": _visible_rooms_for(sc, e_name, e_room),
            "senses": senses_of(extra), "attention": "engaged",
            "knows_identity": True,
            **_source_channels(sc, e_name, e_room, sources, prev_sc=prev_scene),
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
            "visible_rooms": _visible_rooms_for(sc, character_name(sh), r),
            "senses": senses_of(sh),
            "attention": act.get("goal") or "ambient",
            "knows_identity": p_name in (known.get(character_name(sh)) or []),
            **_source_channels(sc, character_name(sh), r, sources, prev_sc=prev_scene),
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
        labels = _observer_body_labels(
            perceiver, known, appearances,
            include=[perceiver.get("name")])
        scoped["scene"] = _observer_scene_payload(
            sc, perceiver, body_labels=labels)
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
        # What the hearing gate decided this mind actually receives, kept so
        # the scrub chain below can be checked against it. See the floor at
        # the end of this loop.
        delivered_lines = []
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
                if str(d_speaker).strip().casefold() in _ubiq:
                    # A bodiless voice (ship AI, station PA) has no room, and
                    # spatial_rel(None, ...) yields barrier='unknown' ->
                    # hear_level 'none', so the Director could voice the ship's
                    # computer and NOBODY would hear it. Treat it as present.
                    #
                    # Asked of the ENTITY, never of whether a position record
                    # happens to exist. This used to be gated on the speaker
                    # having no room, which meant one stale `positions` entry
                    # disabled the rescue entirely -- and the artifact that
                    # motivated it is exactly such an entry. Measured live: a
                    # ship's computer flagged `ubiquitous` still pinned to the
                    # room it was first voiced in answered a direct question
                    # from four decks away, and the answer was dropped at
                    # hear_level 'none'. Being bodiless is a fact about the
                    # thing; a position on it is the category error, not a
                    # reason to stop believing the flag.
                    rel = {"same_room": True, "barrier": "open",
                           "distance": "near",
                           "note": "bodiless voice, present throughout"}
                else:
                    sp_room = d.get("speaker_room") or room_of(sc, d_speaker)
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
            # Only `full` is recorded for the floor below. A `fragment` is
            # rendered as a muffled paraphrase rather than the body, so it has
            # no verbatim form to check for, and re-injecting it every pass
            # would stack duplicates.
            if level == "full":
                delivered_lines.append(
                    (display, d.get("exact_quote"), d.get("volume", "normal"),
                     can_see, bool(rel.get("inside_source"))))
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
            ctx, "perception_outcome", view, p["name"], known, ident_roster,
            scene=sc)
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
        view = _dedupe_view_sentences(view)
        # HEARD-LINE FLOOR. Everything above this point can REMOVE text: three
        # scrubs and a dedupe, each correct on its own and none of them aware
        # that a line the hearing gate already granted might be inside what
        # they take. Injection runs BEFORE all of them, and nothing re-checked
        # afterwards, so a line could be delivered and then quietly deleted.
        #
        # Live (chat 38, t137): the Doctor walked beside the player and spoke
        # four times, all `normal` volume, same room, open barrier. Her view
        # ends "...as we scan the mist-shrouded surroundings together. Yeah, I
        # bet I will."" -- an orphaned tail with a closing quote and no
        # opening, the signature of a partial quoted span being removed from
        # the middle of a delivered line. The other three lines are absent
        # entirely. Across the stored corpus, 30 of 1549 lines spoken by
        # somebody standing in the player's own room never reached their view.
        #
        # Nothing downstream could catch it either: the narrator's dialogue
        # fidelity check compares the PROSE against the VIEW, so a line lost
        # from the view is a line the check agrees is not missing.
        #
        # Re-injection is safe by construction: these bodies come from the
        # Director's dialogue_log and passed this perceiver's own hearing gate
        # a few lines above. That is exactly what the scrubs are FOR -- they
        # exist to remove dialogue with no such provenance.
        for display, quote, volume, can_see, conducted in delivered_lines:
            body = _quote_body(quote)
            if not body or _contains_quote(view, body):
                continue
            view = _inject_dialogue(view, display, quote, "full", volume,
                                    can_see, conducted=conducted)
            ctx.warnings.append(
                f"perception_outcome: restored a heard line dropped by the "
                f"scrub chain from view '{pid}': \"{body[:80]}\"")
        view = _deliver_standing_sensations(
            view, p["name"], sc, _standing_contacts_for(sc, p["name"]))
        # Same floor as action-onset, now against commit's previewed attire.
        # This is the seam chat 68 exposed: the model received exact midriff
        # and groin descriptions, foregrounded both surfaces, and still
        # returned only generic "bare stomach" / "parted legs" language.
        body_labels = _observer_body_labels(
            p, known, appearances, include=[p.get("name")])
        body_projection = _observer_scene_payload(
            sc, p, body_labels=body_labels).get("body_regions") or []
        view, restored_body_details = _deliver_foreground_body_details(
            view, body_projection)
        for detail in restored_body_details:
            ctx.warnings.append(
                "perception_outcome: restored foreground body detail omitted "
                f"by the model from view '{pid}': {detail[:120]}")
        clean_views[pid] = view or None

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
    _inverted_motion_check(ctx, "perception_outcome", clean_views,
                           res.get("resolved_event"))
    return {
        "views": clean_views,
        "observations": _observations_from_clean_views(clean_views),
    }
