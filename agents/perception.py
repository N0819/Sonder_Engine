"""Opening, action-onset, and outcome perception agents."""

from __future__ import annotations

import copy
import json
import re

from language_runtime import linguistic
from story.character_schema import (
    character_appearance,
    character_name,
    character_name_from_text,
    character_senses,
    name_boundary_regex,
    persona_appearance,
    persona_name,
    persona_senses,
)
from core.db import q, wget
from story.scene import (
    NON_AWAKE_GATED,
    active_disguises,
    active_transformations,
    conceal_disguised_parts,
    transformed_parts,
    transformed_true_appearance,
    appearance_of,
    apply_awareness_diff,
    awareness_map,
    awareness_of,
    disguise_breaks_recognition,
    disguise_known_to,
    disguised_visible_appearance,
    get_scene,
    is_player_speaker,
    persona_of,
    senses_of,
    sheet_state,
)
import os

from mind import affect
from world.spatial import (
    apply_contact_ops,
    hiding_holders_of,
    ambient_scope,
    contact_sensation,
    egocentric_frame,
    _entity_named,
    entity_arc,
    entity_side,
    has_visual,
    effective_light,
    visual_level_between,
    hear_level,
    measured_proximity_rel,
    merge_scene_with_diff,
    normalize_barrier,
    normalize_bearing,
    proximity_rel,
    relative_bearing,
    resolve_substance_ops,
    room_layout,
    room_of,
    comms_link,
    same_subject,
    scent_level,
    spatial_facts,
    spatial_rel_between,
    substance_event_clause,
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


def _dialogue_hear_level(entry, rel, observer_name, proximity=None):
    """Audibility of one dialogue entry to an observer.

    Ordinary spatial hearing (hear_level) decides first -- including the
    `proximity` downgrade, which the ONSET floor always applied and this
    helper's outcome-pass caller did not, so a mutter crossed a great hall at
    full volume on the outcome pass alone (register L3: two floors, one rule,
    different answers). Pass only a MEASURED tier (see
    `spatial.measured_proximity_rel`): "near" is mostly a default, and a
    default must not silence a conversation.

    Hearing only ever gets OVERRIDDEN in one direction -- a line it would DROP
    ('none', out of earshot) is rescued to 'full' when the line is a
    TRANSMISSION addressed to THIS observer: a combadge/radio/intercom carries
    the voice across the physical barrier that ordinary hearing can't. A line
    already audible is never altered, so same-room and open-door hearing are
    untouched.

    A transmission is recognised by either signal:
      - the director marked it medium:'comm' (explicit), or
      - it plainly NAMES this observer (intended_target) at a spoken volume
        while they are out of earshot -- you do not hold a by-name exchange with
        someone in another room without a channel, so treating it as ambient
        sound and dropping it is the TR-2 bug. This shape-based floor keeps the
        guarantee from depending on the director remembering to tag every line.

    The shape floor's premise is a BARRIER: a by-name exchange across one
    implies a device carrying it. An enclosure implies no such thing -- being
    named by a voice beyond the mass around you creates no channel through
    it -- so a drop caused by the enclosure directions is never shape-rescued.
    An explicit medium:'comm' tag still crosses (a radio in a pocket works).

    The comm path carries only the VOICE; the caller sets can_see separately (a
    transmission grants no sight).

    The one implementation lives in `agents/composer.py` (`line_hear_level`),
    where the deterministic composer's Layer A admits dialogue percepts; this
    name survives as the model path's (and the quality harness's) entry point
    so the two paths cannot drift apart."""
    return composer.line_hear_level(
        entry, rel, observer_name, proximity=proximity)


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
def _ling(name):
    """One deterministic recognition table from the ACTIVE story pack.

    These cue tables used to be English literals in this module, and
    `linguistics.json` had no `agents.perception` entry at all -- so every
    Japanese percept fell through to the `mixed` channel with flat salience,
    and `_SELF_DIRECTED` never fired, telling an observer that an event
    landing on their own body was somebody else's business.

    Read at use time, never at import: the story language is a contextvar and
    two languages can be running in the same process.
    """
    return linguistic("agents.perception", name)


# Sentence end, script-aware, and the module's ONLY definition -- a second,
# weaker binding of this name lived 1,250 lines below and silently won, so
# every reader got a splitter that treated neither `...` nor a trailing
# bracket as an ending while this comment described one that did.
#
# The ASCII branch needs trailing whitespace; the CJK branch must not,
# because Japanese writes no space after 。 -- so an English-only splitter
# returned the WHOLE Japanese event as one "sentence", and every guard that
# keeps a safe subset of sentences (the concealment redactor above all) had
# no subset to keep.
#
# The terminator class carries `…`, because an ellipsis is how prose ends a
# sentence and a beat written with one reached the redactor as a single
# unsplittable block that had to be thrown away whole to protect one clause.
#
# Closing quotes and brackets ride WITH the sentence they end -- '…to me!?"
# The voice is…' must keep its quote -- so they sit inside the LOOKBEHIND
# rather than inside the match, where the split would eat them. That was the
# deleted twin's one genuine advantage over this one, and the reason the
# repair is a union rather than a deletion. Python requires a lookbehind to
# be fixed-width, hence one alternative per closer count rather than a `*`.
_SENTENCE_SPLIT = re.compile(
    r"(?<=[.!?…])\s+"
    r"|(?<=[.!?…][\"'”’)\]])\s+"
    r"|(?<=[.!?…][\"'”’)\]][\"'”’)\]])\s+"
    r"|(?<=[。！？])[」』\"'”’)\]]*\s*")

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


def _cue_hits(cues, folded):
    return sum(1 for cue in cues if re.search(cue, folded))


def _atom_channel(folded):
    for channel, cues in _ling("_CHANNEL_CUES"):
        if _cue_hits(cues, folded):
            return channel
    return "mixed"


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


from . import composer

from .common import (
    preview_player_state_assertions,
    _append_micro_view,
    _append_once,
    _dedupe_view_sentences,
    _player_name_forms,
    self_name_forms,
    self_reference_forms,
    _sentence_subjects,
    _appearance_as_prose,
    _resolve_player_room,
    _room_notes_from_lore,
    crowds_for_room,
    artifacts_for_room,
    couriers_for_room,
    _scrub_unknown_identities,
    _mask_quoted_spans,
    _unmask_quoted_spans,
    _VIEW_MASK,
    _scrub_invented_dialogue,
    _recognizes,
    # Re-export only: tests/test_name_variant_recognition.py:18 imports it
    # through this module. It belongs to common.py and should be imported
    # from there; the test file is outside this slice's ownership.
    _significant_name_tokens,
    observable_action_text,
    player_speech_lines,
    _strip_identity_tokens,
    _unknown_actor_label,
    observer_body_regions,
    scene_extra_parts,
    cast_room,
    character_room,
    character_scene_keys,
)


def _ubiquitous_names(sc):
    """Bodiless voices in this scene (ship AI, station PA), casefolded.

    Imported lazily: perception must not take a hard dependency on scene.py's
    import graph for what is a small, optional lookup."""
    try:
        from story.scene import ubiquitous_speaker_names
        return ubiquitous_speaker_names(sc)
    except Exception:
        return frozenset()


def _saw_across_beat(sc, prev_sc, perceiver_name, source_name, rel,
                     senses=None):
    """Visual channel to one source, over the whole beat (see _source_channels).

    Per-body and light-aware via `visual_level_between` when the perceiver has
    a position, room-level otherwise. Answered against the outcome scene first;
    only if that says no does the pre-diff scene get asked, so this can add a
    channel the beat closed and can never remove one it opened.

    `senses` is the observer's card, run through the same gate every other
    admission now uses (`composer._sense_graded`): an authored-blind body has
    no visual channel to anything, however the world is lit.
    """
    def _at(scene):
        if not scene:
            return False
        if room_of(scene, perceiver_name) is not None:
            return composer._sense_graded(
                visual_level_between(scene, perceiver_name, source_name),
                "sight", senses) != "none"
        if not has_visual(rel):
            return False
        return composer._sense_graded("full", "sight", senses) != "none"
    return _at(sc) or _at(prev_sc)


def _sense_card(sheet):
    """The STRUCTURED card senses, which are what the G4 gate takes.

    `scene.senses_of` returns senses_as_text -- a prose sentence, built for a
    model prompt. `spatial.sense_adjusted` wants the list of
    `{channel, acuity, range}` records, and the perceiver dicts carried only
    the prose, which is half of why the gate reached no composed view: even a
    reader of the `senses` key would have handed the gate a string and got the
    level back unchanged. Same dispatch as `senses_of`, so a persona and a
    character card resolve the same way they do everywhere else.
    """
    if not isinstance(sheet, dict):
        return []
    if "psychology" in sheet or "core" in sheet:
        return character_senses(sheet)
    if "narration" in sheet:
        return persona_senses(sheet)
    return []


def _source_channels(sc, perceiver_name, perceiver_room, sources,
                     prev_sc=None, senses=None):
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
        # THE body-to-body relation builder (see spatial_rel_between): it
        # carries concealment, the threshold-crossing grace, and all three
        # enclosure directions. It used to be built here by hand -- bare
        # spatial_rel plus a concealed patch plus a one-way inside_source
        # check -- which left `enclosed_from_source` and `source_enclosed`
        # unset on every production rel, so the enclosure guards in
        # hear_level/scent_level were guards that could not fire: a voice
        # sealed inside a body reached the whole room at full clarity
        # (register L2). Argument order also matters: spatial_rel stamps the
        # light of the room being LOOKED AT, and the hand-built form passed
        # (source_room, perceiver_room) -- grading sight of the source by the
        # light where the PERCEIVER stood (register L6).
        rel = spatial_rel_between(sc, perceiver_name, s["name"],
                                  observer_room=perceiver_room,
                                  target_room=s["room"])
        if prev_sc:
            prev_rel = spatial_rel_between(
                prev_sc, perceiver_name, s["name"],
                observer_room=room_of(prev_sc, perceiver_name) or perceiver_room,
                target_room=room_of(prev_sc, s["name"]) or s["room"])
            # Only ever upgrades. `has_visual` is the room-level question and
            # is the one that goes false when an edge is severed mid-beat --
            # which is exactly the transition this exists to preserve.
            if has_visual(prev_rel) and not has_visual(rel):
                rel = {**prev_rel, "was_reachable_at_beat_start": True}
        rels[s["name"]] = rel
    return {
        "spatial_to_sources": rels,
        "visual_channel_to_sources": {
            n: (_saw_across_beat(sc, prev_sc, perceiver_name, n, rels[n],
                                 senses))
            for n in rels
        },
        "scent_channel_to_sources": {
            n: composer._sense_graded(scent_level(r), "scent", senses)
            for n, r in rels.items()},
    }


def _with_comm_channel(scene, rel, *, speaker, observer, observer_room=None,
                       speaker_room=None):
    """Attach the live channel carrying this voice, when there is one.

    Computed HERE and handed over as data, because `agents/composer.py` is the
    layer that may not read the world: it decides admission from typed
    percepts, and a renderer that could reach into the scene could add to what
    it renders. Perception already holds the scene, the rooms and the names, so
    the lookup belongs on this side of the line.

    Absent when no channel applies, so the composer's `rel.get("comm_channel")`
    reads as "no channel" rather than as "unknown".
    """
    if not isinstance(rel, dict):
        return rel
    try:
        channel = comms_link(
            scene,
            speaker_room or room_of(scene, speaker),
            observer_room or room_of(scene, observer),
            speaker_name=speaker, observer_name=observer)
    except Exception:
        return rel
    return {**rel, "comm_channel": channel} if channel else rel


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
    # The two failures are not equal. Over-denial is the worse one: silence
    # about something a mind plainly perceived is its own lie, and it is
    # invisible afterwards. Being told about yourself in the third person for
    # one beat is bounded and visible; losing what you saw is neither. So when
    # the drop would leave a view with no assertion of sight in it at all, the
    # view stands and the warning carries it.
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


def _behind_rooms(scene, observer):
    """Room ids at the observer's back (the way they came), from their
    egocentric frame. Approximate field of view: an observer does not receive
    NEW VISUAL detail from a room behind them -- they get sound/other channels
    and what they already remember, but not fresh sight (you don't watch the
    room you just walked out of unless you turn). Empty when the observer has
    no movement history, so nothing is gated. See the perception FOV clause.

    THE REAR ARC, NOT JUST DEAD ASTERN. `relative_bearing` already distinguishes
    `behind_left` / `behind_right`, but `egocentric_frame` collapses those into
    the LATERAL buckets -- correctly, because an exit behind your left shoulder
    is still the one on your left when prose places it. Reading only `behind`
    therefore gated a doorway at 180 degrees and let one at 135 through, so a
    body could turn its back on a room and go on receiving fresh sight of it.

    Live (chat 74 turn 57): a character turned from the open doorway ('w') to
    the towel rack ('ne'). `relative_bearing('ne','w')` is `behind_left`, the
    room landed in `left`, and his view read "back to the room. You see Hinami".

    This matches what the WITHIN-room path already does -- `entity_arc` gives a
    source a front/rear arc rather than a single astern bearing -- so the two
    scales of the same rule finally agree. Only sight is gated either way.
    """
    frame = egocentric_frame(scene, observer)
    behind = [e.get("to") for e in frame.get("behind") or [] if e.get("to")]

    orientation = scene.get("orientation") or {}
    rec = next((v for k, v in orientation.items()
                if str(k).casefold() == str(observer).casefold()), None) or {}
    facing = rec.get("facing")
    if not facing:
        return behind                    # movement fallback only; no guessing

    room = (scene.get("rooms") or {}).get(room_of(scene, observer)) or {}
    for edge in room.get("adjacent") or []:
        if not isinstance(edge, dict) or not edge.get("to"):
            continue
        rel = relative_bearing(facing, normalize_bearing(edge.get("dir")))
        if str(rel or "").startswith("behind") and edge["to"] not in behind:
            behind.append(edge["to"])
    return behind


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
        hidden = disguise_breaks_recognition(
            body.get("disguise_known_to"), observer_name,
            body.get("disguise_conceals_identity"))
        if not hidden and _recognizes(name, recognized):
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
        rel = spatial_rel_between(scene, observer, sname,
                                  observer_room=o_room,
                                  target_room=s.get("room"))
        # Per-BODY, so a source standing in a torch's pool is visible while the
        # rest of the dark room is not -- the room-level answer cannot see that.
        visible = (visual_level_between(scene, observer, sname) != "none"
                   and sname not in behind)
        # A voice/breath tell needs clean hearing, not mere co-location: an
        # enclosed body's position derives to its carrier's room, so bare
        # `same_room` handed a breath tell across a seal that muffles the
        # voice itself to a fragment (register L2). Conducted hearing
        # (observer inside the source) stays full, so those tells survive;
        # a crate stays a thing you can be heard through (no body-mass flag,
        # unchanged).
        audible = bool(rel.get("same_room")) \
            and hear_level(rel, "normal") == "full"
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

    Returns (visible_appearance, disguise_active, known_to_or_None,
    conceals_identity):
    - visible_appearance: what EVERY observer visually perceives -- the
      disguised outward form when a disguise is active (a concealed feature is
      not seen even by someone who knows it is there), else the true
      appearance unchanged.
    - disguise_active: True when a disguise is in force, None when not. It
      used to be a PAYLOAD -- second-person instruction to the perception model
      ("Every observer VISUALLY perceives only outward_visible_appearance")
      plus the `concealed_truth` itself, so an observer in known_to could be
      given the truth as KNOWLEDGE rather than as vision. There is no
      perception model, and the block reached no consumer: it is a flag now,
      and the wording it carried was prompt text with nowhere to be a prompt.
      None rather than False for the absent case, because that is the answer
      every caller and test already reads.
    - known_to: casefolded names that legitimately know the truth, or None.
      LIVE, and the reason the knowledge layer is not entirely gone: it feeds
      `scene.disguise_breaks_recognition`, so a body's acquaintances still
      recognise them through a disguise that conceals identity.
    - conceals_identity: whether this disguise covers what a body is
      RECOGNISED by (a face, a build, a voice) as opposed to a feature it
      merely hides. False for a glamour over fox ears: the face is still
      the face, so anyone who knows her still knows her -- wearing
      unfamiliar ears. See `scene.disguise_breaks_recognition`.

    Feeding the disguised appearance is the primary, fail-safe fix: the view
    is composed FROM the disguised form, so a concealed feature cannot be
    rendered as seen by anybody.

    RESIDUAL, and it is a SUBTRACTION rather than a leak: an observer in
    known_to no longer receives the concealed truth anywhere. They recognise
    the body, and they are not told what is under the disguise. Restoring it
    means putting the truth in the CHARACTER payload -- knowledge is not
    perception, and the percept IR is deliberately about what a channel
    delivered -- which is a design decision beyond removing the dead block.
    """
    # A TRANSFORMATION RESOLVES FIRST, AND IS NOT A DISGUISE. It changes the
    # body's TRUE appearance -- there is no concealed truth, nobody sees
    # through it, and no observer is granted knowledge of an older shape. So
    # it lands here, before the concealment layer, and a body that is merely
    # transformed returns with no disguise payload and no known_to at all.
    key = str(subject_name or "").casefold()
    transformation = active_transformations(chat_id).get(key)
    true_appearance = transformed_true_appearance(
        true_appearance, transformation)

    disguise = active_disguises(chat_id).get(key)
    if transformation and disguise:
        # ONE OUTWARD FORM, AND THE TRANSFORMATION IS IT. The two kinds are a
        # singular GROUP (`scene.SINGULAR_BODY_CONDITIONS`), enforced at the
        # write -- but a branch copies conditions wholesale without a write,
        # and rows minted before the rule was written are still out there.
        # Live (chat 74): "you allow your glamour to come undone" minted a
        # `physical_transformation` BESIDE three active disguises instead of
        # ending them, so a body that had just revealed its true form went on
        # presenting the false one. The observer watched the ears rise and
        # then saw human ears again on the very next beat.
        #
        # The transformation wins because it is a statement about the BODY,
        # while a disguise is a statement about what is shown of it -- and a
        # body cannot be concealing a form it no longer has.
        disguise = None
    if not disguise:
        return true_appearance, None, None, False
    known_to = disguise_known_to(disguise, subject_name, known_map)
    visible = disguised_visible_appearance(true_appearance, disguise)
    return visible, True, known_to, bool(disguise.get(
        "conceals_identity"))


def _subject_concealed_terms(chat_id, subject_name):
    """Tripwire terms for a body, through the SAME precedence the concealment
    layer uses.

    Read straight from `active_disguises` this was a second source of truth,
    and the two disagreed exactly when it mattered. `_subject_disguise_context`
    drops the disguise when the body is TRANSFORMED -- so it returns
    `known_to=None` -- while the terms came back from the dead disguise anyway.
    The tripwire then held concealed features with nobody marked as knowing
    them, so EVERY observer read as unaware and an aware one got flagged.

    Live (chat 74): Hinami's `glamour_dropped` transformation correctly
    overrode three stale disguise rows, and `perception_outcome` still warned
    that 'fox ears' had leaked to The Doctor -- who is in `known_to`, and who
    by then was looking at ears that were genuinely there. The view was right;
    the warning was noise, and noise on a firewall tripwire is expensive
    because it trains a reader to ignore it.

    A transformed body conceals nothing: it is not hiding a feature, it HAS
    the feature. So there is nothing to tripwire on.
    """
    key = str(subject_name or "").casefold()
    if active_transformations(chat_id).get(key):
        return []
    return [t for t in ((active_disguises(chat_id).get(key) or {})
                        .get("concealed_terms") or []) if t]


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


def perception_establish(ctx, nonce):
    chat = ctx.chat
    est = ctx.director_establish or {}
    sc = get_scene(chat["id"], chat)
    diff = est.get("state_diff") or {}
    sc = merge_scene_with_diff(sc, diff)
    from persist.commit import apply_attire_diff
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
        "crowds": crowds_for_room(ctx.chat.id, sc, p_room),
        "couriers": couriers_for_room(ctx.chat.id, sc, p_room),
        "notices": artifacts_for_room(ctx.chat.id, sc, p_room),
        "visible_rooms": _visible_rooms_for(sc, p_name, p_room),
        "senses": senses_of(pers), "sense_card": _sense_card(pers),
        "attention": "engaged",
        "knows_identity": True,
        "entity_state": p_state,
        **_source_channels(sc, p_name, p_room, sources,
                           senses=_sense_card(pers)),
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
            "crowds": crowds_for_room(ctx.chat.id, sc, r),
            "couriers": couriers_for_room(ctx.chat.id, sc, r),
            "notices": artifacts_for_room(ctx.chat.id, sc, r),
            "visible_rooms": _visible_rooms_for(sc, character_name(sh), r),
            "senses": senses_of(sh), "sense_card": _sense_card(sh),
            "attention": act.get("goal") or "ambient",
            "knows_identity": p_name in (known.get(character_name(sh)) or []),
            "entity_state": entity_states.get(character_name(sh)) or {},
            **_source_channels(sc, character_name(sh), r, c_sources,
                               senses=_sense_card(sh)),
            "proximity_to_sources": _proximity_to_sources(sc, character_name(sh), c_sources),
            "behind_sources": _behind_sources(sc, character_name(sh), c_sources),
            "room_layout": room_layout(sc, character_name(sh)),
        })

    # Consciousness gate (rare at opening, but a scenario may start someone
    # unconscious/asleep): overlay the establish diff onto committed conditions.
    amap = apply_awareness_diff(awareness_map(chat["id"]), diff)
    # The gate itself is INSIDE the composer orchestrators, per perceiver
    # (`if p.get("awareness") in NON_AWAKE_GATED`), so this loop stamps the
    # verdict and nothing here needs to partition on it.
    for p in perceivers:
        p["awareness"] = awareness_of(amap, p["name"])

    return _composer_establish(
        ctx, sc, perceivers, known, p_name, p_appearance,
        entity_states, sensory_events)

def perception_act(ctx, nonce):
    chat = ctx.chat
    interp = ctx.director_interpret
    sc = get_scene(chat["id"], chat)
    # Player-authored standing contact is true before reactors decide. Preview
    # it on a copy so pass 1 carries each participant's bodily endpoint while
    # leaving persistence solely to director_resolve/commit. No ageing here:
    # the durable merge will apply this beat exactly once.
    if interp.get("contact_assertions"):
        sc = apply_contact_ops(
            copy.deepcopy(sc), interp.get("contact_assertions"), _age=False)
    pers = persona_of(chat)
    known = wget(chat["id"], "known", {})
    action = interp.get("action")
    if not isinstance(action, dict):
        action = {}

    p_room = ctx.get("_player_room")
    if p_room is None:
        p_room = _resolve_player_room(sc, pers, interp, ctx.cast, ctx.input)
        ctx["_player_room"] = p_room

    p_name = pers.get("name") or persona_name(pers)
    # WHAT THE PLAYER SAID HAPPENED, HAS HAPPENED -- here, before a single
    # observer's view is built. Everything the player asserted about their own
    # body reached the scene only through director_resolve, which runs AFTER
    # every character has declared, so a player who took their own top off or
    # went to their knees was perceived in the previous posture and previous
    # outfit for the whole beat in which they changed both.
    #
    # Guarded by subject in `validated_player_state_assertions`, applied to a
    # COPY, persisted by nobody here: commit still writes each channel exactly
    # once, from resolve. It lands before `p_appearance` and before the
    # composer reads `sc`, because those are how a body reaches a view at all.
    sc = preview_player_state_assertions(
        sc, interp.get("state_assertions"), ctx, p_name)
    p_appearance = _appearance_as_prose(appearance_of(
        p_name, pers.get("appearance") or persona_appearance(pers), sc))
    # A physical disguise conceals the actor's real appearance from observers:
    # p_visible is what is actually SEEN (disguised form when active), fed to
    # both the LLM and the deterministic injection below so a concealed feature
    # is never rendered as perceived.
    (p_visible, _p_disguise, p_disguise_known,
     p_disguise_conceals) = _subject_disguise_context(
        chat["id"], p_name, p_appearance, known)
    p_disguise_terms = _subject_concealed_terms(chat["id"], p_name)

    speech_elems = [
        e for e in (interp.get("sequence") or [])
        if e.get("type") == "speech" and e.get("text")
    ]
    if not speech_elems and interp.get("speech"):
        speech_elems = [{"type": "speech", "text": interp["speech"],
                         "volume": interp.get("speech_volume", "normal"), "tone": ""}]

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
        b_visible, _, b_known_to, _ci = _subject_disguise_context(
            chat["id"], b_name, b_true, known)
        co_present.append({
            "name": b_name, "room": b_room, "appearance": b_visible,
            "aliases": character_scene_keys(b_sh)[1:],
            "disguise_known_to": b_known_to,
            "disguise_conceals_identity": _ci,
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
        # THE body-to-body relation builder: concealment, the
        # threshold-crossing grace, and the three enclosure directions in one
        # place (register L2 -- built by hand here, the enclosure flags were
        # never set and hear_level's guards could not fire). Argument order is
        # (observer, actor): spatial_rel stamps the light of the room being
        # LOOKED AT, and the hand-built form passed (p_room, r), grading
        # sight OF the actor by the light where the OBSERVER stood -- a full
        # visual channel to an actor standing in darkness (register L6).
        rel = spatial_rel_between(sc, character_name(sh), p_name,
                                  observer_room=r, target_room=p_room)
        if _previous_open_group_continuity(
                ctx, sc, p_name, character_name(sh), c["id"], p_room, r):
            rel = {**rel, "open_group_continuity": True}
        rdata = (sc.get("rooms") or {}).get(r) if r else None
        prox_to_others, behind_others = _co_present_company(
            sc, character_name(sh), co_present, known)

        perceivers.append({
            "id": c["id"], "name": character_name(sh), "room": r,
            "room_name": (rdata or {}).get("name") or r or "an unspecified area",
            "room_notes": ((rdata or {}).get("notes") or _room_notes_from_lore(r, ctx, sc)),
            "ambient_location": _ambient_location_for(sc, r),
            "crowds": crowds_for_room(ctx.chat.id, sc, r),
            "couriers": couriers_for_room(ctx.chat.id, sc, r),
            "notices": artifacts_for_room(ctx.chat.id, sc, r),
            "visible_rooms": _visible_rooms_for(sc, character_name(sh), r),
            "senses": senses_of(sh), "sense_card": _sense_card(sh),
            "attention": act.get("goal") or "ambient",
            "spatial_to_actor": rel,
            "visual_channel_to_actor": has_visual(rel) and composer._sense_graded(
                "full", "sight", _sense_card(sh)) != "none",
            "scent_channel_to_actor": composer._sense_graded(
                scent_level(rel), "scent", _sense_card(sh)),
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

    return _composer_act(
        ctx, sc, interp, perceivers, known, p_name, p_visible,
        p_disguise_known, p_disguise_conceals, p_disguise_terms, co_present,
        amap, speech_elems, action)

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
        # name_boundary_regex, not \b: Japanese particles are word characters,
        # so `\bミカ\b` never matched `ミカは棚に向かう` and the concealed
        # sentence was kept verbatim. This decides who may see an act, so it
        # has to hold in every script the story is written in.
        names_concealed = any(
            name_boundary_regex(name).search(folded)
            for name in concealed_names
        )
        if names_concealed:
            continuing = True
            continue
        if continuing and _ling("_PRONOUN_SUBJECT").match(sentence):
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
    from persist.commit import apply_attire_diff, dedup_minted_rooms

    diff = copy.deepcopy(res.get("state_diff") or {})
    dedup_minted_rooms(chat["id"], sc, diff)
    prev_scene = sc
    substance_events = resolve_substance_ops(
        prev_scene, diff.get("substance_ops"))
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
        from world.spatial_frames import infer_came_from, infer_focus, infer_facing
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
    # view: p_appearance becomes the disguised (visible) form, so no percept
    # built below can carry a concealed feature. The knowledge layer is
    # `known_to` alone -- see `_subject_disguise_context`, which also records
    # what went missing when its prose payload did.
    (p_appearance, p_disguise, p_disguise_known,
     p_disguise_conceals) = _subject_disguise_context(
        chat["id"], p_name, p_appearance_true, known)
    p_disguise_terms = _subject_concealed_terms(chat["id"], p_name)

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

    sources = [{"name": p_name, "room": p_room}]
    for _e in br_entries:
        sources.append({"name": _e.get("speaker"), "room": cast_room(sc, _e.get("speaker"), ctx.cast)})
    for c in ctx.cast:
        d = ctx.character_results.get(c["id"])
        sh = json.loads(c["sheet"])
        if d and (d.get("sequence") or d.get("speech") or d.get("action")):
            sources.append({"name": character_name(sh),
                            "room": character_room(sc, sh)})

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
    extra_entries = []
    for extra in ctx.extra_players:
        pid_key = str(extra["persona_id"])
        e_name = extra["name"]
        e_room = room_of(sc, e_name) or p_room
        sources.append({"name": e_name, "room": e_room})
        appearances[e_name] = _appearance_as_prose(appearance_of(
            e_name, extra.get("appearance") or f"{e_name}, a person of unremarkable appearance.", sc))
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
        "crowds": crowds_for_room(ctx.chat.id, sc, p_room),
        "couriers": couriers_for_room(ctx.chat.id, sc, p_room),
        "notices": artifacts_for_room(ctx.chat.id, sc, p_room),
        "visible_rooms": _visible_rooms_for(sc, p_name, p_room),
        "senses": senses_of(pers), "sense_card": _sense_card(pers),
        "attention": "engaged",
        "knows_identity": True,
        **_source_channels(sc, p_name, p_room, sources, prev_sc=prev_scene,
                           senses=_sense_card(pers)),
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
            "crowds": crowds_for_room(ctx.chat.id, sc, e_room),
            "couriers": couriers_for_room(ctx.chat.id, sc, e_room),
            "notices": artifacts_for_room(ctx.chat.id, sc, e_room),
            "visible_rooms": _visible_rooms_for(sc, e_name, e_room),
            "senses": senses_of(extra), "sense_card": _sense_card(extra),
            "attention": "engaged",
            "knows_identity": True,
            **_source_channels(sc, e_name, e_room, sources, prev_sc=prev_scene,
                               senses=_sense_card(extra)),
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
            "crowds": crowds_for_room(ctx.chat.id, sc, r),
            "couriers": couriers_for_room(ctx.chat.id, sc, r),
            "notices": artifacts_for_room(ctx.chat.id, sc, r),
            "visible_rooms": _visible_rooms_for(sc, character_name(sh), r),
            "senses": senses_of(sh), "sense_card": _sense_card(sh),
            "attention": act.get("goal") or "ambient",
            "knows_identity": p_name in (known.get(character_name(sh)) or []),
            **_source_channels(sc, character_name(sh), r, sources,
                               prev_sc=prev_scene, senses=_sense_card(sh)),
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

    return _composer_outcome(
        ctx, sc, prev_scene, diff, interp, res, known, p_name,
        p_appearance, p_disguise, p_disguise_known, p_disguise_conceals,
        p_disguise_terms, perceivers, appearances, sources, enriched_dlog,
        substance_events, amap)


# ---------------------------------------------------------------------------
# The composer path -- which is now the only path.
#
# Layer A/B live in agents/composer.py; this section is the orchestrator that
# assembles each stage's typed inputs and calls down into it. Zero model
# calls, and no view is BUILT from `resolved_event`: the Director's
# omniscient account of the beat reaches no percept, so the per-observer
# surgery that used to cut it down (redaction, surface translation) has
# nothing left to cut and went with the model path.
#
# It is read in exactly one place, and stating that precisely matters more
# than the tidier sentence: `_inverted_motion_check` compares the FINISHED
# view against the resolved event, as a tripwire. Nothing flows from the
# event into the view -- the comparison runs the other way, and its only
# output is a warning.
#
# The scrub chain does not run here as repair; the checkers run as TRIPWIRES
# (`_composer_tripwires`): a firing tripwire is a composer defect and says so
# in its warning. Audit history's lesson stands -- real leaks are guards that
# cannot fire -- so the guards are kept armed even though the composer makes
# their firing structurally impossible on every path it controls. What each
# tripwire may DO to the text differs, and is argued at that function: a
# repair that deletes entitled content is not defence in depth, it is the
# regression, and that was measured rather than supposed.
# ---------------------------------------------------------------------------

_LOOK_VERBS = frozenset({
    "look", "examine", "inspect", "survey", "study", "scan", "observe",
    "glance", "peer", "search", "check",
})


def _explicit_look_intent(interp):
    """Did the player explicitly look/examine this beat? Read from the
    Director's structured interpretation (location_query, or a declared
    action whose leading verb is a look verb), never from raw input. An
    explicit look re-renders the player's full standing state instead of the
    delta."""
    if not isinstance(interp, dict):
        return False
    if str(interp.get("location_query") or "").strip():
        return True
    for event in interp.get("sequence") or []:
        if not isinstance(event, dict) or event.get("type") != "action":
            continue
        text = str(event.get("attempt") or event.get("observable") or "")
        words = text.strip().split()
        verb = str(event.get("verb") or (words[0] if words else ""))
        verb = re.sub(r"[^\w]", "", verb).strip().casefold()
        if verb in _LOOK_VERBS or verb.rstrip("s") in _LOOK_VERBS:
            return True
    return False


def _composer_prev_ledger(ctx):
    """The per-observer composer ledger from the PREVIOUS turn's stored
    perception step -- what each observer's view already carried (standing
    dedupe keys) and which full appearance descriptions were already
    delivered (first-mention tracking). Same recovery pattern as
    `_previous_open_group_continuity`: read the stored step, never live
    state."""
    cache_key = "_composer_prev_ledger_cache"
    if cache_key in ctx:
        return ctx.get(cache_key) or {}
    ledger = {}
    if ctx.turn.idx > 0:
        previous = q(
            "SELECT id FROM turns WHERE chat_id=? AND idx=?",
            (ctx.chat.id, ctx.turn.idx - 1), one=True,
        )
        if previous:
            rows = q(
                "SELECT s.key, v.content FROM steps s JOIN variants v "
                "ON v.step_id=s.id AND v.active=1 "
                "WHERE s.turn_id=? AND s.key IN "
                "('perception_establish','perception_act','perception_outcome')",
                (previous["id"],),
            )
            by_key = {}
            for row in rows:
                try:
                    by_key[row["key"]] = json.loads(row["content"])
                except (TypeError, ValueError):
                    continue
            for key in ("perception_outcome", "perception_act",
                        "perception_establish"):
                candidate = (by_key.get(key) or {}).get("composer_ledger")
                if isinstance(candidate, dict):
                    ledger = candidate
                    break
    ctx[cache_key] = ledger
    return ledger


def _composer_prev_state(ledger, pid):
    entry = (ledger or {}).get(str(pid)) or {}
    return (frozenset(entry.get("standing") or []),
            frozenset(entry.get("described") or []))


def _composer_bare_details(rows):
    """[(observer-safe body label, place, detail)] from an already-gated
    `observer_body_regions` projection, via the same `_bare_body_details`
    parser the model-path fidelity floor uses. Covered zones never match, so
    this cannot turn a covered chest into anatomy."""
    out = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        label = str(row.get("body") or "someone").strip()
        for region, surface in (row.get("regions") or {}).items():
            for place, detail in _bare_body_details(region, surface):
                rendered = _self_body_detail(detail) if label == "you" else detail
                out.append((label, place, rendered))
    return out


def _composer_unknown_sources(name, known, roster):
    recognized = set(known.get(name) or [])
    return recognized, [
        s for s in roster
        if s["name"] != name and not _recognizes(s["name"], recognized)
    ]


def _joint_stranger_labels(bodies):
    """The label every body would get if nobody recognized anybody -- the
    superset of the epithets this beat can put into circulation.

    A per-observer display map deliberately leaves the observer OUT of its own
    map, so it can never say what the rest of the room is calling that
    observer. This assignment includes everyone, so `_composer_self_forms`
    below can hand a mind the widened or ordinal-distinguished form of its own
    epithet as well as the base one. It decides nothing about admission: it is
    only ever read to rewrite a body's own epithet into "you"."""
    return composer.assign_stranger_labels([
        (b.get("name"), b.get("appearance"), b.get("aliases") or [])
        for b in bodies or [] if b.get("name")
    ])


def _composer_self_forms(name, base_forms, body, joint_labels, display_map):
    """One observer's complete self-reference forms: their names, plus the
    epithets the engine minted FOR them (`common.self_reference_forms`).

    Engine-supplied prose reaches a view written in the third person about
    everyone in it, and `_self_second_person` turns the receiving mind's own
    handles into "you". It only ever knew names, so a beat that referred to a
    body by the descriptor OTHER minds use for it walked straight past --
    which is how a player read "the sword at the apprentice's hip" in his own
    view, about his own sword.

    `display_map` is what this observer calls everyone ELSE, and is passed as
    the collision guard: a form this observer is already using for another
    body is never claimed as self-reference."""
    forms = list(base_forms or [name])
    if not body:
        # No body record for this perceiver this beat (an observer in another
        # room, an extra player who is not in the roster). Minting an epithet
        # from nothing yields `_unknown_actor_label`'s universal fallback,
        # which every appearance-less body shares -- and a form shared with a
        # body outside this observer's display map is one the collision guard
        # below cannot see. Decline instead.
        return forms
    epithets = self_reference_forms(
        name,
        (body or {}).get("appearance"),
        (body or {}).get("aliases") or [],
        labels=[(joint_labels or {}).get(name)],
        avoid=list((display_map or {}).values()),
    )
    seen = {str(f).casefold() for f in forms}
    for form in epithets:
        if form.casefold() not in seen:
            seen.add(form.casefold())
            forms.append(form)
    return forms


def _composer_identity_space(ctx, p_name, p_appearance):
    """Every name this chat can leak -- not just the ones on stage tonight.

    `_identity_roster` is built from `ctx.cast`, and `active_cast` filters
    to `status='active'`. So a character who left the scene, went dormant or
    died is OFF the roster while their name stays written into room notes,
    authored overlays and ambient prose. The corpus replay measured the
    consequence: 69 surviving identity leaks in composed views, dominated by
    `room_notes` naming an off-roster character, with no tripwire coverage
    at all -- a player view carried a never-met character's name out of a
    room note and nothing warned, because the roster the tripwire checks
    against had never heard of her either.

    Recognition still decides. A name in here is scrubbed only for an
    observer who has not earned it; someone who knows Hinami keeps reading
    "Hinami", and someone who does not reads the fox-eared woman with six
    tails. The space is who COULD be leaked, not who must be hidden.

    Cached per turn: it is three cheap reads and it is asked for once per
    observer per stage.
    """
    cache_key = "_composer_identity_space_cache"
    cached = ctx.get(cache_key)
    if cached is not None:
        return cached
    space = _identity_roster(p_name, p_appearance, ctx.cast)
    seen = {str(s["name"]).casefold() for s in space if s.get("name")}
    rows = q(
        "SELECT COALESCE(cc.sheet, ch.sheet) AS sheet FROM chat_chars cc "
        "JOIN characters ch ON ch.id = cc.char_id WHERE cc.chat_id=?",
        (ctx.chat.id,),
    )
    for row in rows:
        try:
            sheet = json.loads(row["sheet"])
        except (TypeError, ValueError):
            continue
        name = character_name(sheet)
        if not name or name.casefold() in seen:
            continue
        seen.add(name.casefold())
        keys = character_scene_keys(sheet)
        space.append({"name": name,
                      "appearance": character_appearance(sheet),
                      "aliases": keys[1:]})
    for extra in (ctx.extra_players or []):
        name = str((extra or {}).get("name") or "").strip()
        if not name or name.casefold() in seen:
            continue
        seen.add(name.casefold())
        space.append({"name": name,
                      "appearance": (extra or {}).get("appearance") or "",
                      "aliases": []})
    for name, rec in (wget(ctx.chat.id, "background_presences", {}) or {}).items():
        name = str(name or "").strip()
        if not name or name.casefold() in seen:
            continue
        seen.add(name.casefold())
        sketch = (rec or {}).get("sketch") if isinstance(rec, dict) else {}
        space.append({
            "name": name,
            "appearance": str((sketch or {}).get("appearance") or ""),
            "aliases": [],
        })
    ctx[cache_key] = space
    return space


def _composer_extra_parts(ctx, p_name):
    """Authored structured body parts (tails, wings, horns) by display name.

    Card-read, so a cast with none yields {} and nothing downstream changes.
    The composer's body-region projection is the only consumer now that the
    model payload is gone: the feature reaches a mind through
    `observer_body_regions`, exactly the seam it always used.

    Cached per turn -- three orchestrators ask for it and it is a sheet read
    per cast member.
    """
    cached = ctx.get("_composer_extra_parts_cache")
    if cached is None:
        cached = scene_extra_parts(ctx.cast, persona_of(ctx.chat), p_name)
        # A DISGUISE HIDES THE PARTS TOO, and this is the only place that can
        # make it so. `disguised_visible_appearance` rewrites the appearance
        # SUMMARY; authored extra parts are a separate typed ledger the
        # composer renders straight from structured data, so a glamoured
        # kitsune kept six tails and two fox ears in every view while her
        # summary read "ordinary human ears" (reported live, chat 72).
        # Filtering at this seam rather than at the percept build keeps it
        # ahead of every consumer and out of reach of display-label
        # ambiguity -- these keys are true body names, the percept rows are
        # observer-facing labels and two bodies can share one.
        # TRUTH FIRST, THEN CONCEALMENT. A transformation changes what the
        # body IS -- its list replaces the card's outright, which is what
        # lets it ADD a part no card declares. A disguise then hides what
        # that body currently has. The order is the whole model: you can
        # glamour a transformed body, and the glamour hides the fox's tail
        # rather than the woman's.
        chat_id = ctx.chat["id"]
        shifted = active_transformations(chat_id)
        if shifted:
            cached = {
                name: transformed_parts(
                    parts, shifted.get(str(name or "").casefold()))
                for name, parts in (cached or {}).items()
            }
            # A body the card never gave parts to can be given them here.
            for key, form in shifted.items():
                if form.get("parts") and not any(
                        str(n).casefold() == key for n in cached):
                    cached[form.get("subject") or key] = form["parts"]
        cached = conceal_disguised_parts(cached, active_disguises(chat_id))
        ctx["_composer_extra_parts_cache"] = cached
    return cached


# DERIVED from the one definition of the wire format, never re-spelled.
# `common._VIEW_MASK` is what `_mask_quoted_spans` actually emits; this
# module used to carry a second spelling of the same token, so changing the
# mask in common.py would have silently disarmed the refusal check below --
# the check that stops a self-narration cut from taking a reader's delivered
# line with it. It would not have raised, it would have stopped matching.
# `.split` rather than a regex over the format string, so a format that stops
# having exactly one `%d` fails here and loudly.
_MASK_PREFIX, _MASK_SUFFIX = _VIEW_MASK.split("%d")
_MASK_TOKEN = re.compile(
    re.escape(_MASK_PREFIX) + r"\d+" + re.escape(_MASK_SUFFIX))


def _strip_self_narration_quote_safe(view, perceiver_name, other_names=()):
    """`_strip_self_narration` with a floor under delivered speech.

    The stripper splits on sentence punctuation, and sentence punctuation
    occurs INSIDE quoted lines. On the model path that was tolerable: the
    text it repaired was model prose, and losing a sentence of it lost
    paraphrase. On the composer path the same pass ran over a view whose
    quotes are entitled delivered lines reproduced verbatim from
    `dialogue_log` -- so it cut them mid-sentence. Measured over the corpus
    replay: 167 of 382 fires dropped text containing a quote character, and
    at least 16 cascaded into the invented-dialogue guard, which then failed
    to match the mangled quote against ground truth and deleted the whole
    line. That is the composer's ONLY recall regression (33 player-view
    lines lost against the model's 6), and it was self-inflicted.

    So: a drop that would take a quote with it is refused outright. The
    refusal is returned rather than swallowed, because a view knowingly
    delivered with self-narration still in it is a thing the caller should
    say out loud -- the same contract `_strip_self_narration`'s own two
    floors already use.

    QUOTED SPANS ARE MASKED BEFORE THE SPLIT, the same way
    `_dedupe_view_sentences` does it and for the same reason its comment
    records: a per-fragment "does this contain a quote character" test is
    defeated by the splitter itself, because the fragment it hands you is
    already cut. Masked, a delivered line is one opaque token that no
    splitter can enter, so the stripper decides about whole sentences
    again. Then any sentence still carrying a token is refused outright:
    the mask proves a delivered line is in there, and no framing error is
    worth a reader's line.

    Not a quote CHARACTER class -- this is prose full of possessives, and
    "Reya's voice carries down the hall" is exactly the authored
    self-narration the gate exists to remove.

    Returns (text, dropped, refused), all unmasked.
    """
    masked, spans = _mask_quoted_spans(str(view or ""))
    own_refusals = []
    stripped, dropped_masked = _strip_self_narration(
        masked, perceiver_name, other_names, refusals=own_refusals)
    dropped = [_unmask_quoted_spans(s, spans) for s in dropped_masked]
    if any(_MASK_TOKEN.search(s) for s in dropped_masked):
        return view, [], dropped
    if own_refusals:
        # The stripper's OWN two floors (would empty the view / would take
        # all the sight with it) also decline to cut, and a view knowingly
        # delivered with self-narration in it is the same reportable thing
        # whichever floor stopped the cut. They were silent by default.
        return view, [], [_unmask_quoted_spans(r, spans)
                          for r in own_refusals]
    return _unmask_quoted_spans(stripped, spans), dropped, []


def _composer_scrub_surface(text, name, recognized, unknown_sources):
    """Input-side identity floor for an act's observable surface: a Director
    or character-authored surface can embed a canonical name ("steps toward
    Hinami") the receiving observer has not earned. Applied at ADMISSION so
    the percept never carries it; the output tripwire then has nothing to
    fire on."""
    if not text or not unknown_sources:
        return text
    scrubbed, _ = _scrub_unknown_identities(
        text, allowed_forms=[name, *recognized],
        unknown_sources=unknown_sources)
    return scrubbed


def _composer_authored_prose(ctx, stage, text, name, recognized,
                             unknown_sources, *, roster_names=()):
    """The admission gate for AUTHORED prose: room notes, appearance and
    overlay descriptions, ambient events.

    These three surfaces are the ones nobody wrote for a particular mind.
    An author writes a room note once and it is served to everyone standing
    in the room; an overlay describes a body to whoever can see it. So they
    arrive carrying two things a view must not: another person's canonical
    name, and the perceiver themself in the third person.

    Both are subtractions and both happen HERE, before the percept exists,
    for the same reason the act-surface scrub does: a fact that never
    entered the IR cannot be rendered, cannot be re-derived into a
    structured observation, and cannot be minted into a memory. Repairing
    the rendered view instead is what the corpus replay caught destroying
    entitled speech.

    Returns (text, notes) -- notes are things the caller should warn about,
    not failures. A gate that fires is doing its job; a gate that REFUSES
    (quoted self-narration it will not cut) is the one worth reading.
    """
    text = str(text or "").strip()
    if not text:
        return text, []
    notes = []
    if unknown_sources:
        text, leaked = _scrub_unknown_identities(
            text, allowed_forms=[name, *recognized],
            unknown_sources=unknown_sources)
        if leaked:
            notes.append(
                f"{stage}: authored prose named {leaked} to {name}, who has "
                "no channel to that identity; replaced with descriptors at "
                "admission")
    text, _dropped, refused = _strip_self_narration_quote_safe(
        text, name, list(roster_names))
    if refused:
        notes.append(
            f"{stage}: authored prose narrates {name} in the third person "
            "inside a quoted line, so it was admitted as written rather "
            f"than cut: {refused[0][:120]!r}")
    return text, notes


def _composer_tripwires(ctx, stage, pid, name, view, known, roster,
                        spoken_lines=None):
    """The retired scrub passes, kept armed as tripwires over composed views.

    Firing means a COMPOSER DEFECT -- Layer A admitted something it should
    not have -- and the warning says so.

    WHAT EACH ONE IS ALLOWED TO DO TO THE TEXT differs, and the difference
    was paid for. "Defense in depth costs nothing when the guards never
    fire" is what this function used to say, and the corpus replay measured
    what it actually cost: the guards fired 382 times, 167 of those drops
    took a quote character with them, and the composer lost 33 entitled
    player-view lines where the model path lost 6. The repair, not the
    composer, was the only recall regression in the build.

    So the three are graded by what a wrong repair destroys:

    * IDENTITY still repairs. `_scrub_unknown_identities` SUBSTITUTES a
      descriptor for a name, outside quoted spans only -- it cannot delete
      a sentence and cannot touch a delivered line. And what it prevents is
      a firewall breach, which must never ship on the strength of a warning
      nobody reads.
    * SELF-NARRATION repairs only where it can prove it is safe: a drop
      that would take a quote with it is refused and reported instead
      (`_strip_self_narration_quote_safe`). A sentence with no quote in it
      carries no delivered line, so cutting it costs framing and nothing
      else.
    * INVENTED DIALOGUE no longer repairs at all. It deletes whole lines --
      the most destructive act available here -- and on this path it has no
      legitimate work: every quote in a composed view was built from
      `dialogue_log` by `speech_percept`, so a fire is either the cascade
      above or a gap in the ground truth it checks against. Both are bugs
      in the engine, and neither is fixed by deleting the reader's line.
    """
    if not view:
        return view
    recognized, unknown = _composer_unknown_sources(name, known, roster)
    if unknown:
        view, leaked = _scrub_unknown_identities(
            view, allowed_forms=[name, *recognized], unknown_sources=unknown)
        if leaked:
            ctx.warnings.append(
                f"{stage}: COMPOSER TRIPWIRE -- unearned identity {leaked} "
                f"reached the composed view of {name}; Layer A admitted a "
                "fact with no channel (engine defect)")
    stripped, self_narrated, refused = _strip_self_narration_quote_safe(
        view, name, [s["name"] for s in roster])
    if self_narrated:
        ctx.warnings.append(
            f"{stage}: COMPOSER TRIPWIRE -- composed view of {name} narrated "
            f"its own perceiver (engine defect): {self_narrated[0][:120]!r}")
        view = stripped
    if refused:
        ctx.warnings.append(
            f"{stage}: COMPOSER TRIPWIRE -- composed view of {name} narrates "
            "its own perceiver inside a delivered line; the line was kept "
            f"and the framing error stands (engine defect): "
            f"{refused[0][:120]!r}")
    if spoken_lines is not None:
        _checked, invented = _scrub_invented_dialogue(
            view, spoken_lines, cast_names=[s["name"] for s in roster])
        if invented:
            ctx.warnings.append(
                f"{stage}: COMPOSER TRIPWIRE -- dialogue in composed view "
                f"'{pid}' does not match the delivered-line ground truth "
                f"(engine defect, view delivered as composed): {invented}")
    return view


def _authored_prose_gate(ctx, stage, name, known, identity_space):
    """One observer's admission gate over authored prose, as a callable.

    Built once per observer per stage and handed down, so the percept
    builders stay decision-free: they take text that is already safe for
    this mind rather than learning who this mind is."""
    recognized, unknown = _composer_unknown_sources(
        name, known, identity_space)
    roster_names = [s["name"] for s in identity_space]

    def gate(text):
        gated, notes = _composer_authored_prose(
            ctx, stage, text, name, recognized, unknown,
            roster_names=roster_names)
        for note in notes:
            ctx.warnings.append(note)
        return gated

    return gate


def _gated_ambient_percepts(gate, sensory_events, room):
    """Authored ambient events, run through the observer's admission gate.

    Ambient prose is written for the scene, not for a mind: the establish
    stage's own authored events were measured narrating a perceiver's voice
    back at them, and naming characters to observers who had never met
    them. Gating the event text (not the rendered percept) keeps the
    dedupe key honest -- two observers who receive different gated text
    have genuinely received different things."""
    if gate is None:
        return composer.ambient_percepts(sensory_events, room)
    gated = []
    for event in sensory_events or []:
        if not isinstance(event, dict):
            continue
        desc = gate(str(event.get("desc") or event.get("description")
                        or event.get("text") or ""))
        if not desc:
            continue
        gated.append({**event, "desc": desc,
                      "description": desc, "text": desc})
    return composer.ambient_percepts(gated, room)


def _composer_standing_percepts(sc, p, name, others, display_map, known, *,
                                entity_state=None, appearance_changed=(),
                                gate=None, extra_parts=None):
    """The standing-state half of one observer's IR: environment, presence,
    first-mention/changed appearances, own body state, standing contact
    sensations, bare body regions. Every admission is a subtraction --
    unseen bodies, rear-arc bodies and covered regions simply never become
    percepts.

    `gate` is this observer's authored-prose gate (`_authored_prose_gate`).
    Room notes and appearance/overlay descriptions pass through it because
    nobody wrote either of them for a particular mind -- see
    `_composer_authored_prose`."""
    percepts = []
    room = p.get("room")
    room_notes = p.get("room_notes")
    if gate is not None:
        room_notes = gate(room_notes)
    env = composer.environment_percept(
        room, p.get("room_name"), room_notes,
        effective_light(sc, room) if room else "")
    if env:
        percepts.append(env)
    senses = p.get("sense_card")
    percepts.extend(composer.presence_percepts(
        sc, name, others, display_map, senses))
    percepts.extend(composer.pose_percepts(
        sc, name, others, display_map, senses))
    recognized = set(known.get(name) or [])
    for body in others:
        b_name = body.get("name")
        if not b_name:
            continue
        if composer._sense_graded(
                visual_level_between(sc, name, b_name),
                "sight", senses) != "full":
            continue
        if entity_arc(sc, name, b_name) == "rear":
            continue
        recog = not disguise_breaks_recognition(
            body.get("disguise_known_to"), name,
            body.get("disguise_conceals_identity")
        ) and _recognizes(b_name, recognized)
        changed = any(same_subject(sc, b_name, item)
                      for item in appearance_changed or ())
        if recog and not changed:
            # A familiar stable body's authored card is not a new percept.
            continue
        label = display_map.get(b_name) or (
            b_name if recog else "the unfamiliar person")
        if recog:
            description = body.get("appearance")
        else:
            description = _strip_identity_tokens(
                body.get("appearance"),
                [b_name, *(body.get("aliases") or [])])
        # `_strip_identity_tokens` removes only the described body's OWN
        # name. A scene overlay describing one body routinely names another
        # ("her arms still around Hinami"), and that third name walked
        # through -- 957 admissions the output tripwire then caught and
        # scrubbed after the fact. The gate catches it before the percept.
        if gate is not None:
            description = gate(description)
        if description:
            percepts.append(composer.appearance_percept(
                b_name, label, description, force=changed))
    if entity_state:
        state_percept = composer.body_state_percept(entity_state)
        if state_percept:
            percepts.append(state_percept)
    # The identity floor rides the sensation clause at its source: the OTHER
    # party is named through this observer's own display map — "you" is
    # impossible here (contact_sensation picks the non-observer party), a
    # recognized partner gets their name, a stranger the descriptor, and a
    # spelling the map cannot place falls to "someone" rather than leaking
    # the canonical name (the tripwire downstream remains the backstop).
    # Before this, the clause named the partner canonically and the tripwire
    # fired on every contact beat with an unrecognized partner (chat 70).
    _sensation_label = (lambda other:
                        display_map.get(str(other)) or "someone")
    percepts.extend(composer.contact_percepts([
        (contact, contact_sensation(contact, you=name, scene=sc,
                                    label_for=_sensation_label))
        for contact in _standing_contacts_for(sc, name)
    ]))
    region_labels = {name: "you"}
    for body in others:
        if body.get("name"):
            region_labels[body["name"]] = display_map.get(
                body["name"], "someone")
    rows = observer_body_regions(sc, name, region_labels,
                                 extra_parts=extra_parts)
    percepts.extend(
        composer.body_region_percepts(_composer_bare_details(rows)))
    # Authored extra parts ride the same gated projection as bare regions,
    # in a sibling key. Reading only `regions` -- which is what this did
    # when the two features merged -- landed the whole extra-parts feature
    # silently dead on the live path: gated correctly, rendered nowhere.
    percepts.extend(composer.body_part_percepts([
        (str(row.get("body") or "someone"), part)
        for row in rows or [] if isinstance(row, dict)
        for part in (row.get("part_data") or [])
    ]))
    return percepts


def _composer_company(others, display_map, percepts):
    """Which co-present bodies this observer's view was composed ABOUT, each
    under the label the observer earned -- the per-beat record the people
    projection (`story_view.player_view`'s `people`) reads back.

    Derived from the presence percepts themselves (their opaque `body` key)
    rather than by re-checking sight levels here, so this record structurally
    cannot admit a body the rendered view did not: both come from the same
    gated IR. `recognized` is `observer_display_map`'s own verdict -- a
    recognised body maps to its own name -- which is NOT the same question as
    "is the name in the identity ledger": a disguise that conceals identity
    makes a well-known name a stranger, and a reader that re-derived
    recognition from the ledger would undo the disguise.

    The canonical `name` rides this record because a step's content is
    engine-side, like the other viewers' views beside it; the projection is
    what withholds it from an unrecognising viewer.
    """
    admitted = {p.data.get("body") for p in percepts
                if p.kind == "presence" and p.data.get("body")}
    out = []
    for body in others or []:
        name = str(body.get("name") or "")
        if not name or composer.body_key(name) not in admitted:
            continue
        label = str(display_map.get(name) or "")
        if not label:
            continue
        out.append({"key": composer.body_key(name), "name": name,
                    "label": label, "recognized": label == name})
    return out


def _composer_finish_observer(ctx, stage, pid, name, rendered, known, roster,
                              clean_views, observations, ledger, *,
                              spoken_lines=None):
    view = _composer_tripwires(
        ctx, stage, pid, name, rendered.text, known, roster,
        spoken_lines=spoken_lines)
    clean_views[pid] = view or None
    observations[pid] = composer.observations_from_render(pid, rendered)
    ledger[pid] = {
        "standing": sorted(rendered.standing_keys),
        "described": sorted(rendered.described),
    }


def _composer_establish(ctx, sc, perceivers, known, p_name, p_appearance,
                        entity_states, sensory_events):
    chat_id = ctx.chat["id"]
    bodies = []
    p_visible, _, p_known_to, _ci = _subject_disguise_context(
        chat_id, p_name, p_appearance, known)
    bodies.append({
        "name": p_name, "room": room_of(sc, p_name),
        "appearance": p_visible, "aliases": [],
        "disguise_known_to": p_known_to,
        "disguise_conceals_identity": _ci,
    })
    for c in ctx.cast:
        sh, _, _ = sheet_state(c)
        b_name = character_name(sh)
        if not b_name:
            continue
        b_true = _appearance_as_prose(appearance_of(
            b_name, character_appearance(sh), sc))
        b_visible, _, b_known_to, _ci = _subject_disguise_context(
            chat_id, b_name, b_true, known)
        bodies.append({
            "name": b_name, "room": character_room(sc, sh),
            "appearance": b_visible,
            "aliases": character_scene_keys(sh)[1:],
            "disguise_known_to": b_known_to,
            "disguise_conceals_identity": _ci,
        })
    roster = _identity_roster(p_name, p_appearance, ctx.cast)
    identity_space = _composer_identity_space(ctx, p_name, p_appearance)
    cast_parts = _composer_extra_parts(ctx, p_name)
    clean_views, observations, ledger, company = {}, {}, {}, {}
    for p in perceivers:
        pid = str(p["id"])
        name = p["name"]
        if p.get("awareness") in NON_AWAKE_GATED:
            percepts = composer.residue_percepts(p["awareness"])
            company[pid] = []       # an unconscious observer sees nobody
        else:
            others = [b for b in bodies
                      if not _is_the_observer(sc, b["name"], name)]
            display_map = composer.observer_display_map(
                sc, name, others, known)
            gate = _authored_prose_gate(
                ctx, "perception_establish", name, known, identity_space)
            percepts = _composer_standing_percepts(
                sc, p, name, others, display_map, known,
                entity_state=p.get("entity_state")
                or (entity_states or {}).get(name),
                gate=gate, extra_parts=cast_parts)
            percepts.extend(
                _gated_ambient_percepts(gate, sensory_events, p.get("room")))
            company[pid] = _composer_company(others, display_map, percepts)
        # A scene opening is the one beat where everything is legitimately
        # new: full render for every mind, and the ledger starts here.
        rendered = composer.render_view(percepts, mode="character",
                                        full_render=True,
                                        language=ctx.language)
        _composer_finish_observer(
            ctx, "perception_establish", pid, name, rendered, known, roster,
            clean_views, observations, ledger)
    ctx["_composer_turn_ledger"] = ledger
    return {
        "views": clean_views,
        "observations": observations,
        "composer_ledger": ledger,
        "company": company,
    }


def _composer_act(ctx, sc, interp, perceivers, known, p_name, p_visible,
                  p_disguise_known, p_disguise_conceals, p_disguise_terms,
                  co_present, amap, speech_elems, action):
    onset_sequence = list(interp.get("sequence") or [])
    if speech_elems and not any(
            isinstance(e, dict) and e.get("type") == "speech"
            for e in onset_sequence):
        onset_sequence.extend(speech_elems)

    self_forms_by_name = {}
    for c in ctx.cast:
        sh = json.loads(c["sheet"])
        self_forms_by_name[character_name(sh)] = self_name_forms(
            character_name(sh), character_scene_keys(sh))

    onset_targets = {str(t).casefold()
                     for t in ((action or {}).get("targets") or [])}
    onset_loud = any(str(e.get("volume", "")).lower() in ("loud", "shout")
                     for e in speech_elems)
    spoken = player_speech_lines(interp)
    roster = _identity_roster(p_name, p_visible, ctx.cast)
    identity_space = _composer_identity_space(ctx, p_name, p_visible)
    cast_parts = _composer_extra_parts(ctx, p_name)
    prev_ledger = _composer_prev_ledger(ctx)
    actor_body = {
        "name": p_name, "room": ctx.get("_player_room"),
        "appearance": p_visible, "aliases": [],
        "disguise_known_to": p_disguise_known,
        "disguise_conceals_identity": p_disguise_conceals,
    }
    all_bodies = [b for b in co_present if b.get("name") != p_name]
    all_bodies.append(actor_body)
    bodies_by_name = {b["name"]: b for b in all_bodies if b.get("name")}
    joint_labels = _joint_stranger_labels(all_bodies)
    clean_views, observations, ledger, company = {}, {}, {}, {}
    for p in perceivers:
        pid = str(p["id"])
        name = p["name"]
        prev_standing, prev_described = _composer_prev_state(prev_ledger, pid)
        if p.get("awareness") in NON_AWAKE_GATED:
            name_cf = name.casefold()
            cause = (amap.get(name_cf) or {}).get("cause", "").lower()
            pain = any(w in cause for w in
                       ("injur", "wound", "blood", "hurt", "struck",
                        "broke", "burn"))
            percepts = composer.residue_percepts(
                p["awareness"], targeted=(name_cf in onset_targets),
                loud_event=onset_loud, pain=pain)
            company[pid] = []       # an unconscious observer sees nobody
        else:
            others = [b for b in co_present
                      if not _is_the_observer(sc, b["name"], name)]
            others.append(actor_body)
            display_map = composer.observer_display_map(
                sc, name, others, known)
            percepts = _composer_standing_percepts(
                sc, p, name, others, display_map, known,
                entity_state=p.get("entity_state")
                or _own_body_state(sc, name),
                gate=_authored_prose_gate(
                    ctx, "perception_act", name, known, identity_space),
                extra_parts=cast_parts)
            self_forms = _composer_self_forms(
                name, self_forms_by_name.get(name),
                bodies_by_name.get(name), joint_labels, display_map)
            rel = p.get("spatial_to_actor") or {}
            vis = p.get("visual_channel_to_actor", False)
            can_see = _in_plain_view(rel, vis)
            display = display_map.get(p_name, p_name)
            recognized, unknown = _composer_unknown_sources(
                name, known, roster)
            continuity = bool(rel.get("open_group_continuity"))
            for idx, event in enumerate(onset_sequence):
                if not isinstance(event, dict):
                    continue
                if event.get("type") == "speech":
                    speech_rel = rel if continuity else {
                        **rel, "open_group_continuity": False}
                    speech_rel = _with_comm_channel(
                        sc, speech_rel, speaker=p_name, observer=name,
                        observer_room=p.get("room"))
                    entry = {
                        "speaker": p_name,
                        "text": event.get("text"),
                        "volume": event.get("volume", "normal"),
                        "tone": event.get("tone", ""),
                        "visibility": event.get("visibility", "overt"),
                        "conceal_from": event.get("conceal_from") or [],
                    }
                    percept = composer.speech_percept(
                        entry, speech_rel, name, display=display,
                        can_see=can_see,
                        proximity=p.get("proximity_to_actor"),
                        order_key=idx, observer_id=pid,
                        senses=p.get("sense_card"))
                    if percept:
                        percepts.append(percept)
                elif event.get("type") == "action":
                    if _declares_rapid_movement([event]):
                        # Speech before the run stays audible; speech after
                        # gets no continuity floor.
                        continuity = False
                    surface = _composer_scrub_surface(
                        observable_action_text(event), name, recognized,
                        unknown)
                    percept = composer.act_percept(
                        sc, event, name, p_name, rel, display=display,
                        can_see=can_see,
                        self_forms=self_forms,
                        order_key=idx, observer_id=pid, surface=surface)
                    if percept:
                        percepts.append(percept)
            company[pid] = _composer_company(others, display_map, percepts)
        rendered = composer.render_view(
            percepts, mode="character", prev_standing=prev_standing,
            prev_described=prev_described, language=ctx.language)
        _composer_finish_observer(
            ctx, "perception_act", pid, name, rendered, known, roster,
            clean_views, observations, ledger, spoken_lines=spoken)
    merged = dict(prev_ledger)
    merged.update(ledger)
    ctx["_composer_turn_ledger"] = merged
    _disguise_leak_check(ctx, "perception_act", clean_views, perceivers,
                         p_name, p_disguise_terms, p_disguise_known)
    return {
        "views": clean_views,
        "observations": observations,
        "composer_ledger": merged,
        "company": company,
    }


def _own_body_state(sc, name):
    """This observer's own posture, activity and held items, from the scene.

    `body_state_percept` is interoception -- channel "interoception", source
    label "you" -- and it could only ever fire from
    `director_establish.entity_states`, which exists on the opening turn and
    nowhere else. So a mind knew what was in its own hands on turn 0 and
    never again, in an engine whose composer header says exactly why that
    costs something: "a character agent is a stateless LLM call; if it is not
    in context, the mind does not have it".

    The durable home for the same three facts is the scene entity's `state`,
    which `_PROTECTED_STATE_KEYS` already reserves as structural for
    "perception's own deterministic backstop". Posture is the one of the
    three with a second and better home -- `scene.poses`, which
    `pose_percepts` renders with the sight grade and always delivers for the
    observer themselves -- so it is read from here only when the pose ledger
    is silent, rather than said twice.
    """
    state = (_entity_named(sc, name) or {}).get("state")
    if not isinstance(state, dict):
        return {}
    out = {}
    activity = str(state.get("activity") or "").strip()
    if activity:
        out["activity"] = activity
    held = [str(item).strip() for item in (state.get("held_items") or [])
            if str(item or "").strip()]
    if held:
        out["held_items"] = held
    posture = str(state.get("posture") or "").strip()
    if posture and not any(
            same_subject(sc, key, name)
            and str((value or {}).get("posture") or "").strip()
            for key, value in ((sc.get("poses") or {}).items()
                               if isinstance(sc.get("poses"), dict) else ())):
        out["posture"] = posture
    return out


def _is_the_observer(sc, candidate, observer, observer_aliases=()):
    """Is `candidate` another spelling of the observer's own name.

    AGENTS.md: one being, one name -- and a being routinely carries several
    at once. `character_scene_keys` names the cast half and says why readers
    must try all of them: "the director sometimes keys by identity.uid (or an
    alias)". `same_subject` covers the scene half, an entity id and its
    aliases. A bare `==` between two of those spellings is False, and this
    module already learned that lesson five times.

    Asked in the direction that matters: everything in a view is suppressed
    for the one person it is about, so a miss here does not leak -- it hands
    an observer their own line and their own act as somebody else's.
    """
    if same_subject(sc, candidate, observer):
        return True
    cand = str(candidate or "").strip().casefold()
    if not cand:
        return False
    return any(str(alias or "").strip().casefold() == cand
               for alias in observer_aliases or ())


def _mover_is_a_body(sc, mover):
    """Does this `positions` key name somebody, or something.

    A crossing percept says "a figure" about whatever it is handed, and
    `state_diff.positions` is not a roster of people -- AGENTS.md's
    body-enclosure row: it "legitimately keys objects and unregistered
    presences by entity id" beside cast bodies keyed by display name. So a
    crate carried from one room to the next arrived in every view at either
    end as a person walking in.

    The engine already answers this question once, in
    `commit_background._is_inert_presence_candidate` -- an inert `kind`, or
    portable and neither animate-kinded nor wearing anything -- and it is
    conservative in the direction this needs. It calls something a thing
    only when that is demonstrable, so an undressed unregistered presence
    stays a body, and a mover with no entity record at all (every cast
    member) is a body without being asked.
    """
    from persist.commit import _is_inert_presence_candidate
    entity = _entity_named(sc, mover)
    if not entity:
        return True
    return not _is_inert_presence_candidate(sc, mover, entity)


def _composer_outcome(ctx, sc, prev_scene, diff, interp, res, known, p_name,
                      p_appearance, p_disguise, p_disguise_known,
                      p_disguise_conceals, p_disguise_terms, perceivers,
                      appearances, sources, enriched_dlog, substance_events,
                      amap):
    chat = ctx.chat
    chat_id = chat["id"]
    pers = persona_of(chat)

    cast_aliases = {}
    for c in ctx.cast:
        sh = json.loads(c["sheet"])
        cast_aliases[character_name(sh)] = character_scene_keys(sh)[1:]
    self_forms_by_name = {
        nm: self_name_forms(nm, [nm, *(cast_aliases.get(nm) or [])])
        for nm in appearances
    }
    self_forms_by_name[p_name] = self_name_forms(
        p_name, [p_name, *((pers.get("identity") or {}).get("aliases") or [])])

    # Terminal overt act per actor -- the same last-overt rule as the model
    # path's deterministic backstop, for the same reason (no per-stage
    # room/barrier snapshot exists to gate earlier sub-actions honestly).
    last_overt_by_actor = {}
    for e in (interp.get("sequence") or []):
        if e.get("type") == "action" and e.get("visibility") != "concealed":
            surface = observable_action_text(e)
            if surface:
                last_overt_by_actor[p_name] = {
                    "actor": p_name, "attempt": surface, "event": e}
    for c in ctx.cast:
        d = ctx.character_results.get(c["id"])
        sh = json.loads(c["sheet"])
        cname = character_name(sh)
        for e in ((d or {}).get("sequence") or []):
            if e.get("type") == "action" and e.get("visibility") != "concealed":
                surface = observable_action_text(e)
                if surface:
                    last_overt_by_actor[cname] = {
                        "actor": cname, "attempt": surface, "event": e}

    # The complete set of lines actually spoken this beat (the invented-
    # dialogue tripwire's ground truth).
    spoken_lines = list(player_speech_lines(interp))
    spoken_lines += [d.get("exact_quote") for d in enriched_dlog]
    for rmap in (ctx.character_results, ctx.reaction_results):
        for d in (rmap or {}).values():
            if not isinstance(d, dict):
                continue
            for e in (d.get("sequence") or []):
                if e.get("type") == "speech" and e.get("text"):
                    spoken_lines.append(e["text"])
            if d.get("speech"):
                spoken_lines.append(d["speech"])
    for entry in (interp.get("other_players") or {}).values():
        for e in ((entry or {}).get("sequence") or []):
            if e.get("type") == "speech" and e.get("text"):
                spoken_lines.append(e["text"])

    # Co-present bodies with disguise-adjusted VISIBLE appearance.
    bodies = []
    for nm, app in appearances.items():
        if nm == p_name:
            visible, known_to = p_appearance, p_disguise_known
            conceals = p_disguise_conceals
        else:
            visible, _, known_to, conceals = _subject_disguise_context(
                chat_id, nm, app, known)
        bodies.append({
            "name": nm, "room": cast_room(sc, nm, ctx.cast),
            "appearance": visible,
            "aliases": cast_aliases.get(nm) or [],
            "disguise_known_to": known_to,
            # Both halves, always. `conceals` was computed here and dropped on
            # the same line, and an ABSENT flag reads as "does not conceal" --
            # so every identity-concealing disguise stopped working between
            # the act view and this one.
            "disguise_conceals_identity": conceals,
        })
    bodies_by_name = {b["name"]: b for b in bodies if b.get("name")}
    joint_labels = _joint_stranger_labels(bodies)

    # Visible-form structural changes this beat re-earn a full description.
    appearance_changed = set()
    for field in ("attire", "overlays", "scales"):
        appearance_changed.update(str(key) for key in (diff.get(field) or {}))
    for key, entity in (diff.get("entities") or {}).items():
        if isinstance(entity, dict) and any(
                f in entity for f in ("description", "appearance")):
            appearance_changed.add(str(key))
            if entity.get("name"):
                appearance_changed.add(str(entity["name"]))
    if p_disguise:
        appearance_changed.add(p_name)

    ident_roster = [
        {"name": nm, "appearance": ap, "aliases": cast_aliases.get(nm) or []}
        for nm, ap in appearances.items()
    ]
    for s in sources:
        if s.get("name") and all(r["name"] != s["name"] for r in ident_roster):
            ident_roster.append(
                {"name": s["name"], "appearance": None, "aliases": []})

    # The stage roster is who ACTED this beat; the identity space is who
    # this chat could name. Authored prose is gated against the second.
    cast_parts = _composer_extra_parts(ctx, p_name)
    identity_space = list(ident_roster)
    _space_seen = {str(r["name"]).casefold() for r in identity_space}
    for s in _composer_identity_space(ctx, p_name, appearances.get(p_name)):
        if str(s.get("name") or "").casefold() not in _space_seen:
            _space_seen.add(str(s["name"]).casefold())
            identity_space.append(s)

    # Movement this beat, for crossing percepts.
    moves = []
    for mover, new_room in ((diff.get("positions") or {}).items()
                            if isinstance(diff, dict) else ()):
        prev_room = room_of(prev_scene, str(mover))
        if not new_room or prev_room == str(new_room):
            continue
        if not _mover_is_a_body(sc, str(mover)):
            continue
        moves.append((str(mover), prev_room, str(new_room)))

    # Micro-round deliveries were gated by `_delivery_ok` when the loop ran;
    # they arrive pre-rendered and are appended after the composed view.
    # (Residual: the micro loop should emit percepts -- noted in
    # design_notes/13-composer-build.md.)
    micro_by_pid = {}
    for round_data in (ctx.interaction_loop or {}).get("rounds") or []:
        for perceiver_id, additions in (
                round_data.get("delivered_views") or {}).items():
            key = str(perceiver_id)
            if key == "player":
                continue
            micro_by_pid.setdefault(key, []).append(additions)

    base_ledger = dict(_composer_prev_ledger(ctx))
    base_ledger.update(ctx.get("_composer_turn_ledger") or {})
    full_player_render = _explicit_look_intent(interp)
    _ubiq = _ubiquitous_names(sc)

    clean_views, observations, ledger, company = {}, {}, {}, {}
    episodes, episode_meta = {}, {}
    for p in perceivers:
        pid = str(p["id"])
        name = p["name"]
        is_player_view = pid == "player" or pid.startswith("extra:")
        prev_standing, prev_described = _composer_prev_state(base_ledger, pid)
        if p.get("awareness") in NON_AWAKE_GATED:
            name_cf = name.casefold()
            loud_event = any(
                str(d.get("volume", "")).lower() in ("loud", "shout")
                for d in enriched_dlog)
            targeted = any(
                str(d.get("intended_target") or "").casefold() == name_cf
                for d in enriched_dlog)
            cause = (amap.get(name_cf) or {}).get("cause", "").lower()
            pain = any(w in cause for w in
                       ("injur", "wound", "blood", "hurt", "struck",
                        "broke", "burn"))
            percepts = composer.residue_percepts(
                p["awareness"], targeted=targeted, loud_event=loud_event,
                pain=pain)
            company[pid] = []       # an unconscious observer sees nobody
        else:
            others = [b for b in bodies
                      if not _is_the_observer(sc, b["name"], name)]
            display_map = composer.observer_display_map(
                sc, name, others, known)
            percepts = _composer_standing_percepts(
                sc, p, name, others, display_map, known,
                entity_state=p.get("entity_state")
                or _own_body_state(sc, name),
                appearance_changed=appearance_changed,
                gate=_authored_prose_gate(
                    ctx, "perception_outcome", name, known, identity_space),
                extra_parts=cast_parts)
            self_forms = _composer_self_forms(
                name, self_forms_by_name.get(name),
                bodies_by_name.get(name), joint_labels, display_map)
            spatial = p.get("spatial_to_sources") or {}
            visual = p.get("visual_channel_to_sources") or {}
            recognized, unknown = _composer_unknown_sources(
                name, known, ident_roster)
            behind = set(p.get("behind_sources") or [])
            order = 0
            for d in enriched_dlog:
                speaker = d.get("speaker", "?")
                if _is_the_observer(
                        sc, speaker, name, cast_aliases.get(name)) or (
                        pid == "player"
                        and is_player_speaker(speaker, chat)):
                    order += 1
                    continue
                rel = spatial.get(speaker)
                if rel is None:
                    if str(speaker).strip().casefold() in _ubiq:
                        rel = {"same_room": True, "barrier": "open",
                               "distance": "near",
                               "note": "bodiless voice, present throughout"}
                    else:
                        sp_room = d.get("speaker_room") or room_of(sc, speaker)
                        rel = spatial_rel_between(
                            sc, name, speaker,
                            observer_room=p.get("room"),
                            target_room=sp_room)
                can_see = _in_plain_view(rel, visual.get(speaker, False))
                if _recognizes(speaker, recognized):
                    display = speaker
                elif can_see:
                    display = display_map.get(speaker) or _unknown_actor_label(
                        speaker,
                        _strip_identity_tokens(
                            appearances.get(speaker),
                            [speaker, *(cast_aliases.get(speaker) or [])]))
                else:
                    display = "a voice"
                percept = composer.speech_percept(
                    d, _with_comm_channel(
                        sc, rel, speaker=speaker, observer=name,
                        observer_room=p.get("room"),
                        speaker_room=d.get("speaker_room")),
                    name, display=display, can_see=can_see,
                    proximity=measured_proximity_rel(sc, name, speaker),
                    order_key=order, observer_id=pid,
                    senses=p.get("sense_card"))
                if percept:
                    percepts.append(percept)
                order += 1
            for act in last_overt_by_actor.values():
                actor = act["actor"]
                if _is_the_observer(
                        sc, actor, name, cast_aliases.get(name)) \
                        or actor in behind:
                    continue
                rel = spatial.get(actor)
                if rel is None:
                    continue
                can_see = _in_plain_view(rel, visual.get(actor, False))
                if not can_see:
                    continue
                if _recognizes(actor, recognized):
                    display = actor
                else:
                    display = display_map.get(actor) or _unknown_actor_label(
                        actor,
                        _strip_identity_tokens(
                            appearances.get(actor),
                            [actor, *(cast_aliases.get(actor) or [])]))
                surface = _composer_scrub_surface(
                    act["attempt"], name, recognized, unknown)
                percept = composer.act_percept(
                    sc, act.get("event") or {}, name, actor, rel,
                    display=display, can_see=True,
                    self_forms=self_forms,
                    order_key=order, observer_id=pid, surface=surface)
                if percept:
                    percepts.append(percept)
                order += 1
            for mover, from_room, to_room in moves:
                if same_subject(sc, mover, name):
                    continue
                if p.get("room") not in (from_room, to_room):
                    continue
                _graded = (lambda scene: composer._sense_graded(
                    visual_level_between(scene, name, mover),
                    "sight", p.get("sense_card")))
                seen = _graded(sc) != "none" or (
                    prev_scene and _graded(prev_scene) != "none")
                if not seen:
                    continue
                label = display_map.get(mover)
                if label is None:
                    label = mover if _recognizes(mover, recognized) \
                        else "a figure"
                direction = ("arrived" if to_room == p.get("room")
                             else "left")
                percepts.append(composer.crossing_percept(
                    mover, label, direction, order_key=order))
                order += 1
            for event in substance_events or []:
                if not isinstance(event, dict) or event.get("op") != "add":
                    continue
                percept = composer.substance_percept(
                    event, substance_event_clause(event, you=name, scene=sc),
                    order_key=order)
                if percept:
                    percepts.append(percept)
                    order += 1
            company[pid] = _composer_company(others, display_map, percepts)
        rendered = composer.render_view(
            percepts,
            mode="player" if is_player_view else "character",
            prev_standing=prev_standing, prev_described=prev_described,
            full_render=is_player_view and full_player_render,
            language=ctx.language)
        _composer_finish_observer(
            ctx, "perception_outcome", pid, name, rendered, known,
            ident_roster, clean_views, observations, ledger,
            spoken_lines=spoken_lines)
        for additions in micro_by_pid.get(pid) or []:
            current = clean_views.get(pid) or ""
            appended = _dedupe_view_sentences(
                _append_micro_view(current, additions))
            if appended != current:
                clean_views[pid] = appended
                observations[pid] = list(observations.get(pid) or []) + [
                    composer.compact_observation({
                        "observation_id":
                            f"current:{pid}:{len(observations.get(pid) or [])}",
                        "perceiver_id": pid,
                        "source_atom_id": "current",
                        "channel": "mixed",
                        "fidelity": "rendered",
                        "observed": {"text": str(additions)},
                        "intensity": 0.5,
                        "suddenness": 0.2,
                        "ambiguity": 0.3,
                        "directed_at_self": False,
                    })]
        if not is_player_view:
            content, gist, entities = composer.render_episode(
                percepts, prev_standing=prev_standing,
                prev_described=prev_described, language=ctx.language)
            episodes[pid] = content
            episode_meta[pid] = {"gist": gist, "entities": entities}
    merged = dict(base_ledger)
    merged.update(ledger)
    ctx["_composer_turn_ledger"] = merged
    _disguise_leak_check(ctx, "perception_outcome", clean_views, perceivers,
                         p_name, p_disguise_terms, p_disguise_known)
    _inverted_motion_check(ctx, "perception_outcome", clean_views,
                           res.get("resolved_event"))
    return {
        "views": clean_views,
        "observations": observations,
        "episodes": episodes,
        "episode_meta": episode_meta,
        "composer_ledger": merged,
        "company": company,
    }
