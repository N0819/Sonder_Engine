"""Player-facing narration agent."""

from __future__ import annotations

import contextvars
import json
from concurrent.futures import ThreadPoolExecutor

from core.db import get_setting, q, wget, wset
from language_runtime import (
    LanguagePackError, compositor_text, compositor_value,
    english_linguistic, installed_language_packs, linguistic)
from llm.prompts import get_prompt, prompt_fragment
from story import attire as attire_model
from story.scene import (
    NON_AWAKE_GATED,
    apply_awareness_diff,
    awareness_map,
    awareness_of,
    narration_tense,
    persona_of,
    get_scene,
)
import os
import re

from world.spatial import (
    containment_conceals,
    room_display_name,
    contact_sensation,
    effective_light,
    entity_arc,
    has_visual,
    hiding_holders_of,
    room_of,
    room_of_record,
    same_subject,
    spatial_digest,
    spatial_rel,
    substances_for,
    contact_action_clause,
    contact_actions_for_observer,
    contact_endpoint_is_body,
    contact_thing_label,
    visible_adjacent_rooms,
    visual_level_between,
)
from world.weather import weather_for_room, weather_words


def _ling(name):
    return linguistic("agents.narration", name)


def _event_line(key, **values):
    """One `current_events` line, in the STORY's language.

    These markers were English f-string literals in this module until
    2026-08-23, which made the highest-leverage instruction in the whole
    payload -- the per-line act/speech marker, measured to take placeholder
    dialogue from 14 to 0 where the same rule stated in the sheet's prose
    changed nothing -- reach a Japanese story in English, inside an
    otherwise Japanese sheet. A marker is only worth its measured power
    while the model can read it.

    They live in `linguistics.json` beside the warning prefixes rather than
    in the compositor card, because nothing here is reader-exposed: the
    compositor renders the PAGE, and this renders a prompt.
    """
    return str(_ling("_EVENT_LINES")[key]).format(**values)

# English compatibility view for tests/tooling; live checks use `_ling(...)`.
_ENFORCEABLE_PREFIXES = english_linguistic(
    "agents.narration", "_ENFORCEABLE_PREFIXES")

from llm.schemas import validate_llm_output

from story.character_schema import (
    character_appearance,
    character_identity_from_text,
    character_name,
    persona_appearance,
    persona_voice_setting,
)

from . import composer
from .common import (
    _agent_json,
    extra_parts_lines,
    scene_extra_parts,
    _already_established_phrases,
    _cap_repeated_quotes,
    attire_exposure_facts,
    compact_attire,
    exposure_owner_refs,
    _overused_phrases,
    _check_narrator_fidelity,
    _dedupe_view_sentences,
    _narration_person_counts,
    _narration_tense_counts,
    _TENSE_DRIFT_RATIO,
    _TENSE_MIN_EVIDENCE,
    _protected_view_quotes,
    _dialogue_tokens,
    _quote_body,
    _recognizes,
    _self_second_person,
    self_name_forms,
    self_reference_forms,
    _strip_identity_tokens,
    _strip_player_echo,
    _unknown_actor_label,
    cast_room,
    character_scene_keys,
    adjudicated_player_action_text,
    communication_surface,
    observable_action_text,
    observable_action_onset_text,
    player_room_in,
    player_speech_lines,
    resolve_action_referents,
    sequence_event_allowed,
)

def _authored_narration_person(voice_setting, scenario, player_name,
                               player_pronouns):
    """The person the AUTHOR asked for, or None. Two sources, in order.

    THE BEAT WITH NOTHING TO DETECT FROM IS THE OPENING ONE, and it is the
    worst place in the story to guess. `narration_person` is inferred from
    how the player wrote their turn, and turn 0 has no player turn: with
    `raw_input` empty the counts are all zero, nothing is stored, and the
    resolver returned the literal "second". Measured (quiet, 2026-09-05,
    PQ9): `second` on turn 0 and `third` on all twenty turns after it, so a
    reader met the switch in the first two paragraphs -- while the persona
    card said, in as many words, "close third person, restrained, exact
    about small things", and nothing read it.

    1. The persona's own `narration.voice_setting`, read for the ENGINE'S OWN
       three words. This is not a matcher hunting a meaning in free prose:
       `first`/`second`/`third person` is the vocabulary this very field
       names, in the pack's own spelling, and a guide that says two of them
       has said nothing this can act on -- so an ambiguous guide declines.
    2. The scenario prose, scored by the same detector the player's own turn
       is scored by. An opening written as "You stand at the gate" and one
       written as "Mireille stands at the gate" are the author answering the
       question in the only other place they were asked it.

    Neither is recorded. The evidence does not change between beats, so a
    later turn with nothing to detect re-derives the same answer; the moment
    the player's own writing carries a signal, detection takes over and
    writes, exactly as before.
    """
    matched = [person for person, pattern in
               (_ling("_VOICE_PERSON_RES") or {}).items()
               if pattern.search(str(voice_setting or ""))]
    if len(matched) == 1:
        return matched[0]
    counts = _narration_person_counts(
        str(scenario or ""), player_name, player_pronouns)
    best = max(counts, key=counts.get)
    runner = max((v for k, v in counts.items() if k != best), default=0)
    return best if (counts[best] > 0 and counts[best] > runner) else None


def _resolve_narration_person(chat_id, raw_input, player_name, player_pronouns,
                              key="narration_person", pending=None,
                              voice_setting="", scenario=""):
    """Which grammatical person renders the player character this turn.
    Detection is per-turn (a player can switch style mid-campaign), but a
    turn with no clear signal -- pure dialogue with no narrative frame, e.g.
    just a quoted line -- falls back to whatever was last established rather
    than snapping back to a default and creating whiplash mid-scene.

    Once a person is established, flipping it requires a DECISIVE signal (the
    winner leading the runner-up by >= 2), not just a bare majority. This is
    the hysteresis that stops a single stray token -- one unquoted "you"
    addressed to an NPC, one sentence-initial name that doubles as a verb --
    from silently switching the whole campaign's narration voice, which is
    exactly the flakiness heuristic person-detection is prone to. `key` lets
    additional human players each keep their own established convention.

    `pending`: when a dict is supplied, the newly established/overridden
    person is RECORDED there ({key: person}) instead of written durably --
    the narrator stages stash it on their returned step content so that
    commit.py (the sole persistence boundary) applies the wset at commit
    time; model-era output stays provisional until then. Without `pending`
    the write happens immediately (direct/legacy callers).
    """
    def _record(value):
        if pending is None:
            wset(chat_id, key, value)
        else:
            pending[key] = value

    counts = _narration_person_counts(raw_input, player_name, player_pronouns)
    best = max(counts, key=counts.get)
    top = counts[best]
    runner = max((v for k, v in counts.items() if k != best), default=0)
    detected = best if (top > 0 and top > runner) else None
    stored = wget(chat_id, key, None)

    if detected is None:
        # An ESTABLISHED convention still wins: the author's guide seeds the
        # beat that has nothing, it does not override what the player has
        # since been writing. See `_authored_narration_person`.
        return stored or _authored_narration_person(
            voice_setting, scenario, player_name, player_pronouns) or "second"
    if stored is None or detected == stored:
        if detected != stored:
            _record(detected)
        return detected
    # Established, and this turn disagrees. The lead used to be measured
    # against the RUNNER-UP, which is the wrong opponent: it asked whether the
    # winner beat some third person nobody was arguing for, rather than whether
    # it beat the person actually stored. A turn reading {first: 0, second: 1}
    # against a stored `first` is unanimous disagreement, not a stray token,
    # and it scored a lead of 1 and changed nothing. Measured on the story that
    # reported this: 17 of 49 turns could not correct a wrong `first`.
    #
    # Compare against the incumbent. The lead of 2 is KEPT: dropping it for
    # "the stored person scored nothing this turn" was tried and is wrong,
    # because a single misparsed token looks exactly like unanimity. "Mark the
    # map, then rest" scores one third-person hit off the player's own name
    # used as a verb, with nothing on the other side -- indistinguishable by
    # counts from a genuine one-token switch, and flipping a whole campaign on
    # it is the failure this rule exists to prevent.
    #
    # Measured over 2212 live player turns: comparing against the incumbent
    # rather than the runner-up costs no extra mid-story changes at all, and
    # dropping the lead entirely costs two.
    stored_support = counts.get(stored, 0)
    if top - stored_support >= 2:
        _record(detected)
        return detected
    return stored


def _resolve_narration_tense(chat_id, recent_prose=()):
    """Which tense this beat is written in: the AUTHOR's dial, else the
    story's own.

    The dial is authoritative and unchanged -- `narration_tense` is read per
    turn so an edit lands on the next beat. What is new is the fallback. An
    unset story used to send NO tense at all, on the reasoning that an
    author who expressed no opinion should not be given one; the measured
    consequence (solitude, 2026-09-05, PS20) is that the narrator wrote
    seventeen beats in the present, turn 18 in the past ("No answer
    came... swallowed... She stood") and turn 19 in the present again, and
    the drift check had nothing to score against so it did not even report
    it. Silence is not neutrality when a whole-draft property is being
    chosen fresh every beat.

    So: an author who said nothing gets the tense the STORY has been in,
    read off its own recent narration by the same detector and the same two
    numbers the drift check uses -- one question ("is this page past or
    present") asked of two texts, so a story cannot be told one thing and
    scored by another. Below the evidence floor, or without a clear lead,
    this still returns "" and the payload still carries no tense: a story
    with nothing written yet (the opening beat, every time) is exactly the
    case that has no established tense to inherit.

    Nothing is written back. The evidence is the story's own prose, so the
    answer is recomputed from the page rather than remembered off it, and
    an author who turns the dial mid-story overrides it immediately.
    """
    authored = narration_tense(chat_id)
    if authored:
        return authored
    counts = {"past": 0, "present": 0}
    for prose in recent_prose or ():
        one = _narration_tense_counts(str(prose or ""))
        counts["past"] += one["past"]
        counts["present"] += one["present"]
    if counts["past"] + counts["present"] < _TENSE_MIN_EVIDENCE:
        return ""
    lead = "past" if counts["past"] >= counts["present"] else "present"
    other = "present" if lead == "past" else "past"
    if counts[lead] < counts[other] * _TENSE_DRIFT_RATIO:
        return ""
    return lead

# WHAT THIS LIST IS NOW (E13): a partition of the fidelity warnings, and
# nothing more. It named the findings that bought an automatic second narrator
# call -- dropped or altered dialogue, an ABSOLUTE-tier violation -- while
# content-reuse and missing-proper-noun findings stayed out of it because
# their false positives were not worth a doubled stage. The correction pass
# that spent the call was removed 2026-09-06: narration blocks on being
# parseable JSON and on nothing else, every check reports, and the only live
# reader of the list is `tools/narrator_sheet_bench.py`, which uses it to
# score arms.

# Deterministic craft screen. The pack's `_CRAFT_TELLS` table is the AUTHORITY
# on which phrasings are tells; the PROSE CRAFT sheet states the class (a
# phrasing that would sit unchanged in any other scene) and illustrates it,
# and its illustrations are not this table. Review 2026-09-07 B29 measured the
# drift the other way round: until that day narrator.txt carried two
# enumerations ("Banned: deliberate, unhurried, casually, pointedly, slow and
# steady" and "BANNED AI TELLS: shifts her weight; eyes flick; ...") that were
# a strict SUBSET of what is screened here -- the table also held
# 'deliberately'/'unhurriedly', the sensor-ledger 'registers' diction and
# 'continuous while' -- so a draft could obey the sheet word for word and
# still be flagged. When a new tell is caught, widen the TABLE; never re-sync
# the sheet into an enumeration (CLAUDE.md: no word lists in prompts). A draft
# containing any is REPORTED, one warning per tell, and published as written
# -- the rewrite this screen used to buy was removed 2026-09-06 for the reason
# `narrator` states at the removal site (E13). Conservative -- only clear
# tells, to avoid false positives on ordinary prose. Dialogue is exempt
# (quotes are fixed); we scan the whole draft but the patterns don't match
# normal speech.


def _craft_tells(prose: str) -> list:
    """Banned AI tells present in a narrator draft (deduped, ordered). Quoted
    dialogue is masked before scanning -- quotes are fixed (reproduced verbatim),
    so a tell inside a spoken line is not the narrator's prose and could never be
    rewritten away, which would burn a pointless retry every turn."""
    if not prose:
        return []
    # Mask curly-quoted dialogue too -- models routinely emit it, and every
    # other dialogue regex in the pipeline (agents/common.py) accepts it; a
    # tell inside curly quotes would otherwise burn unwinnable retries.
    scan = re.sub(r'"[^"]*"|“[^“”]*”', " ", prose)
    found = []
    for pat, label in _ling("_CRAFT_TELLS"):
        if re.search(pat, scan, re.I):
            found.append(label)
    return list(dict.fromkeys(found))

def _authored_body_parts(ctx, persona, player_name):
    """{name: part lines} for every present body that AUTHORED extra parts.

    The same fact as `_cast_pronouns`, and the same failure it was built
    for: guessing flipped a character's pronouns across beats, and guessing
    here gave a body a part it does not have. Measured live -- the narration
    handed Elyra the player's six fox tails; her card declares no extra
    parts at all, so there was nothing in the narrator's payload that could
    have said otherwise. Perception and the Director have carried this index
    all along; only the stage that writes the prose was without it.

    Read live from the cards, like every other user of scene_extra_parts,
    and ABSENT when nobody declared any -- so an ordinary cast leaves the
    payload shape, and the provider's prefix cache, unchanged.
    """
    try:
        parts = scene_extra_parts(ctx.cast, persona, player_name)
    except Exception:
        return {}
    return {name: extra_parts_lines(p) for name, p in (parts or {}).items()
            if p}


def _cast_pronouns(cast, label=None):
    """Authoritative pronouns per cast member, so the narrator renders each
    named character in third person with their GIVEN pronouns instead of
    guessing from the name (which flipped Vorne he/she across beats). W6.
    Also the reference the deterministic pronoun-fidelity check scores against
    (agents/common.py's _check_pronoun_fidelity).

    KEYED BY WHAT THE VIEW CALLED THE BODY, never by the identity behind it.
    A body the player's view LABELS rather than NAMES has no name in the
    prose, and this map was the last narrator field still filed under the
    canonical name -- so every beat handed the page a roster of the real
    names of the strangers standing in the room. It is a door rather than a
    push: measured (masque, 2026-09-05, PX2) the same payload produced
    "Near the wall, Mattin Ruel stood flat-footed in his black steward's
    coat" on turn 1 and "an unfamiliar voice carried from the reception
    room" on turn 4, three beats before the player heard the name said
    aloud. The firewall does not depend on which way the model goes.

    `label` is the observer's own identity floor (`_speaker_display`, the
    same one `present_scene`, `co_present_positions` and `event_order` are
    built with), so there is one answer to "what may this page call that
    body" rather than a second one that can drift. Two bodies the view
    cannot tell apart collapse to one label; the entry is DROPPED rather
    than resolved to either, and the narrator card already says a character
    absent from `cast_pronouns` keeps whatever the view established.
    """
    out, collided = {}, set()
    for row in (cast or []):
        try:
            # The one identity reader, never the stored blob (review
            # 2026-09-07 B12): read raw, a card whose pronouns the shape repair
            # had to lift back into `identity` contributed nothing here, and
            # the page then referred to that body however the view had guessed.
            ident = character_identity_from_text(row["sheet"])
        except Exception:
            continue
        name = str(ident.get("name") or "").strip()
        pronouns = ident.get("pronouns") or {}
        clean = {k: pronouns[k] for k in ("subject", "object", "possessive")
                 if isinstance(pronouns, dict) and pronouns.get(k)}
        if not (name and clean):
            continue
        key = str(label(name) if label else name).strip() or name
        if key in out and out[key] != clean:
            collided.add(key)
        out[key] = clean
    for key in collided:
        out.pop(key, None)
    return out


def _speaker_display(name, recognized, appearance=None, aliases=None):
    """How the narrator payload refers to one speaker: the canonical name when
    the player recognizes them (rank/title variants included -- same
    _recognizes rule perception used to build the view), else the same
    appearance-derived anonymous label perception injects, so the binding
    never leaks an identity past the view's own gate."""
    if _recognizes(name, recognized):
        return name
    stripped = _strip_identity_tokens(appearance, [name, *(aliases or [])]) \
        or None
    return _unknown_actor_label(name, stripped, aliases)


def _standing_substance_clauses(scene, you):
    """Standing substances involving `you`, as cause-blind touch clauses.

    Mirrors `spatial.substance_event_clause`'s epistemic envelope exactly, so
    a standing re-delivery can never exceed what the onset beat delivered:
    the recipient side never names the source (an internal target knows the
    matter reached them, not who caused it), and the source side never names
    the destination (releasing is felt at your own body, where it landed is
    sight's problem). `detail` is model prose delivered once at onset and is
    deliberately not re-delivered -- every admission here subtracts.

    These are standing physical facts. Model silence cannot evaporate matter;
    removal, transfer, cleanup, or a world-specific process must change the
    ledger explicitly. Player-facing delta suppression prevents unchanged
    clauses from being repeated every beat.
    """
    clauses = []
    for record in substances_for(scene, you):
        substance = " ".join(str(record.get("substance") or "").split())[:160]
        if not substance:
            continue
        amount = " ".join(str(record.get("amount") or "").split())[:80]
        material = f"{amount} of {substance}" if amount else substance
        placement = str(record.get("placement") or "").strip().casefold()
        if same_subject(scene, record.get("target"), you):
            if placement == "interior":
                interior = " ".join(
                    str(record.get("target_interior") or "").split())[:160]
                clauses.append(
                    f"your {interior or 'interior'} still holds {material}")
            elif placement == "surface":
                part = " ".join(
                    str(record.get("target_part") or "").split())[:120]
                clauses.append(f"{material} on your {part or 'skin'}")
            else:
                clauses.append(f"{material} within what you contain")
        elif same_subject(scene, record.get("source"), you):
            part = " ".join(str(record.get("source_part") or "").split())[:120]
            clauses.append(f"{material} released from your {part or 'body'}")
    return clauses


#: Payload order for the manifest -- DERIVED from `composer.CHANNELS` minus
#: `mixed`, which appears only when a merged span actually crossed channels
#: (absent-when-empty, like the key itself).
#:
#: It was a hand-written literal under a comment that said "the fixed
#: vocabulary of composer.CHANNELS": two lists of one thing, agreeing today.
#: A seventh channel added to the composer would be built into percepts,
#: survive `observations_from_render`, arrive in `by_channel` -- and be
#: dropped from the narrator payload by the loop below, silently, because the
#: loop iterates this tuple. Derived, the same addition surfaces as a missing
#: `statuses` entry, which the loop states rather than swallows.
_MANIFEST_CHANNELS = tuple(c for c in composer.CHANNELS if c != "mixed")


def _player_standing_verdicts(ctx):
    """The player's own composer ledger verdicts, or {} (B28).

    A NAMED READ BECAUSE IT IS ONE HALF OF A JOIN. The other half is
    `perception._composer_finish_observer`, which files the key -- and the
    two are bound by nothing but four matching string literals
    (`perception_outcome`, `composer_ledger`, `player`, `verdicts`). Inline in
    `narrator`, either side could be renamed and every test still pass while
    the manifest quietly went back to shipping standing facts as news, which
    is exactly the "passing tests and a wrong page" this class hides behind.
    Named, `tests/test_standing_verdict_one_ledger.py` can compare the two.

    Read from the STORED perception_outcome step rather than turn state, so a
    narrator rerun sees the verdicts the first run did. Absent reads as "not
    computed" -- see `_sensory_channels_manifest` -- never as `unchanged`.
    """
    outcome = ctx.get("perception_outcome", {}) or {}
    ledger = outcome.get("composer_ledger") or {}
    return (ledger.get("player") or {}).get("verdicts") or {}


def _sensory_channels_manifest(scene, player_name, view, observations,
                               recognized, cast_info, p_room,
                               standing_verdicts=None):
    """Per-sense delivery manifest for the narrator payload, or {}.

    THE DEFECT: percepts carry a real channel from every builder through
    `composer.observations_from_render`, and the tag was discarded one stage
    before the prose -- the narrator payload was a single blob, so a model
    obeying SCENE CRAFT's compression could not see that an entire sense went
    silent, and the composer's delta dedupe means beat two of a standing
    contact delivers no touch at all. Measured over 600 stored perception
    steps: sight 1089 spans against touch 94 and delivered smell ~0 after the
    opening turn.

    EVERY ENTRY IS A RE-DELIVERY, NEVER A WIDENING -- the firewall is a gap
    and guards subtract:
      * this-beat spans are admitted only when byte-contained in the player's
        own scrubbed view, so this second representation structurally cannot
        exceed the first (the same invariant `observations_from_render`
        keeps, re-checked here because observations are projected from the
        render BEFORE the tripwire scrub);
      * standing contacts: the player is a party (first-hand by definition),
        and the other party passes the same recognition floor the view used
        (`_speaker_display`), falling to "someone" for a spelling the floor
        cannot place;
      * standing substances: cause-blind both directions (see
        `_standing_substance_clauses`);
      * weather is exposure-gated by `weather_for_room` itself, per channel;
      * a player sealed inside an enclosure gets no manifest at all -- the
        room's air, light and weather are not theirs, and perception already
        owns that view.

    A STANDING FACT IS NOT NEWS TWICE, AND ONE LEDGER SAYS SO. `standing`
    entries are `{clause, verdict}`, where the verdict is this observer's own
    composer ledger's (`composer.STANDING_VERDICTS`, shipped by
    `perception_outcome`) and is ABSENT where that ledger has no answer --
    weather, light, a substance, or a chat stored before the field existed --
    which reads as "not computed", never as "new". Without it this manifest
    was the second representation of a fact the view had already settled and
    the two disagreed on every beat after the first: `render_view` suppresses
    a standing contact this observer's ledger already carried, while this
    function re-derived the same contact from the scene and shipped its full
    sensation sentence again (B28). Measured chat 117: a hand that never left
    a belt, re-delivered on 40 of 70 beats under a template that ends
    "continuous while the contact holds" -- the engine saying the fact is
    unchanged in the breath it re-delivers it. Nothing is dropped, because a
    standing fact the narrator must not contradict is still a fact: what
    changes is that an `unchanged` one now arrives labelled as one, which is
    what the sheet's AMBIENT RESTRAINT has always been asking about and never
    had an answer to.
    """
    if not isinstance(scene, dict) or not p_room:
        return {}
    if hiding_holders_of(scene, player_name):
        return {}

    view_text = str(view or "")
    by_channel = {}
    for obs in observations or []:
        if not isinstance(obs, dict):
            continue
        text = str(((obs.get("observed") or {}).get("text")) or "").strip()
        if not text or text not in view_text:
            continue
        channel = str(obs.get("channel") or "mixed")
        by_channel.setdefault(channel, []).append(text)

    def _partner_label(other):
        other = str(other)
        info = (cast_info or {}).get(other)
        if info is not None:
            return _speaker_display(other, recognized,
                                    info.get("appearance"),
                                    info.get("aliases"))
        if _recognizes(other, recognized or ()):
            return other
        # A CONTACT PARTY IS NOT NECESSARILY A BODY, and "someone" asserts one.
        # THE THIRD SITE of one floor: perception fixed two and this one --
        # the floor that actually feeds the narrator -- stayed person-shaped,
        # which is how the measured case reached the page. Chat 98 turn 22: a
        # combadge resting on the player's own uniform was rendered as a body
        # pressed continuously against her, with three absent people's scents
        # attached to it. The scene is asked to vouch, and answers only
        # affirmatively in both directions, so silence yields the thing-word
        # rather than a person.
        return (contact_thing_label(scene, other)
                or ("someone" if contact_endpoint_is_body(scene, other)
                    else "something"))

    verdicts = {str(k): str(v) for k, v in (standing_verdicts or {}).items()}

    def _entry(clause, key=None):
        """One standing entry: the clause, plus the ledger's verdict on it
        when the ledger has one. `key` is the composer's own dedupe key, so
        the join between the two representations is the composer's, not a
        second spelling of it here."""
        out = {"clause": clause}
        verdict = verdicts.get(key or "")
        if verdict:
            out["verdict"] = verdict
        return out

    touch_standing = []
    # Built through the composer's OWN percept builders rather than by
    # collecting clauses: they mint the dedupe key the observer's ledger is
    # filed under, and a key spelled a second time here is the disagreement
    # this entry shape exists to end.
    contact_percepts = composer.contact_percepts([
        (contact, contact_sensation(contact, you=player_name, scene=scene,
                                    label_for=_partner_label))
        for contact in (scene.get("contacts") or [])
        if isinstance(contact, dict)
    ])
    contact_percepts.extend(composer.contact_action_percepts([
        (record, contact_action_clause(
            record, observer=player_name, scene=scene,
            label_for=_partner_label))
        for record in contact_actions_for_observer(scene, player_name)
    ]))
    for percept in contact_percepts:
        touch_standing.append(
            _entry(percept.data["clause"], percept.dedupe_key))
    # A standing substance has no composer percept and therefore no ledger
    # key: it ships with no verdict, which says "not computed" rather than
    # "new". Give it one the day perception files one.
    touch_standing.extend(
        _entry(clause)
        for clause in _standing_substance_clauses(scene, player_name))

    try:
        scoped = weather_for_room(scene, p_room) or {}
    except Exception:
        scoped = {}
    hearing_standing = [_entry(word) for word in weather_words(scoped, "sound")]
    if scoped.get("falls_on_you"):
        touch_standing.append(_entry(
            "%s %s falling on you"
            % (scoped["intensity"], scoped["precipitation"])))
    if scoped.get("wind_reaches"):
        touch_standing.append(_entry("%s on your skin" % scoped["wind"]))

    # THE STATUS DECIDES, AND IT IS DECIDED FIRST. This was built the other way
    # round: `sight_standing` was filled from the weather and then
    # unconditionally appended with `light: {light}`, so the sight entry's
    # standing list was never empty -- and `sight_status` was computed ten
    # lines later, where it can come back "silent". `weather_words`' sight arm
    # gates on room EXPOSURE (sky_visible / falls_on_you / wind_reaches),
    # never on light, so an exposed room at night handed the narrator
    # {"status": "silent", "why": "no light reaches this room",
    #  "standing": ["storm sky", "heavy rain", "light: dark"]}
    # -- bare strings, the shape standing entries had before B28 gave each
    # one the ledger's verdict; the defect is the contradiction, not the row.
    #
    # Not a firewall breach -- the weather is legitimately the player's, and
    # they can hear it and feel it on the other two channels. But the payload
    # contradicted itself in the one field the prompt's SENSORY CHANNELS block
    # is told to read as authoritative, and a reader resolves that either way
    # they like.
    light = effective_light(scene, p_room)
    if light == "dark":
        # Content wins over aperture: a filling light source or a percept
        # that legitimately rode sight this beat means SOMETHING is seen.
        sight_status = ("degraded", "almost no light reaches this room") \
            if by_channel.get("sight") else \
            ("silent", "no light reaches this room")
    elif light == "dim":
        sight_status = ("degraded", "dim light -- shapes, not detail")
    else:
        sight_status = ("live", "")

    # Silent means nothing is standing on this channel. The reason the player
    # cannot see is already in `why`, so `light: dark` beside it would be the
    # same fact a second time and the only copy shaped like content.
    sight_standing = [] if sight_status[0] == "silent" else [
        _entry(word)
        for word in (*weather_words(scoped, "sight"), f"light: {light}")]

    touch_live = bool(touch_standing or by_channel.get("touch"))
    statuses = {
        "sight": sight_status,
        "hearing": ("live", ""),
        "touch": ("live", "") if touch_live else
                 ("silent", "nothing is in contact with your body this beat"),
        "smell": ("live", "open air; nothing ledgered rides this channel"
                  if not by_channel.get("smell") else ""),
        "interoception": ("live", "your own body, always"),
    }
    standing = {
        "sight": sight_standing,
        "hearing": hearing_standing,
        "touch": touch_standing,
    }
    manifest = {}
    for channel in _MANIFEST_CHANNELS:
        # A channel the composer can mint and this function has no delivery
        # rule for is a gap, and it says so. Dropping it -- which is what a
        # hand-written vocabulary did by omission -- would tell the narrator
        # the sense is absent, which is a stronger claim than "not computed".
        status, why = statuses.get(
            channel, ("unknown", "no delivery status is computed for this "
                                 "channel yet"))
        entry = {"status": status}
        if why:
            entry["why"] = why
        if by_channel.get(channel):
            entry["this_beat"] = by_channel[channel]
        if standing.get(channel):
            entry["standing"] = standing[channel]
        manifest[channel] = entry
    if by_channel.get("mixed"):
        manifest["mixed"] = {"status": "live",
                             "this_beat": by_channel["mixed"]}
    return manifest


def _presence_room_of(ctx, scene, name, reaction=None):
    """Where a background presence stood for the beat it just acted in, or
    None when nothing can place it.

    Three sources, most specific first: the room the background stage
    resolved and recorded on the reaction itself, the canonical resolver over
    the stored record, and nothing. The stage's own answer comes first
    because it is the room the presence was GATED and voiced at -- asking a
    second time invites the two to disagree, which is the defect
    `presence_room` was written to end.

    `presence_room` rather than `room_of`: it knows the sketch's station room
    as well as the entity table, which is what answers for a presence the
    scene places nowhere and for one whose name two entities answer to.
    """
    room = str((reaction or {}).get("room") or "").strip()
    if room:
        return room
    # Local import: `persist.commit` reaches back into `agents.common` from
    # inside its own functions, and this is a cold path -- the same shape
    # `agents/perception.py` uses for `presence_has_an_identity`.
    from persist.commit import presence_record_for, presence_room
    records = wget(ctx.chat["id"], "background_presences", {}) or {}
    record = presence_record_for(records, name, scene)[1] or {}
    return presence_room(scene, name, record) or None


def _ordered_beat_events(ctx, p_name, view, recognized, cast_info,
                         scene=None, p_room=None, player_forms=()):
    """F1/F4: the pipeline's own numbered causal record of this beat, built
    from step order + the loop call sequences (stimulus -> response pairs):
    player declaration first, then reaction rounds, then interaction rounds in
    call order, then parallel character declarations, then background
    reactions. Info-barrier: an NPC line enters ONLY if its quote actually
    reached the player's view, and an NPC ACT only if it is overt and the
    player can perceive its actor; speakers render under the same display
    (name or anonymous label) the view used."""
    raw = []
    player_deferred = []
    # Action referents are canonical identities at interpret time.  Event
    # order is player-facing, so resolve them through the same recognition
    # floor used for the actor label rather than leaking a name inside the
    # action surface while anonymising its speaker one field away.
    referent_labels = {str(p_name): "you"}
    for canonical, info in (cast_info or {}).items():
        display = _speaker_display(
            canonical, recognized, info.get("appearance"),
            info.get("aliases"))
        referent_labels[str(canonical)] = display
        for alias in info.get("aliases") or []:
            referent_labels[str(alias)] = display
    di = ctx.get("director_interpret") or {}
    for e in (di.get("sequence") or []):
        if not isinstance(e, dict):
            continue
        if not sequence_event_allowed(e, ctx.get("director_resolve") or {}):
            continue
        destination = player_deferred if (
            e.get("depends_on") or str(e.get("phase") or "").casefold()
            in ("continuation", "completion")) else raw
        if e.get("type") == "speech" and e.get("text"):
            destination.append((p_name, "speech", e["text"]))
        elif e.get("type") == "communication":
            surface = communication_surface(e)
            if surface:
                destination.append((p_name, "communication", surface))
        elif e.get("type") == "action":
            surface = adjudicated_player_action_text(
                e, ctx.get("director_resolve") or {})
            if surface:
                destination.append((p_name, "action",
                                    resolve_action_referents(
                                        surface, e, referent_labels)))

    seen_cache = {}

    def _player_perceives(name, room=None, strict=False):
        """Can the player place this actor's overt physical act this beat.

        The same gate `co_present_positions` already uses. An act is listed by
        its Director-authored `observable` surface -- the intent-free
        bystander view -- so listing one hands the narrator no more than the
        position payload it already holds for that character. Fails CLOSED
        (no scene, no player room, actor unseen): a thin beat is a worse page,
        a leaked act is a broken firewall.

        `room` names where this body stands when the caller already knows and
        `room_of` does not -- a background presence is placed under a scene
        entity id, and that lookup comes back empty when the scene places it
        nowhere or when two entities answer to its name (chat 78's cell holds
        two identically-named guards). `strict` refuses an unplaceable body
        outright instead of taking `_player_sees_character`'s room-level
        fallback, which resolves an unknown room to the player's OWN and
        therefore answers "visible" for anybody it cannot place. That fallback
        exists for a cast member whose room is stored under an alias --
        over-denial there drops a plainly co-present character out of the page
        -- and it is the wrong default for a body the engine cannot place at
        all.
        """
        if not name or not scene or not p_room:
            return False
        key = (name, room, strict)
        if key not in seen_cache:
            now = room or room_of(scene, name)
            seen_cache[key] = False if (now is None and strict) else \
                _player_sees_character(scene, p_name, p_room, name, now)
        return seen_cache[key]

    def _seq_events(name, seq):
        """Every outward element of one character's declared sequence, in the
        order they declared it.

        Speech was always collected here; an ACT was not, which left the
        record the narrator is told is "what actually happened this beat"
        speech-only for everyone except the player. A beat's one physical
        event -- a character moving the player's own body -- therefore reached
        the narrator as a single clause buried mid-paragraph in the view,
        competing with the room's furniture and carrying an `ambiguous`
        fidelity, and nothing anywhere required it to survive onto the page.
        Measured over three rerolls of the same turn, it did not survive any
        of them. Acts are rendered, not quoted, so they are listed for ORDER
        and COVERAGE and never for verbatim reproduction.
        """
        perceives = None
        for e in seq or []:
            if not isinstance(e, dict):
                continue
            if e.get("type") == "speech" and e.get("text"):
                raw.append((name, "speech", e["text"]))
            elif e.get("type") == "communication":
                surface = communication_surface(e)
                if surface:
                    raw.append((name, "communication", surface))
            elif e.get("type") == "action":
                if str(e.get("visibility") or "overt").strip().lower() \
                        != "overt":
                    continue          # concealed: the player was not shown it
                surface = observable_action_text(e)
                if not surface:
                    continue          # purely mental beat, no outward surface
                if perceives is None:
                    perceives = _player_perceives(name)
                if perceives:
                    raw.append((name, "action",
                                resolve_action_referents(
                                    surface, e, referent_labels)))

    covered = set()
    for r in (ctx.reaction_loop or {}).get("rounds") or []:
        _seq_events(r.get("reactor"), (r.get("result") or {}).get("sequence"))
        try:
            covered.add(int(r.get("reactor_id")))
        except (TypeError, ValueError):
            pass
    for r in (ctx.interaction_loop or {}).get("rounds") or []:
        _seq_events(r.get("speaker"), (r.get("result") or {}).get("sequence"))
        try:
            covered.add(int(r.get("speaker_id")))
        except (TypeError, ValueError):
            pass
    for c in ctx.cast:
        try:
            cid = int(c["id"])
        except (TypeError, ValueError):
            continue
        if cid in covered:
            continue
        d = ctx.character_results.get(c["id"]) \
            or ctx.character_results.get(cid)
        if not isinstance(d, dict):
            continue
        name = d.get("name")
        _seq_events(name, d.get("sequence"))
        if not (d.get("sequence")) and d.get("speech"):
            raw.append((name, "speech", d["speech"]))
    raw.extend(player_deferred)
    br = ctx.get("background_react") or {}
    reactions = br.get("reactions")
    if reactions is None:
        reactions = ([br] if br.get("fired") and br.get("dialogue_log_entry")
                     else [])
    for r in reactions:
        entry = (r or {}).get("dialogue_log_entry") or {}
        speaker = entry.get("speaker") or (r or {}).get("name")
        if entry.get("exact_quote") and entry.get("speaker"):
            raw.append((entry["speaker"], "speech", entry["exact_quote"]))
        # A background presence's ACT was collected nowhere. Its shape differs
        # from a character's declared sequence -- one prose string on the
        # reaction, no `observable`/`visibility` pair -- so the `_seq_events`
        # path above cannot see it, and the beat's one physical event from an
        # unregistered presence (a gun-stick holding its aim on the player's
        # chest) reached the narrator only inside the omniscient resolved_event
        # prose. background.py authors the act as the outward surface already;
        # the perceptibility gate is the same one the cast path uses.
        act = str((r or {}).get("action") or "").strip()
        if act and speaker and _player_perceives(
                speaker, room=_presence_room_of(ctx, scene, speaker, r),
                strict=True):
            raw.append((speaker, "action", act))

    view_norm = re.sub(r"\s+", " ", str(view or "")).casefold()
    events = []
    for name, kind, text in raw:
        if not name:
            continue
        if kind in ("speech", "communication") and name != p_name:
            body = re.sub(r"\s+", " ", _quote_body(text)).casefold()
            if not body or body not in view_norm:
                continue  # the player never received this line
        info = cast_info.get(name) or {}
        display = name if name == p_name else _speaker_display(
            name, recognized, info.get("appearance"), info.get("aliases"))
        ev = {"n": len(events) + 1, "actor": display, "kind": kind}
        if kind == "speech":
            if name == p_name:
                # A player line carries its WORDS as well as the causal fact
                # that it was spoken, and `declared` marks whose it is.
                #
                # It used to carry `declared` alone. That redaction was aimed
                # at a real defect -- with the quote in both `player_declared`
                # and here, the model paraphrased a requested fee ("meals and
                # a bed") as an offer BY the player to provide those things --
                # but it cost more than it bought, because a line with no
                # content is a line the narrator cannot place. Measured in
                # chat 84, turns 2581 and 2582: the PA's answer rendered
                # BEFORE the question it answers, twice, and both player lines
                # came out as the vague placeholder the sheet explicitly
                # forbids ("your mutter slips out", "another mutter follows").
                #
                # Restoring the words costs no information: `player_speech_lines`
                # already puts these exact strings in the payload every turn as
                # the tail of `past_narration`, which is the page the player
                # has just read. What was missing was never the text, only
                # its POSITION among the beat's other events. Reproduction is
                # still forbidden -- by the sheet, and deterministically by
                # `_strip_player_echo` -- and nothing requires an event_order
                # quote to reach the page: DIALOGUE FIDELITY is scored off the
                # VIEW, which never carries a mind's own speech back to it.
                ev["declared"] = True
                ev["quote"] = text
            else:
                ev["quote"] = text
        else:
            # The same identity floor the composer puts under the player's
            # view, applied to the second copy of this beat's prose that
            # reaches the player. An act's `observable` surface is written in
            # the third person by whoever declared it, and it names the player
            # the way THAT mind refers to them -- by name, or by the epithet
            # the engine minted for a mind that has not recognized them
            # ("eyes settling on the sword at the apprentice's hip", observed
            # live). This is not narrator compensation: event_order is a
            # delivery of engine-written prose to the player, so it carries
            # the delivery floor rather than inheriting one.
            ev["action"] = _self_second_person(text, player_forms) \
                if player_forms else text
        events.append(ev)
    return events


def _player_sees_character(scene, p_name, p_room, name, now_room):
    """S3-A4: can the player actually SEE this co-present character this beat.

    Co-location is not perception. A character standing in the player's
    pitch-dark room, sealed inside a closed container, or in the player's rear
    blind spot is not seen, and the audit's case was exactly that: an entrant
    into the player's pitch-dark room arriving in the narrator payload as an
    enforced fact.

    Body-level (`visual_level_between`) whenever BOTH bodies are literally in
    `scene.positions`, so a carried light counts: standing in a lamp's pool in
    an otherwise dark room IS seen. When either is not (the player's room came
    from `ctx['_player_room']`, or the character is stored under a uid/alias
    key `cast_room` resolved) fall back to the room-level answer rather than
    denying outright -- over-denial here would drop a plainly visible
    co-present character out of ordinary narration, which is the failure mode
    this gate must not create.
    """
    if not name or not p_room:
        return False
    if containment_conceals(scene, p_name, name):
        return False
    # None = no facing/bearing basis, which fails open per entity_arc's own
    # contract; only a positive 'rear' is a blind spot.
    if entity_arc(scene, p_name, name) == "rear":
        return False
    if room_of(scene, p_name) and room_of(scene, name):
        return visual_level_between(scene, p_name, name) != "none"
    return has_visual(spatial_rel(scene, p_room, now_room or p_room))


def _position_delta_payload(ctx, chat, p_name, p_room, recognized, cast_info):
    """F2: each co-present cast member's position delta this beat
    (prev committed room -> this beat's room, plus a moved flag). Returns
    (payload_view, check_facts, room_display_names). Scoped to characters the
    player can place: co-present now AND actually perceptible (see
    `_player_sees_character`)."""
    prev_sc = get_scene(chat["id"], chat)
    sc = ctx.get("outcome_scene") or prev_sc
    rooms = sc.get("rooms") or {}
    room_names = {
        rid: room_display_name(r, rid)
        for rid, r in rooms.items() if isinstance(r, dict) or r is None
    }
    payload, facts = {}, []
    for name, info in cast_info.items():
        prev_room = cast_room(prev_sc, name, ctx.cast)
        now_room = cast_room(sc, name, ctx.cast)
        if not now_room:
            continue
        # S3-A4: only include characters currently IN the player's room.
        # Previously, a character who LEFT (prev_room == p_room but now_room
        # != p_room) was included with their destination room name, leaking
        # spatial info the player hasn't perceived. The player can only
        # place someone who is still co-present -- a character who left is
        # gone, and their destination is not the player's to know.
        if not p_room or now_room != p_room:
            continue
        # S3-A4 (second half): co-location alone was the whole gate, so a
        # character who ENTERED the player's pitch-dark room still arrived
        # here with moved=True. The narrator prompt's POSITION CONTINUITY
        # rule then invites rendering them and _check_narrator_fidelity
        # ENFORCES prose agreement, turning an unperceived body into a
        # required sentence.
        if not _player_sees_character(sc, p_name, p_room, name, now_room):
            continue
        moved = (prev_room is None) or (prev_room != now_room)
        # Where they came FROM is a separate perception from the fact that
        # they are here now: seeing someone walk in tells you nothing about
        # the room behind the door. Name the origin only when the player can
        # see into it (barrier + light, via has_visual). Otherwise the entry
        # still ships -- the player sees the arrival -- with no origin.
        prev_display = None
        if moved and prev_room and has_visual(
                spatial_rel(sc, p_room, prev_room)):
            prev_display = room_names.get(prev_room, prev_room)
        display = _speaker_display(
            name, recognized, info.get("appearance"), info.get("aliases"))
        payload[display] = {
            "room": room_names.get(now_room, now_room),
            "prev_room": prev_display,
            "moved": moved,
        }
        # The display is what prose says; the key is what the ledger is filed
        # under, and the attire screen needs both.
        facts.append({"name": display, "key": name, "room_id": now_room,
                      "moved": moved})
    return payload, facts, room_names


def _visible_portal_states(scene, room_id, visible_rooms):
    """F3: committed open/shut state of every door/portal the player can
    currently see, keyed by display name -- portal-link entities touching the
    player's room, door-like entities in it, transit hatches of an enclosure
    the player is in or beside, and this room's door adjacency barriers. A
    generic 'doors' entry is added only when every visible door-state
    agrees, so 'through the open doors' is checkable without a named
    entity (the DW t12 case).

    S3-A5: ``visible_rooms`` (the player's room plus any visible adjacent
    rooms) gates which portal states are included.  A portal/door in a room
    the player cannot see is withheld -- the player has not perceived it and
    must not be told its state.

    REQUIRED, since 2026-08. It defaulted to None for "backwards-compatible
    callers", and there were none: the one production call site has always
    passed the set. What the default actually did was make the gate optional
    -- three `if _filter_adjacent` branches that fell open -- so the pre-S3-A5
    leak stayed reachable by anyone who omitted an argument, and a test pinned
    it as correct. A guard with an off switch is not a guard."""
    if not room_id or not isinstance(scene, dict):
        return {}
    visible_rooms = set(visible_rooms or ()) | {room_id}
    out = {}
    _guessed = set()
    entities = scene.get("entities") or {}
    rooms = scene.get("rooms") or {}
    interior_owner = {
        rid: (r or {}).get("parent_entity")
        for rid, r in rooms.items() if isinstance(r, dict)
    }
    for eid, ent in entities.items():
        if not isinstance(ent, dict):
            continue
        name = str(ent.get("name") or eid).strip()
        state = ent.get("state") if isinstance(ent.get("state"), dict) else {}
        link = state.get("link")
        if isinstance(link, dict) and room_id in (link.get("rooms") or []):
            # S3-A5: a portal-link that also touches a room the player
            # cannot see still leaks state through the visible end, so it is
            # included only when every room the portal connects is visible.
            portal_rooms = set(link.get("rooms") or [])
            if portal_rooms and not portal_rooms.issubset(visible_rooms):
                continue
            out[name] = ("open" if str(link.get("phase") or "").lower()
                         == "open" else "shut")
            continue
        # Where this entity IS, not where two of its spellings are filed
        # (review 2026-09-07, B18): a lift whose `positions` row sits under
        # an alias reported no hatch state to the narrator at all.
        ent_room = room_of_record(scene, eid, ent)
        transit = state.get("transit")
        if isinstance(transit, dict) and transit.get("hatch"):
            if ent_room == room_id or interior_owner.get(room_id) == eid:
                hatch = str(transit.get("hatch") or "").lower()
                out[f"{name} hatch"] = "open" if hatch == "open" else "shut"
            continue
        blob = (str(ent.get("kind") or "") + " " + name).lower()
        # S3-A5: only include door-like entities positioned in a visible room.
        if ent_room in visible_rooms and any(
                w in blob for w in ("door", "gate", "hatch", "portal",
                                    "shutter")):
            # UNBOUND, and that is the whole difference from the `link`
            # branch above. A portal-link NAMES the two rooms it joins, so
            # it IS that doorway and speaks for it. This branch is a guess
            # from a word in the entity's name, and a guess must not
            # contradict the edge (see below).
            _guessed.add(name)
            val = state.get("open")
            if isinstance(val, bool):
                out[name] = "open" if val else "shut"
            else:
                sval = str(state.get("door") or state.get("status")
                           or state.get("position") or "").lower()
                if sval in ("open", "ajar"):
                    out[name] = "open"
                elif sval in ("closed", "shut", "sealed", "locked"):
                    out[name] = "shut"
    # A WAY THROUGH IS THE EDGE'S, AND THE EDGE WINS (2026-09-06). The block
    # above reads a door-like ENTITY's open/shut state; the block below reads
    # the room's own edges. Both reach the narrator, and they are free to
    # disagree -- measured (chat 117, turn 20): a bulkhead entity recorded
    # `ajar` while its edge still read `closed_door`, so the page was handed
    # "open" and "shut" about one door in the same payload.
    #
    # Nothing that decides passage reads the entity (the objects card now
    # says so outright), so where this room has any door EDGE at all, a
    # GUESSED door-claim is dropped. Only the guesses: an entity carrying a
    # portal `link` names the two rooms it joins and therefore IS that
    # doorway, and it keeps speaking. A door with no room behind it -- a
    # cupboard, a cabinet, a stove -- has no door edge to be contradicted
    # by and keeps its own state, which is what the guessing branch is
    # actually useful for.
    _door_edges = [e for e in ((rooms.get(room_id) or {}).get("adjacent") or [])
                   if isinstance(e, dict)
                   and str(e.get("barrier") or "") in ("closed_door",
                                                       "open_door")]
    if _door_edges and _guessed:
        out = {k: v for k, v in out.items() if k not in _guessed}
    edge_states = set()
    for edge in (rooms.get(room_id) or {}).get("adjacent") or []:
        if not isinstance(edge, dict):
            continue
        barrier = str(edge.get("barrier") or "")
        if barrier not in ("closed_door", "open_door"):
            continue
        to = edge.get("to")
        if to and to not in visible_rooms:
            continue
        to_name = str(((rooms.get(to) or {}).get("name")) or to or "").strip()
        state = "shut" if barrier == "closed_door" else "open"
        if to_name:
            out.setdefault(f"door to {to_name}", state)
        edge_states.add(state)
    all_states = set(out.values()) | edge_states
    if len(all_states) == 1 and (out or edge_states):
        out.setdefault("doors", next(iter(all_states)))
    return out


#: How many prior turns of the shared text reach `past_narration`. Override
#: with the `narrator_history_turns` setting; this is what a chat gets with
#: no setting written.
#:
#: The cap counts TURNS, and that bounds the block predictably because beats
#: do not grow: measured across chats 74-84, a turn contributes 700-1,200
#: characters of player input plus prose, so twelve of them is 10-14k
#: characters and a longer story does not drift upward from there. Most
#: stories never reach the cap at all -- five of the eight sampled had fewer
#: turns than the depth.
_PAST_NARRATION_TURNS = 12
#: The craft diffs (`already_established_phrases`, `overused_phrases`, the
#: fidelity reuse check) keep their original four-turn window even when the
#: narration block runs deeper. Widening them would flag more of the story as
#: already-established and suppress exactly the fine detail the block exists
#: to enable -- a different change, with the opposite sign.
_PREV_PROSE_TURNS = 4


def _past_narration_block(chat_id, turn_idx, frame_id, depth):
    """The story so far, as ONE text, exactly as the player has been reading it.

    `static/js/chat.js` renders every turn as the player's own input followed
    directly by the narrator's prose, unlabelled, inside a single `.turn`
    div. The page is therefore already one continuous narration in one voice,
    the player and the narrator writing alternating stretches of it -- and
    the narrator had never been shown that text. It received the last four
    narrator proses as `recent_prose_for_rhythm`, a style reference with the
    player's own contributions missing, which is why it could not tell where
    its own beat was supposed to start.

    No labels between the parts: they are the same voice, so a speaker tag
    would fracture a text that is already whole.

    THIS turn's input is NOT in here. It was, and the block read as one
    unbroken text because of it -- but that buried the single most
    load-bearing sentence in the payload at the tail of its longest field.
    It now has its own section, `current_narration`, sitting between this
    block and `current_events`: same voice, same position in the story,
    unmissable. Measured over 12 real beats, splitting it out and sourcing
    `current_events` from perception together produced the only arm with no
    enforceable findings AND no warnings at all.

    Returns (block, prev): the joined text, and the narrator-prose list the
    craft diffs and the fidelity reuse check still score separately.
    """
    rows = q("SELECT t.idx AS idx, t.player_input AS player_input, "
             "v.content AS content FROM turns t "
             "LEFT JOIN steps s ON s.turn_id=t.id AND s.key='narrator' "
             "LEFT JOIN variants v ON v.step_id=s.id AND v.active=1 "
             "WHERE t.chat_id=? AND t.idx<? AND t.frame_id IS ? "
             "ORDER BY t.idx DESC LIMIT ?",
             (chat_id, turn_idx, frame_id, max(1, int(depth or 1))))
    parts, prev = [], []
    # LEFT JOIN, not the inner join this replaced: a turn whose narrator step
    # is missing or inactive (a rerun in flight, an aborted beat) still had a
    # player writing in it, and dropping their text would leave a hole in the
    # middle of a block whose whole value is that it is continuous.
    for r in reversed(rows):
        said = (r["player_input"] or "").strip()
        if said:
            parts.append(said)
        prose = ""
        if r["content"]:
            try:
                prose = (json.loads(r["content"]) or {}).get("prose") or ""
            except (TypeError, ValueError):
                prose = ""
        if prose.strip():
            parts.append(prose.strip())
            prev.append(prose)
    return "\n\n".join(parts), prev[-_PREV_PROSE_TURNS:]


def _past_narration_extra_block(chat_id, turn_idx, frame_id, persona_id,
                                depth):
    """`_past_narration_block` for one additional human player.

    Same text, different seats: this persona's own inputs
    (`turn_player_inputs`, keyed by persona) interleaved with the prose that
    was rendered FOR them (`narrator_extra`, keyed by persona id inside the
    step content). Two people at one table are shown two different stories on
    purpose -- each is perception-filtered to its own seat -- so an extra
    player's block must never be assembled out of the primary player's text.

    Frame filtering comes from the join to `turns`: `turn_player_inputs`
    carries no frame of its own.
    """
    pid_key = str(persona_id)
    rows = q("SELECT t.idx AS idx, i.input AS player_input, "
             "v.content AS content FROM turns t "
             "LEFT JOIN turn_player_inputs i "
             "  ON i.chat_id=t.chat_id AND i.turn_idx=t.idx AND i.persona_id=? "
             "LEFT JOIN steps s ON s.turn_id=t.id AND s.key='narrator_extra' "
             "LEFT JOIN variants v ON v.step_id=s.id AND v.active=1 "
             "WHERE t.chat_id=? AND t.idx<? AND t.frame_id IS ? "
             "ORDER BY t.idx DESC LIMIT ?",
             (persona_id, chat_id, turn_idx, frame_id,
              max(1, int(depth or 1))))
    parts, prev = [], []
    for r in reversed(rows):
        said = (r["player_input"] or "").strip()
        if said:
            parts.append(said)
        prose = ""
        if r["content"]:
            try:
                prose = ((json.loads(r["content"]) or {}).get(pid_key) or {}
                         ).get("prose") or ""
            except (TypeError, ValueError):
                prose = ""
        if prose.strip():
            parts.append(prose.strip())
            prev.append(prose)
    return "\n\n".join(parts), prev[-_PREV_PROSE_TURNS:]


def _render_observed_events(observations, player_acts=()):
    """This beat's events, as PERCEPTION delivered them.

    `_ordered_beat_events` re-derives the same record from the loops and the
    background stage and then re-applies the firewall by hand: the delivery
    gate on quotes, the visibility gate on acts, and the identity floor on
    speakers. That is a SECOND implementation of "what reached this mind",
    standing beside the composer's, and the composer's is the one the
    firewall is actually built on -- `observations_from_render` derives it
    FROM the rendered view, so it cannot exceed the view's budget.

    Two authorities on one question drift, and this pair had drifted in three
    places at once, all measured: an act performed behind a one-way mirror
    reached the record (`_player_sees_character` is asked, but only after the
    act is already collected in some paths); a name the ledger does not hold
    was rendered as the canonical name; and an unrecognised speaker heard
    over an intercom was labelled by APPEARANCE -- chats 79/80/81 carry six
    stored narrations calling a voice on a PA "the young Korean-American
    woman" to a player sealed in a cell who has never seen her. Perception's
    own view said "You hear a voice say" in every one of them.

    So the model reads perception's answer. The structured record stays on
    `_fidelity_facts` for the deterministic checks, which score what is on
    the page rather than deciding what may reach it.

    THE PLAYER'S OWN ACTS ARE PREPENDED, and they have to be: perception
    cannot supply them, because a mind is never handed its own conduct as a
    percept. Carrying them ONLY as raw text in `current_narration` does not
    work -- measured over 12 real beats, player-act coverage on the page fell
    to 1 of 9 while every draft still scored 12/12 clean on every fidelity
    check, because no check can see a mind's own conduct either. Restoring
    them as entries took coverage back to 7 of 9 and REDUCED enforceable
    findings from 3 to 1. They are the Director's reconciled `observable`
    surfaces, which is what actually happened, rather than the claim the
    player's own sentence makes.
    """
    lines = []
    for act in player_acts or ():
        text = str((act or {}).get("action") or "").strip()
        if text:
            lines.append(_event_line(
                "act_player", n=len(lines) + 1,
                actor=act.get("actor") or "you", action=text))
    for obs in observations or []:
        if not isinstance(obs, dict):
            continue
        # STANDING STATE IS NOT AN EVENT, and numbering it here was the
        # engine contradicting its own payload comment: `present_scene` is
        # declared "standing state, not chronology" three fields below, and
        # then every standing span arrived here too, numbered, under a sheet
        # rule saying each numbered entry is a delivery the narrator must
        # render. A beat's list was mostly wallpaper carrying an obligation,
        # and a model that renders one paragraph per numbered entry is
        # obeying that, not misreading it.
        #
        # `standing` is decided at projection, where the percept is still in
        # hand (`composer.observations_from_render`), and it is FALSE for an
        # appearance the engine flagged `force` -- a garment gone, a mask
        # down. A change of clothing is an event and keeps its number. A row
        # stored before the field existed reads back False, which is
        # obligation: replay can never make something skippable that was not
        # already.
        if obs.get("standing"):
            continue
        text = str((obs.get("observed") or {}).get("text") or "").strip()
        if text:
            lines.append(_event_line(
                "observation", n=len(lines) + 1, text=text))
    return "\n".join(lines)


def _render_current_events(events, player_name=""):
    """`event_order` as a plain chronological package.

    NOT WHAT THE NARRATOR IS WRITTEN FROM ANY MORE (E14). `narrator` builds
    `current_events` from `_render_observed_events` -- perception's own record
    -- and keeps `event_order` on `_fidelity_facts` for the deterministic
    checks alone, so the model is handed what a mind was admitted rather than
    what happened. This renderer survives for `tools/narrator_package_bench.py`
    and the tests that score the two shapes against each other; a change here
    reaches no played beat.

    The structured list stays the record the deterministic checks read; this
    is the same record as text, because the thing being asked of the model is
    prose and a numbered line of prose is what it can follow. A player line is
    marked as already standing on the page above -- the one place the
    expand-never-repeat rule is actually needed is the line it governs.
    """
    lines = []
    for ev in events or []:
        if not isinstance(ev, dict):
            continue
        n, actor = ev.get("n"), (ev.get("actor") or "").strip()
        if ev.get("kind") == "speech":
            quote = _quote_body(str(ev.get("quote") or "")).strip()
            if not quote:
                continue
            if ev.get("declared"):
                lines.append(_event_line(
                    "speech_declared", n=n, actor=actor, quote=quote))
            else:
                lines.append(_event_line(
                    "speech", n=n, actor=actor, quote=quote))
        elif ev.get("action"):
            # Marked as emphatically as the speech entries, and for a reason
            # measured rather than guessed: the per-line speech marker took
            # placeholders from 14 to 0 across six drafts while a prose-block
            # rule in the sheet saying the same thing about ACTS changed
            # nothing -- acts still reached the page 5 times in 12
            # (tools/narrator_package_bench.py, grok-4.20, n=6). The player's
            # raw input at the tail of `past_narration` describes the act, and
            # without this the model reads it as a beat already written.
            # Whose act it is decides what the marker may CLAIM. Every act
            # entry used to say "the player described attempting it", and
            # `_ordered_beat_events` lists NPC acts on the same footing as
            # the player's -- so a character's own motion was announced to
            # the model as something the player had written. A marker is only
            # worth its measured power while it is true.
            if actor and player_name and actor == player_name:
                lines.append(_event_line(
                    "act_player", n=n, actor=actor, action=ev["action"]))
            else:
                lines.append(_event_line(
                    "act_other", n=n, actor=actor, action=ev["action"]))
    return "\n".join(lines)


def _extension_narration_payload(ctx, payload, *, scope, player=""):
    """Hand the assembled narrator payload to installed extensions, or leave it.

    Lazy-imported and total, the same discipline as `character.py`'s routing
    seam and for the same reason: this runs inside the turn's wall clock, so a
    broken extension must cost the beat nothing. With nothing installed -- the
    overwhelmingly common case -- this is one attribute lookup.
    """
    try:
        import extension_runtime

        return extension_runtime.dispatch_narration_payload(
            ctx, payload, scope=scope, player=player)
    except Exception:
        return payload


def _quote_marks():
    """Every mark ANY installed pack counts as a quotation mark.

    A closed vocabulary the ENGINE owns and can enumerate -- straight and
    curly pairs in English, those plus 「」『』 in Japanese -- which is the
    kind of list code is allowed to hold. It is read out of the packs, never
    guessed at, and it is the UNION rather than the active pack's own set:
    what is being stripped here is decoration a model put around the
    ENGINE'S OWN TOKEN, and a model that reaches for a corner bracket in an
    English story has still put a mark where the engine puts the marks. A
    pack that adds a mark widens this by installing.
    """
    global _QUOTE_MARKS_CACHE
    if _QUOTE_MARKS_CACHE is None:
        marks = set()
        for language_id in installed_language_packs():
            try:
                marks.update(str(c) for c in linguistic(
                    "agents.common", "_QUOTE_CHARS", language_id))
            except LanguagePackError:
                continue
        _QUOTE_MARKS_CACHE = "".join(sorted(marks))
    return _QUOTE_MARKS_CACHE


_QUOTE_MARKS_CACHE = None


def _speech_weld(language=None):
    """The one pair of marks a delivered line is welded in, from the pack.

    A Japanese page welds 「」 where an English one welds straight quotes, and
    neither spelling is this module's to choose. Before 2026-09-05 the weld
    was the literal `'"%s"'`, so every Japanese view carried an English
    speech mark inside a Japanese sentence.
    """
    pair = compositor_value("speech_quote_pair", language)
    return str(pair[0]), str(pair[1])


#: Sentence-terminal and clause marks, in both scripts the packs install.
#: TYPOGRAPHY, not vocabulary: these are the marks a line ENDS with, a closed
#: set the writing system fixes and the engine can enumerate, which is exactly
#: the kind of table code is allowed to hold. Nothing here tries to anticipate
#: how English will phrase anything.
_TERMINAL_MARKS = ".,;:!?…。、！？"
#: The two of them that a dialogue tag uses.
_TAG_COMMAS = ",、"


def _terminal_at_the_weld(body, outer):
    """`(body, outer)` with the punctuation at a welded line's closing mark
    reconciled. One mark ends a line, and the engine's is the one that counts.

    THE ENGINE WELDS THE LINE'S OWN TERMINAL PUNCTUATION; a mark the model
    typed immediately outside that weld is a second terminal for the same
    line. Measured (masque, 2026-09-05, PX18): the model reads DIALOGUE
    FIDELITY, writes `"{{L1}}",` for a delivered line that already ends in a
    full stop, and the page ships `"...will be served in the half-hour.",
    Lisenne Corvay said` -- four times in one beat, and a guard fired on it
    every time and changed nothing.

    This is a REPAIR rather than a warning, and it is the only one this stage
    makes. The standing rule for narration is that every reading of the prose
    detects and reports; the rule that rule was written for is a code-based
    JUDGMENT that the model's prose is wrong, paid for with a whole extra
    call. This is neither: the doubled mark is the engine's own weld meeting
    the model's, no judgment about the writing is involved, and putting one
    mark where the writing system allows one costs nothing. Anything that
    needs an opinion about the prose -- a wrong speaker, a pronoun, an adverb
    -- stays a warning.

    Four cases, and everything else is left exactly as written:
      * the same mark on both sides -- the outer one is a duplicate, and goes;
      * a tag comma against a full stop -- the comma takes the stop's place,
        which is what the convention asks for;
      * a tag comma against a question or exclamation -- the mark that carries
        meaning stays and the comma goes;
      * a tag comma against a line that ends bare -- it belongs inside.
    """
    body = str(body or "")
    outer = str(outer or "")
    if not outer or not body:
        return body, outer
    last = body[-1]
    if last == outer:
        return body, ""
    if outer in _TAG_COMMAS:
        if last in ".。":
            return body[:-1] + outer, ""
        if last in _TERMINAL_MARKS:
            return body, ""
        return body + outer, ""
    return body, outer


def _substitute_dialogue_tokens(prose, lines, language=None):
    """Put the exact words where the model put the token, welded ONCE.

    A QUOTED LINE IS WELDED ONCE, BY THE CODE THAT OWNS QUOTING. The
    placeholder protocol hands the model a token and takes the words back
    here; the marks around them are the engine's, not the model's. The model
    reads DIALOGUE FIDELITY ("render the words as a quote") and writes
    `"{{L1}}"`, and this function then added a second pair -- `""line""` in
    English, `「"line"」` in Japanese. Measured on five separate play runs
    (F29, F54; PA10, PB9, PE7): the majority of beats in each, and 31 false
    guard warnings in the flat run alone, because a doubled mark shifts every
    quote-region boundary a guard reads.

    So the token is matched TOGETHER with any marks the model wrapped it in,
    and the whole span is replaced by one pack-correct pair around a body
    that has had its own marks stripped. There is no repeated-run
    normalisation anywhere downstream: a doubled mark is not detected and
    repaired, it is structurally never written.

    Returns the prose and the lines whose token never appeared. An OMITTED
    token is the residual failure mode, and it is a strictly better one than a
    paraphrase: it is countable before the reader sees anything, and the
    engine knows exactly which line is missing. A paraphrase is neither.
    """
    text = str(prose or "")
    missing = []
    marks = _quote_marks()
    open_mark, close_mark = _speech_weld(language)
    wrap = "[%s]*" % re.escape(marks) if marks else ""
    tail_class = "[%s]?" % re.escape(_TERMINAL_MARKS)
    for index, line in enumerate(lines, 1):
        pattern = re.compile(r"%s\{\{L%d\}\}%s(%s)"
                             % (wrap, index, wrap, tail_class))
        body = str(line or "").strip().strip(marks).strip()

        def _weld(match, _body=body):
            inner, outer = _terminal_at_the_weld(_body, match.group(1))
            return open_mark + inner + close_mark + outer

        text, hits = pattern.subn(_weld, text)
        if not hits:
            missing.append((index, line))
    # A token for a line that does not exist is the model inventing an index.
    # Strip it rather than leaving `{{L9}}` on the page.
    text = _LINE_TOKEN_RE.sub("", text)
    return re.sub(r"[ \t]{2,}", " ", text), missing


#: The placeholder protocol's own token. Engine-owned: the narrator card
#: teaches this exact spelling, so matching it is reading the protocol back,
#: not searching prose for a phrase.
_LINE_TOKEN_RE = re.compile(r"\{\{L(\d+)\}\}")


def _stray_line_tokens(prose, lines):
    """Tokens the model wrote with no line behind them.

    A TOKEN IS A LINE'S ADDRESS, AND A LINE THAT WAS NEVER HANDED OVER HAS
    NONE. The protocol numbers the delivered lines and the model places
    their tokens; on a beat with no `dialogue_lines` at all the model has
    nothing to place, and the player's own line is never one of them (the
    echo rule wants its ABSENCE). Measured, Harrowmere 2026-09-02, three of
    forty beats: turn 15 put `{{L1}}` where the player's own question went,
    turn 22 wrote one on a beat with no line anywhere, and turn 37 wrote one
    for a line the view never carried. Substitution only ran when tokens
    existed, so each reached the page verbatim -- the protocol leaking
    through the story it was built to protect. Returns the token strings, in
    page order, so the warning can name what was stripped.
    """
    known = len(lines or ())
    return ["{{L%s}}" % m.group(1)
            for m in _LINE_TOKEN_RE.finditer(str(prose or ""))
            if int(m.group(1)) < 1 or int(m.group(1)) > known]


def _generate_narration(payload, view, prev, p_lines, correction_notes=None,
                        fidelity_facts=None, language="en"):
    call_payload = dict(payload)
    if correction_notes:
        call_payload["correction_notes"] = correction_notes
    tokens = _dialogue_tokens(view, p_lines)
    if tokens:
        call_payload["dialogue_lines"] = [
            {"token": "{{L%d}}" % (i + 1), "line": line}
            for i, line in enumerate(tokens)]
    out = _agent_json(
        "narrator",
        "narrator",
        get_prompt("narrator", language),
        call_payload,
        max_tokens=None,   # the configured ceiling; see complete_validated_json
    )
    # Warning-only re-normalization; strict schema+semantic validation
    # (with repair/fallback/raise) already ran inside _agent_json.
    out, warnings = validate_llm_output("narrator", out)
    # `text` IS `prose` WHEN `prose` IS EMPTY. The old note here recorded that
    # a `setdefault` could never fire (the validated dict always carries a
    # `prose` key) and that a `text`-only payload had already been rejected
    # upstream anyway. The second half is no longer true -- narration blocks
    # on JSON validity alone now -- so a model that files its page under
    # `text` reaches this line, and reading it is the "one-line alias"
    # `llm/schemas.py` asked for rather than a beat thrown away over a key
    # name. An explicit emptiness test, because `setdefault` cannot see a
    # present-but-blank field.
    if not str(out.get("prose") or "").strip():
        _aliased = str(out.get("text") or "").strip()
        if _aliased:
            out["prose"] = _aliased
    out.setdefault("new_specifics", [])
    # ALWAYS, not only when tokens exist. The strip inside the substitution
    # is the deterministic floor under the protocol -- a token is never
    # prose -- and running it only on beats that had lines left every other
    # beat's stray token on the page (`_stray_line_tokens`).
    stray = _stray_line_tokens(out.get("prose", ""), tokens)
    # BEFORE the fidelity check, which is what makes the check measure the
    # page the reader gets rather than a draft that still holds tokens.
    prose, unplaced = _substitute_dialogue_tokens(
        out.get("prose", ""), tokens, language=language)
    out["prose"] = prose
    for _index, line in unplaced:
        warnings.append(
            "Narrator omitted a delivered line's placeholder: "
            f"\"{line[:80]}\"")
    if stray:
        warnings.append(
            "Narrator wrote a line token with no line behind it (%s); "
            "stripped. A token exists only for a line in dialogue_lines, and "
            "the player's own line is never one." % ", ".join(stray))
    # The player's own declared lines must NOT count toward DIALOGUE
    # FIDELITY -- PLAYER ECHO RULE requires the opposite of them (excluded,
    # not present), so scoring them here would make the two rules fight and
    # push the retry loop toward violating the echo rule to "fix" a false
    # positive.
    facts = fidelity_facts or {}
    fidelity_warnings = _check_narrator_fidelity(
        out, view, recent_prose=prev, exclude_quotes=p_lines,
        cast_pronouns=call_payload.get("cast_pronouns"),
        player_name=call_payload.get("player_name"),
        narration_person=call_payload.get("narration_person"),
        # Absent on every story that set no tense, so the check declines to
        # score it -- the same key that governs the instruction governs the
        # verification, and neither exists without the other.
        narration_tense=call_payload.get("narration_tense"),
        event_order=facts.get("event_order"),
        position_facts=facts.get("position_facts"),
        room_names=facts.get("room_names"),
        portal_states=facts.get("portal_states"),
        attire_facts=facts.get("attire_facts"))
    # THE ALIAS RUNS BOTH WAYS OR IT IS A FOOTGUN. `text` is read above as a
    # spelling of `prose` and then left exactly as the model wrote it, so the
    # stored narrator variant carried `{"prose": "...", "text": ""}` and any
    # reader keying on `text` got nothing -- which four tools do, and which a
    # play run's own reader did on turn 9 (solitude, PS20).
    # `NarratorOutput` declares both fields; the repair is that they agree,
    # not that one of them goes.
    if str(out.get("prose") or "").strip():
        out["text"] = out["prose"]
    return out, warnings, fidelity_warnings


def _narrator_player_declared(interpreted):
    """Player conduct for prose, with spoken CONTENT structurally absent.

    The Director has already interpreted the raw input and perception has
    already delivered its consequences.  Narration needs ordering, delivery,
    targets, visible action and explicitly authored private thought.  It does
    not need a third copy of the player's quote, whose only observed use was
    semantic drift while trying not to echo it.
    """
    interpreted = interpreted if isinstance(interpreted, dict) else {}
    sequence = []
    spoke = False
    for event in interpreted.get("sequence") or []:
        if not isinstance(event, dict):
            continue
        if event.get("type") == "speech":
            spoke = True
            sequence.append({
                key: event[key] for key in (
                    "type", "volume", "intended_target", "targets",
                    "visibility", "conceal_from")
                if key in event
            })
        elif event.get("type") == "communication":
            spoke = True
            sequence.append({
                "type": "communication",
                "act": event.get("act"),
                "content": event.get("content"),
                "targets": event.get("targets") or [],
                "volume": event.get("volume", "normal"),
            })
        else:
            safe = {
                key: event[key] for key in (
                    "type", "event_id", "commitment", "stage", "targets",
                    "visibility", "conceal_from")
                if key in event
            }
            onset = observable_action_onset_text(event)
            if onset:
                safe["onset"] = onset
            sequence.append(safe)
    asserted = [
        observable_action_text(event)
        for event in interpreted.get("sequence") or []
        if isinstance(event, dict) and event.get("type") == "action"
        and str(event.get("commitment") or "") != "contestable"
        and observable_action_text(event)
    ]
    return {
        "sequence": sequence,
        "spoke": spoke or bool(interpreted.get("speech")),
        "action": asserted[0] if asserted else None,
        "private_thought": interpreted.get("private_thought"),
    }


def _strip_raw_player_input_echo(prose, raw_input):
    """Remove a verbatim reprint of the player's non-dialogue turn.

    The input is already on the page. Narration may render its adjudicated
    motion, but occasionally returns the entire instruction paragraph word for
    word. Exact normalized-span removal is conservative: paraphrase and short
    callbacks are untouched, while the duplicated paragraph disappears.
    """
    prose = str(prose or "")
    raw = str(raw_input or "").strip()
    if len(raw) < 20:
        return prose
    pattern = r"\s+".join(re.escape(part) for part in raw.split())
    return re.sub(pattern, "", prose, count=1, flags=re.I).strip()

def narrator(ctx, nonce):
    chat = ctx.chat
    pers = persona_of(chat)
    # THE TURN ROW SAYS WHETHER THIS IS THE OPENING, and it is the only thing
    # entitled to. This read `ctx.get("director_establish") or {}` and branched
    # on the truthiness of a MODEL STAGE'S OUTPUT -- gating three separate
    # things on it: which view is read, the `scene_opening` payload flag, and
    # the whole `_world_fields`/`_fidelity_facts` block. `_run_pipeline`
    # decides the same question from `turn_row["idx"] == 0`, so it was one rule
    # with two owners, and the non-authoritative one could answer "no opening"
    # for a turn the runtime had already planned as one. Latent rather than
    # live today only because `DirectorEstablish` default-fills, which is a
    # property of a schema and not of this decision.
    est = ctx.turn["idx"] == 0
    if est:
        view = (ctx.get("perception_establish", {}).get("views") or {}).get("player") \
            or compositor_text("narrator_immediate", ctx.language)
    else:
        view = (ctx.get("perception_outcome", {}).get("views") or {}).get("player") \
            or compositor_text("narrator_nothing", ctx.language)
    # Frame-filtered: t.idx is GLOBAL play order shared by every frame, so
    # without this an OTHER concurrently-played frame's prior text would leak
    # into this frame's own.
    try:
        _depth = int(get_setting("narrator_history_turns")
                     or _PAST_NARRATION_TURNS)
    except (TypeError, ValueError):
        _depth = _PAST_NARRATION_TURNS
    past_narration, prev = _past_narration_block(
        chat["id"], ctx.turn["idx"], ctx.turn["frame_id"], _depth)
    di = ctx.get("director_interpret") or {}
    p_lines = player_speech_lines(di)

    player_declared = _narrator_player_declared(di)

    # (x or {}) rather than .get(key, {}): a hand-edited sheet with an
    # explicit "identity": null defeats the .get default and would crash
    # the narrator stage every turn.
    player_name = (pers.get("identity") or {}).get("name") or "Player" if isinstance(pers, dict) else "Player"
    player_pronouns = (pers.get("identity") or {}).get("pronouns", {}) if isinstance(pers, dict) else {}
    # Durable persistence of a newly detected person is deferred to commit
    # (commit.py's commit_narration_person) via this pending sink -- the
    # narrator stage itself must not write world state before the commit
    # boundary validates the turn.
    pending_person_writes = {}
    narration_person = _resolve_narration_person(
        chat["id"], ctx.input or "", player_name, player_pronouns,
        pending=pending_person_writes,
        voice_setting=persona_voice_setting(pers) if isinstance(pers, dict)
        else "",
        scenario=chat.get("scenario") or "")
    # PERSON IS DETECTED, TENSE IS AUTHORED, and these two lines are where that
    # difference is visible. Person is inferred from how the player wrote this
    # turn and written back to the chat at commit; tense is read straight off
    # the author's style guide, per turn, so turning the dial applies to the
    # next beat with no restart and no re-detection. Nothing writes this one
    # back -- there is nothing to remember that the author did not already say.
    #
    # The opening turn takes this same path (`narrator` renders turn 0 too,
    # with `est` choosing only WHICH view it reads), so the dial reaches the
    # one beat that had nothing to inherit a tense from.
    story_tense = _resolve_narration_tense(chat["id"], prev)

    # WHAT THIS PAGE MAY CALL EACH BODY, decided once and used by every
    # narrator field that names one. `known` is perception's own ledger and
    # `_speaker_display` is its floor, so the roster below cannot exceed the
    # view standing beside it. Hoisted above the world-fields block (which
    # rebuilt these same two structures) because `cast_pronouns` is built on
    # the opening turn too, and an establish is exactly the beat on which
    # nobody has been introduced yet.
    known_map = wget(chat["id"], "known", {}) or {}
    recognized = set(known_map.get(player_name) or [])
    cast_info = {}
    for _row in ctx.cast:
        try:
            _sh = json.loads(_row["sheet"])
        except Exception:
            continue
        cast_info[character_name(_sh)] = {
            "appearance": character_appearance(_sh),
            "aliases": character_scene_keys(_sh)[1:],
        }

    def _view_label(name):
        info = cast_info.get(str(name)) or {}
        return _speaker_display(name, recognized, info.get("appearance"),
                                info.get("aliases"))

    cast_pronouns = _cast_pronouns(ctx.cast, label=_view_label)

    # Consciousness gate: when the player is non-awake, their `player_view` is
    # already the deterministic residue (perception_outcome). Do NOT also hand
    # the narrator the room's spatial frame/facts -- passing scene layout with
    # an instruction to render only a residue is exactly the "objective state +
    # instruction to ignore it" pattern the engine forbids. Gate the payload,
    # not the prose: the narrator renders an honest fade-out from the residue.
    _res_diff = (ctx.get("director_resolve") or {}).get("state_diff") or {}
    player_awareness = awareness_of(
        apply_awareness_diff(awareness_map(chat["id"]), _res_diff), player_name)
    _scene_for_frame = ctx.get("outcome_scene") or get_scene(chat["id"], chat)
    # Through the same identity floor as every other name in this payload:
    # `spatial_digest` renders `ahead_entity` from `scene.positions`, which is
    # keyed by canonical name, and `_view_label` was built twenty lines up
    # for exactly this and not handed over -- the leak `observer_label_fn`'s
    # docstring records, on the narrator's side.
    _spatial_fields = ({} if player_awareness in NON_AWAKE_GATED else {
        "spatial_frame": spatial_digest(_scene_for_frame, player_name,
                                        label_for=_view_label),
    })

    # F1-F4 world-fidelity payload: the pipeline's own ordered event record,
    # co-present position deltas, and visible portal states -- plus the same
    # structures as check inputs for the deterministic backstops in
    # _check_narrator_fidelity. Normal turns only (an opening turn has no
    # prior beat to delta against and no loop order), and gated with the
    # spatial fields on consciousness: a non-awake mind gets no scene.
    # The chronological package the narrator writes from. Empty on an opening
    # turn (nothing has happened yet) and for a non-awake mind (no beat
    # reaches it), which is the same gate the world fields take below.
    current_events = ""
    _world_fields, _fidelity_facts = {}, {}
    if not est and player_awareness not in NON_AWAKE_GATED:
        # The scene this page is written from outranks the cached answer,
        # not the other way round (`common.player_room_in`, finding B36):
        # `perception_outcome` refreshes the cache from this same scene, and
        # where it could not, the scene is still the fresher of the two.
        p_room = player_room_in(_scene_for_frame, ctx, pers=pers,
                                player_name=player_name, resolve=False)
        # Everything that means "the player" in engine-written prose: their
        # own name forms, and the epithets minted for the minds that have not
        # recognized them. `avoid` is every OTHER body's display in this
        # payload, so a descriptor two bodies share is never claimed as the
        # player's.
        _p_aliases = ((pers.get("identity") or {}).get("aliases") or []) \
            if isinstance(pers, dict) else []
        _other_displays = [
            _speaker_display(_n, recognized, _i.get("appearance"),
                             _i.get("aliases"))
            for _n, _i in cast_info.items() if _n != player_name
        ]
        player_forms = self_name_forms(
            player_name, [player_name, *_p_aliases]) + self_reference_forms(
                player_name,
                (pers.get("appearance") or persona_appearance(pers))
                if isinstance(pers, dict) else "",
                _p_aliases, avoid=_other_displays)
        event_order = _ordered_beat_events(
            ctx, player_name, view, recognized, cast_info,
            scene=_scene_for_frame, p_room=p_room,
            player_forms=player_forms)
        pos_payload, pos_facts, room_names = _position_delta_payload(
            ctx, chat, player_name, p_room, recognized, cast_info)
        # S3-A5: pass visible rooms so portal states for unseen rooms are
        # withheld from the narrator payload. visible_adjacent_rooms returns
        # room RECORDS ({room_id, room_name, barrier, description}), not ids
        # -- set() over them raised TypeError: unhashable type: 'dict' and
        # crashed the narrator on every awake, non-establishment turn whose
        # room had a sight-permitting adjacency. Perception unpacked the
        # same records the same way, in the scene payload it built for the
        # retired model path; this is now the only reader of that shape
        # outside `world/spatial.py`.
        _visible = {
            str(r["room_id"]) for r in visible_adjacent_rooms(_scene_for_frame, p_room)
            if isinstance(r, dict) and r.get("room_id")
        } | ({p_room} if p_room else set())
        portal_states = _visible_portal_states(_scene_for_frame, p_room, _visible)
        # WHOSE DRESS THE PAGE MAY SPEAK FOR. The player's own body always --
        # a mind has a channel to its own clothing -- plus exactly the bodies
        # `_position_delta_payload` already admitted, which is the perception
        # gate (`_player_sees_character`), not co-location. A check fact is
        # not a payload field: this reaches the deterministic screen and never
        # the model, so nothing here widens what the narrator may know.
        _attire_facts = attire_exposure_facts(_scene_for_frame, [
            (player_name, exposure_owner_refs(
                narration_person, player_name, player_pronouns)),
            # `f["name"]` on the pronoun side: the ledger is read by key and
            # the pronouns are now filed under the DISPLAY, which is the same
            # answer for a recognised body and the only available one for a
            # body the view labels rather than names.
            *((f["key"], exposure_owner_refs(
                None, f["name"], cast_pronouns.get(f["name"])))
              for f in pos_facts),
        ])
        # PERCEPTION'S OWN RECORD is what the model reads (see
        # `_render_observed_events`). `event_order` is still built above: it
        # stays on `_fidelity_facts` for the deterministic checks, which score
        # what reached the page rather than deciding what may reach the model.
        _obs_map = (ctx.get("perception_outcome", {}) or {}).get(
            "observations") or {}
        current_events = _render_observed_events(
            _obs_map.get("player") or [],
            [ev for ev in event_order
             if ev.get("kind") == "action" and ev.get("actor") == player_name])
        # WHAT THE PLAYER IS WEARING, from the ledger that owns it. The
        # narrator sheet already forbids extending "what anyone wears", and
        # the prose dressed the player anyway -- because the payload carried
        # no clothing at all. `_attire_facts` below is computed from the same
        # scene and reaches the deterministic screen ONLY (its own comment
        # says so), and the screen answers one question: is a COVERED region
        # narrated bare. It has nothing to say about a garment asserted onto
        # a body whose ledger does not carry it, which is the other half of
        # the same disagreement -- measured chat 98 t27, "her uniform sleeve"
        # against a ledger reading combadge + civilian clothing.
        #
        # This widens nothing: a mind has a channel to its own clothing, the
        # same ground `attire_exposure_facts` is already built on, and the
        # narrator writes the player-facing slice. Every OTHER body's dress
        # keeps reaching it the only way it may -- through the composed view,
        # behind perception's own gate -- and is deliberately not here.
        # Through `entry_for` like every other reader of this ledger: a
        # case-variant key here silently dropped `player_attire` from the
        # payload, which is the absence this block exists to fix (review
        # 2026-09-07 B5).
        _worn = compact_attire(attire_model.entry_for(
            (_scene_for_frame or {}).get("attire"), player_name))
        if _worn:
            _world_fields["player_attire"] = _worn
        if pos_payload:
            _world_fields["co_present_positions"] = pos_payload
        if portal_states:
            _world_fields["portal_states"] = portal_states
        # Per-sense delivery manifest (additive, absent-when-empty like
        # authored_body_parts, so pre-change turns keep their payload shape
        # and reroll/replay stay safe). Built from the outcome observations'
        # own IR-derived channels plus the standing substrate; every
        # admission subtracts -- see _sensory_channels_manifest.
        # The player's own composer ledger decides whether a standing fact is
        # news (B28); read from the STORED perception step, not from turn
        # state, so a narrator rerun sees the same verdicts the first run did.
        _verdicts = _player_standing_verdicts(ctx)
        _senses = _sensory_channels_manifest(
            _scene_for_frame, player_name, view,
            _obs_map.get("player") or [], recognized, cast_info, p_room,
            standing_verdicts=_verdicts)
        if _senses:
            _world_fields["sensory_channels"] = _senses
        _fidelity_facts = {
            "event_order": event_order,
            "position_facts": pos_facts,
            "room_names": room_names,
            "portal_states": portal_states,
            "attire_facts": _attire_facts,
        }

    _abp = _authored_body_parts(ctx, pers, player_name)
    # ABSENT WHEN EMPTY, the pattern `authored_body_parts` already set.
    # An empty field is not free: it is a key the model must read and
    # discard, and worse, it ARGUES FOR A RULE WITH NO REFERENT -- the
    # sheet spends 1.5k characters on what to do with
    # `already_established_phrases`, and that block is being read against
    # `[]` on the ordinary beat. `already_established_phrases` is empty on
    # ordinary beats BY CONSTRUCTION and not because it is dead: since the
    # composer kept a standing ledger, `render_view` suppresses standing
    # state the observer was already given, so an ordinary view has nothing
    # left to overlap with recent prose. It fills on the FULL-RENDER beats
    # (a room change, a re-entry), which is exactly where re-cataloguing is
    # the risk it exists to stop -- so the field stays and only its empty
    # emission goes.
    _exemplars = json.loads(get_setting("exemplars") or "[]")
    # `forced`: the narrator is not penalised for the engine's own wording.
    _overused = _overused_phrases(prev, forced=view)
    _established = _already_established_phrases(view, prev)
    _voice = ((pers.get("narration") or {}).get("voice_setting", "")
              if isinstance(pers, dict) else "")
    # ORDER IS THE MESSAGE. `complete_validated_json` sends this dict as
    # `json.dumps(payload, ensure_ascii=False)`, and a Python dict serializes
    # in INSERTION order -- so this literal is, exactly, the order the model
    # reads the beat in. Nothing else constrains it:
    # `llm/prompt_cache.add_cache_breakpoint` puts the breakpoint on the
    # SYSTEM block, so the user message has no cached prefix to protect and
    # reordering it is free.
    #
    # It runs config -> craft -> standing facts -> the three PACKAGES, so
    # that writing begins immediately after `current_events`, which is the
    # material being written from. The previous order was the reverse of
    # this: the view opened the payload, eight identity keys separated it
    # from the world record, and the last thing read before generating was a
    # list of phrases NOT to use.
    payload = {
        # -- Who is writing, and in whose voice.
        "narration_person": narration_person,
        # ABSENT WHEN UNSET, the pattern `authored_body_parts` argues for a few
        # lines up: an unset story is one whose author expressed no opinion,
        # and shipping `""` would make the model read a key and discard it --
        # or worse, read the empty key as an invitation to choose.
        **({"narration_tense": story_tense} if story_tense else {}),
        "player_name": player_name,
        "player_pronouns": player_pronouns,
        "cast_pronouns": cast_pronouns,
        "player_awareness": player_awareness,
        **({"private_voice_setting": _voice} if _voice else {}),
        "scene_opening": bool(est),
        # A body's extra parts are AUTHORED, never inferred. Absent when
        # nobody declared any, so ordinary casts keep their payload shape.
        **({"authored_body_parts": _abp} if _abp else {}),
        # Targeting, visibility and authored private thought -- still with
        # the spoken CONTENT absent. The words now reach the model twice, as
        # the tail of `past_narration` and as an entry in `current_events`,
        # and a third structured copy is what the "meals and a bed" paraphrase
        # came out of; this one is the copy that was never carrying position.
        "player_declared": player_declared,
        # `do_not_quote_verbatim` USED TO SIT HERE, a third copy of the
        # player's own lines carried purely as a prohibition. It is gone: the
        # words already reach the model as the tail of `past_narration`, the
        # echo rule is stated in the sheet, and the FLOOR under it was never
        # this field -- `_strip_player_echo` deletes an echo deterministically
        # from `p_lines`, which is a local here and never came from the
        # payload. Measured over 12 real beats (tools/narrator_sheet_bench.py,
        # `no_do_not_quote` arm): no enforceable regression attributable to
        # the drop. It was also the only payload field the sheet never
        # mentioned in 31k characters, which is its own verdict on how much
        # explaining it needed.

        # -- Craft.
        **({"exemplars": _exemplars} if _exemplars else {}),
        **({"overused_phrases": _overused} if _overused else {}),
        **({"already_established_phrases": _established} if _established
           else {}),

        # -- Standing facts. perception_outcome stashes this turn's post-move,
        # orientation-refreshed scene; fall back to the committed KV on the
        # opening turn (establish), where no movement has happened and
        # orientation is fresh anyway. Using the committed scene here would
        # describe the space with LAST beat's facing on movement beats
        # (commit runs after this stage).
        **_spatial_fields,
        **_world_fields,

        # -- The three packages, in reading order. `past_narration` is the
        # story so far as one unlabelled text ending in this turn's raw input;
        # `present_scene` is perception's render of what may legitimately be
        # perceived right now; `current_events` is what happened this beat, in
        # order, and is the writing material.
        "past_narration": past_narration,
        # The player's own writing for THIS turn, in its own right: the same
        # voice as the block above and the sentence the narrator continues
        # from. It is a CLAIM about what they did -- `current_events` is the
        # record of what came of it, and wins wherever the two differ.
        "current_narration": (ctx.input or "").strip(),
        "present_scene": view,
        "current_events": current_events,
        "variant_seed": nonce,
    }
    # Once, here, rather than inside `_generate_narration`: a hook re-run per
    # attempt could hand each attempt different context, so a second pass would
    # be narrating against a frame the first never saw and the retry would look
    # like the defect. The passes that re-entered it -- one fidelity correction
    # and up to two craft rewrites -- are gone (2026-09-06, below), which
    # leaves one generation per beat and whatever JSON retry `_agent_json`
    # does inside it; the placement stays because it is what makes that true
    # of any pass added later (E13).
    payload = _extension_narration_payload(ctx, payload, scope="narrator")
    out, warnings, fidelity_warnings = _generate_narration(
        payload, view, prev, p_lines, fidelity_facts=_fidelity_facts,
        language=ctx.language)

    # THE FIDELITY CORRECTION PASS IS GONE, for the reason the craft rewrite
    # below was removed and by the same rule: a second full narrator call to
    # re-enforce something the prompt already says. It read its own warning
    # list, decided the page was wrong, and rerolled -- which is what a reader
    # sees as valid prose appearing and then being replaced. The warnings it
    # was built on stay, non-blocking, on the step's own saved output.
    #
    # THE STANDING RULE FOR THIS STAGE, from here on: narration blocks on
    # being parseable JSON and on nothing else. Every other reading of the
    # prose DETECTS and REPORTS; none rejects, rerolls or rewrites.

    # THE CRAFT REWRITE IS GONE, and prose rules live where prose rules belong.
    #
    # It bought a second full narrator call to enforce a list the NARRATOR
    # PROMPT ALREADY CARRIES -- "eyes flick", "middle distance", "hangs in the
    # air" and the rest are all in its 37,616 characters, so the loop was
    # duplicate enforcement of an instruction the model had already been given.
    #
    # And it enforced by matching a STRING rather than the usage the string
    # usually indicates, which is this repo's oldest recurring defect. Measured
    # on a live market-town turn: the pattern `\bregisters?\b`, listed as
    # "sensor-ledger diction", fired on the ordinary English verb in "stepped
    # aside for her without seeming to REGISTER he'd done it". One false
    # positive cost 21.2s -- the largest single model cost in a 352s turn --
    # and the rewrite it forced came back 40% shorter (1029 chars to 613) and
    # was accepted automatically, because the acceptance test asked only for
    # fewer tells and intact dialogue and had nothing to say about a rewrite
    # gutting the description. The engine paid for a second call to make the
    # prose worse.
    #
    # The detection stays as a NON-BLOCKING warning, exactly as content-reuse
    # is handled above: drift stays visible for review without costing a call.
    for _tell in _craft_tells(out.get("prose", "")):
        warnings.append(f"craft: {_tell}")

    ctx.warnings.extend(warnings)
    if fidelity_warnings:
        ctx.warnings.extend(fidelity_warnings)
        # ctx.warnings is accumulated pipeline-wide but never surfaced
        # anywhere (not streamed, not persisted, not logged) -- see
        # AGENTS.md's safe-change workflow: attach directly to this
        # step's own saved output so a content-fidelity failure is at
        # least visible in the step/variant inspector instead of
        # vanishing silently.
        out["fidelity_warnings"] = fidelity_warnings

    if pending_person_writes:
        out["narration_person_writes"] = pending_person_writes
    # Reported, not removed -- see `_report_prose_guards`.
    _echo_notes = []
    out["prose"] = _report_prose_guards(
        out.get("prose", ""), view, p_lines, ctx.input, _echo_notes)
    if _echo_notes:
        ctx.warnings.extend(_echo_notes)
        out.setdefault("fidelity_warnings", []).extend(_echo_notes)
    return out


def _report_prose_guards(prose, view, p_lines, raw_input, warnings):
    """Say what the deterministic rewrites WOULD have changed, and change none.

    Four readings used to edit accepted narration on its way to the page:
    a player-echo strip, a raw-input echo strip, a within-view sentence
    dedupe, and a repeated-quote cap. Each was a code-based judgment that the
    model's prose was wrong, applied silently and unrecoverably -- the reader
    never saw what was removed, and neither did the record.

    They are detection now. Every rule they enforce is already in the
    narrator prompt, so what survives here is the measurement of whether the
    prompt worked, which is the same disposition the craft rewrite got and
    for the same reason: a warning costs nothing and a rewrite costs a page.
    """
    text = str(prose or "")
    checks = (
        ("echoed the player's own line",
         lambda: _strip_player_echo(
             text, p_lines,
             protect_quotes=_protected_view_quotes(view, p_lines))),
        ("echoed the player's raw input",
         lambda: _strip_raw_player_input_echo(text, raw_input)),
        ("repeated a sentence within one view",
         lambda: _dedupe_view_sentences(text)),
        ("repeated a quotation past the cap",
         lambda: _cap_repeated_quotes(text, view, exclude_bodies=p_lines)),
    )
    for label, run in checks:
        try:
            if str(run() or "") != text:
                warnings.append("narration: %s (reported, not removed)" % label)
        except Exception:
            # Detection may never cost the beat it is only describing.
            continue
    return text


def _extra_view_label(chat_id, extra, cast):
    """One extra seat's identity floor: `name -> what THIS player may call
    them`, the same `_speaker_display` gate `narrator` builds for the
    primary. A second human sits behind their own `known` row."""
    recognized = set(
        (wget(chat_id, "known", {}) or {}).get(extra.get("name")) or [])
    info = {}
    for row in (cast or []):
        try:
            sheet = json.loads(row["sheet"])
        except Exception:
            continue
        info[character_name(sheet)] = (
            character_appearance(sheet), character_scene_keys(sheet)[1:])

    def label(name):
        appearance, aliases = info.get(str(name), (None, None))
        return _speaker_display(name, recognized, appearance, aliases)

    return label


def narrator_extra(ctx, nonce):
    """Renders one prose view per additional human player declaring in this
    beat (ctx.extra_players), mirroring narrator() above but keyed by
    persona_id rather than hardcoded to the single primary player. A
    deliberately separate function rather than a refactor of narrator()
    itself -- narrator() is exercised by every existing single-player chat,
    and this only ever runs when ctx.extra_players is non-empty, so it
    can't regress anything by construction.
    """
    if not ctx.extra_players:
        return {}

    chat = ctx.chat
    est = ctx.turn["idx"] == 0          # see narrator() above
    # ONE STORY, ONE TENSE -- see the payload note in render_one. The
    # fallback is read off the PRIMARY seat's narration, which is the story's
    # own page; resolving it per seat would give two humans two tenses on the
    # beat where their own recent prose happened to disagree.
    _, _primary_prev = _past_narration_block(
        chat["id"], ctx.turn["idx"], ctx.turn["frame_id"], _PREV_PROSE_TURNS)
    story_tense = _resolve_narration_tense(chat["id"], _primary_prev)
    outcome_views = (ctx.get("perception_outcome", {}) or {}).get("views") or {}
    establish_views = (ctx.get("perception_establish", {}) or {}).get("views") or {}
    di = ctx.get("director_interpret") or {}
    other_players = di.get("other_players") or {}

    # Frame-filtered -- see the matching comment in narrator() above. The
    # block itself is assembled per persona inside render_one, because each
    # seat reads its own inputs and its own prose.
    try:
        _depth = int(get_setting("narrator_history_turns")
                     or _PAST_NARRATION_TURNS)
    except (TypeError, ValueError):
        _depth = _PAST_NARRATION_TURNS

    def render_one(extra):
        pid = extra["persona_id"]
        pid_key = str(pid)
        entry = other_players.get(pid_key) or {}
        p_lines = player_speech_lines(entry)

        view = (establish_views.get(f"extra:{pid_key}") if est else
                outcome_views.get(f"extra:{pid_key}")) \
            or "Nothing in particular reaches you this beat."

        past_narration, prev = _past_narration_extra_block(
            chat["id"], ctx.turn["idx"], ctx.turn["frame_id"], pid, _depth)

        player_declared = _narrator_player_declared(entry)

        # Deferred to commit exactly like narrator() above -- each pending
        # write rides this persona's own returned entry.
        pending_person_writes = {}
        narration_person = _resolve_narration_person(
            chat["id"], extra.get("input") or "", extra.get("name"),
            extra.get("pronouns") or {}, key=f"narration_person:extra:{pid}",
            pending=pending_person_writes,
            # THIS seat's own guide, and the story both seats are in. Person
            # is per-seat because each human writes their own way, and the
            # seed for a seat with nothing yet is that seat's author.
            voice_setting=persona_voice_setting(extra.get("persona") or {}),
            scenario=chat.get("scenario") or "")

        # THIS player's persona and THIS player's name. `player_name` was a
        # free variable here -- bound in `narrator`, never in `narrator_extra`
        # -- so every extra-player render raised NameError the moment a chat
        # had a second human in it. And the persona it reached for was the
        # chat's PRIMARY one, which would have filed the main player's
        # authored anatomy under the extra player's name: the same defect
        # `_authored_body_parts` exists to prevent, one player over.
        _abp2 = _authored_body_parts(
            ctx, extra.get("persona"), extra.get("name") or "Player")
        # Absent when empty -- see the note in narrator() above.
        # `private_voice_setting` is gone from this seat entirely rather
        # than emitted blank: it was a hardcoded "", which is not "this
        # player has no voice setting" but "this stage never looked", and
        # a field that always arrives empty teaches the model to skip the
        # key rather than to read it.
        _exemplars2 = json.loads(get_setting("exemplars") or "[]")
        _overused2 = _overused_phrases(prev, forced=view)
        _established2 = _already_established_phrases(view, prev)
        # Same order as narrator() above, and for the same reason -- see the
        # ORDER IS THE MESSAGE comment there. This seat has no
        # `current_events` package: `_ordered_beat_events` reads the PRIMARY
        # player's declaration and view to build the record, and there is no
        # per-seat equivalent yet, so an extra player still writes from the
        # view alone. That gap is this stage's, not the design's.
        payload = {
            "narration_person": narration_person,
            # One story, one tense. Person is per-seat because each human
            # writes their own way; tense is the AUTHOR's dial for the whole
            # page, so every seat reads the same chat-level value -- two
            # players reading the same story in different tenses is not a
            # preference, it is a defect.
            **({"narration_tense": story_tense} if story_tense else {}),
            "player_name": extra.get("name") or "Player",
            "player_pronouns": extra.get("pronouns") or {},
            # Keyed by what THIS seat's view called each body, from this
            # seat's own recognition ledger -- see `_cast_pronouns`. A
            # second human is a second observer, not a second reader of the
            # primary's gate.
            "cast_pronouns": _cast_pronouns(
                ctx.cast, label=_extra_view_label(chat["id"], extra, ctx.cast)),
            "scene_opening": bool(est),
            **({"authored_body_parts": _abp2} if _abp2 else {}),
            "player_declared": player_declared,

            **({"exemplars": _exemplars2} if _exemplars2 else {}),
            **({"overused_phrases": _overused2} if _overused2 else {}),
            **({"already_established_phrases": _established2} if _established2
               else {}),

            "spatial_frame": spatial_digest(
                ctx.get("outcome_scene") or get_scene(chat["id"], chat),
                extra.get("name") or "",
                label_for=_extra_view_label(chat["id"], extra, ctx.cast)),

            "past_narration": past_narration,
            "current_narration": (extra.get("input") or "").strip(),
            "present_scene": view,
            "variant_seed": nonce,
        }
        payload = _extension_narration_payload(
            ctx, payload, scope="narrator_extra",
            player=extra.get("name") or "")
        out, warnings, fidelity_warnings = _generate_narration(
            payload, view, prev, p_lines, language=ctx.language)

        # No correction re-call -- see the note in narrator().
        if fidelity_warnings:
            out["fidelity_warnings"] = fidelity_warnings

        if pending_person_writes:
            out["narration_person_writes"] = pending_person_writes
        # Reported, not removed -- see `_report_prose_guards`.
        out["prose"] = _report_prose_guards(
            out.get("prose", ""), view, p_lines, extra.get("input"),
            warnings)
        return pid_key, out, warnings, fidelity_warnings

    # Each extra player's narration only reads data already computed before
    # this step runs (director_interpret/perception_outcome) and never reads
    # another extra player's own output -- genuinely independent work, same
    # as the mapping+perception_act pairing elsewhere in the pipeline. Each
    # render_one only READS its own distinct per-persona world key
    # (narration_person:extra:<pid>); the corresponding write is recorded on
    # that persona's returned entry and applied at commit, so concurrent
    # execution is safe;
    # ctx.warnings mutation is deferred to the main thread below rather than
    # done inside each worker, avoiding any concurrent-list-mutation risk.
    #
    # context.run(...) below is load-bearing, not decoration:
    # ThreadPoolExecutor workers do NOT inherit the submitting thread's
    # contextvars the way agents/runtime.py's own bespoke thread-spawning
    # helpers (_stream_one/_stream_parallel) do -- those explicitly
    # contextvars.copy_context() before starting each thread. Without this,
    # providers.cancel_event/token_sink (set by the step-level worker
    # thread that's currently running this whole narrator_extra call)
    # would read back as their thread-default None inside render_one,
    # silently making an in-flight abort unable to interrupt these calls
    # and dropping their streamed tokens from the event bus.
    # A fresh copy per job, not one copy shared across jobs -- a single
    # Context object cannot be entered by more than one thread at once
    # (contextvars.Context.run raises RuntimeError if already running
    # elsewhere), and these jobs run concurrently on the pool.
    jobs = [
        (lambda extra=extra, cv=contextvars.copy_context(): cv.run(render_one, extra))
        for extra in ctx.extra_players
    ]
    results = {}
    with ThreadPoolExecutor(max_workers=max(1, len(ctx.extra_players))) as pool:
        for pid_key, out, warnings, fidelity_warnings in pool.map(lambda f: f(), jobs):
            ctx.warnings.extend(warnings)
            if fidelity_warnings:
                ctx.warnings.extend(fidelity_warnings)
            results[pid_key] = out

    return results
