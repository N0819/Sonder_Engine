"""The outcome beat as one ordered stream and the signs placed in it: settled
declarations, causal spans and restored lines, the world-ordered stream,
unanswered addresses, background beats, and the tell/demeanor manifest gated
per observer with its cue slots.

Carved verbatim from `agents/perception.py` on 2026-11-01;
`agents/perception.py` is now a facade that re-exports every name defined
here (docs/design/DESIGN_MODULE_LAYOUT.md).
"""

from __future__ import annotations

import json
import re
from story.character_schema import (
    character_name,
    character_senses,
    normalized_character_of_row,
    persona_senses,
)
from core.db import wget
from world.beat_ledger import beat_event_order
from story.scene import is_player_speaker
from mind import affect
from world.spatial import (
    visual_level_between,
    hear_level,
    room_of,
    same_subject,
    spatial_rel_between,
)
from . import composer
from .common import (
    _recognizes,
    _quote_body,
    adjudicated_player_action_text,
    communication_surface,
    observable_action_text,
    sequence_event_allowed,
    _merge_character_results,
)

from agents.perception_senses import (
    _behind_sources,
    _focus_target,
    _sense_card,
)
from agents.perception_scrub import _composer_scrub_surface


def _settled_character_result(ctx, character_id):
    """One character's declarations across both behaviour paths.

    A contested beat runs ``reaction_loop`` instead of the ordinary
    interaction path. Dialogue projection already read both result maps, but
    action/source projection read only ``character_results``. The result was
    a particularly dangerous half-delivery: a reacting character's line could
    reach an observer while the physical act beside it vanished, leaving the
    narrator to guess the missing motion from older prose.

    Reaction comes first because an interaction result, when one exists, is a
    later declaration in the beat. The shared merger preserves both ordered
    sequences and the accumulating update fields.
    """
    return _merge_character_results(
        (getattr(ctx, "reaction_results", None) or {}).get(character_id),
        (getattr(ctx, "character_results", None) or {}).get(character_id),
    ) or {}


def _restrict_causal_concealment(event, source):
    """Preserve both exclusions; an empty concealed audience excludes all."""
    hidden = [row for row in (event, source) if row.get("visibility") == "concealed"]
    if hidden:
        audience = [] if any(not row.get("conceal_from") for row in hidden) else list(
            dict.fromkeys(value for row in hidden for value in row["conceal_from"]))
        event.update(visibility="concealed", conceal_from=audience)


def _causal_outcome_sequences(ctx, interp, res, player_name, sequences, cast_names):
    """Use resolved causal spans without turning their accounts into percepts.

    A declaration may resolve into several events, all citing the same input.
    Keep each span's own outward surface and private time coordinate, while
    carrying the declaration's concealment and causal-floor restrictions.
    """
    from .director_evidence import beat_timeline, declared_elements
    declarations = [{"sequence": sequence} for _, sequence, _ in sequences]
    declared = declared_elements(interp, declarations)
    identities = {f"character:{key}": name for key, name in cast_names.items()}
    identities["persona:primary"] = player_name
    chat = ctx.get("chat") or {}
    if chat.get("persona_id") is not None:
        identities[f"persona:{chat['persona_id']}"] = player_name
    players = {str(player_name).casefold()}
    for player in ctx.extra_players:
        name = player.get("name") or "Player"
        identities[f"persona:{player['persona_id']}"] = name
        players.add(str(name).casefold())
    owner = {str(event.get("event_id")): actor
             for actor, sequence, _ in sequences for event in sequence
             if isinstance(event, dict) and event.get("event_id")}
    result = []
    for row in beat_timeline(res, interp, declarations, identity_index=identities):
        event = dict(row["element"])
        source_id = str(event.get("from_declaration") or "")
        source = declared.get(source_id) or event
        if not sequence_event_allowed(source, res) or not sequence_event_allowed(event, res):
            continue
        actor = str(row.get("actor") or owner.get(source_id) or "")
        if actor.startswith(("persona:", "character:")) and source_id in owner:
            actor = owner[source_id]
        for field in ("phase", "phase_id", "depends_on", "participants",
                      "requires_contacts", "referents"):
            if field in source:
                event.setdefault(field, source[field])
        _restrict_causal_concealment(event, source)
        # The Director may split an action, but cannot give an entirely
        # private declaration an outward surface that it never had.
        if source.get("type") == "action" and source.get("observable") == "":
            event["observable"] = ""
        stage, span = row["event_key"]
        event["_causal_span"] = (stage, span)
        event["_ledger_citation"] = row.get("citation") or ""
        event["_causal_resolved"] = stage == "resolve"
        event["event_id"] = f"{stage}:{span}"
        result.append((actor, [event], actor.casefold() in players))
    return _restore_declared_lines(result, sequences, res)


def _restore_declared_lines(result, sequences, res):
    """A line its speaker declared before an act is said before that act.

    The resolved rows replace the declarations here, and a line the author
    did not carry -- its prose dropped it, so no row cites it -- reached the
    stream only as unbound dialogue, appended after the whole beat
    (`_outcome_event_stream`) and graded in the world the beat ENDED in. The
    rows still cite the speaker's own later elements, so where the line was
    said is not a guess: it goes back immediately before the first row citing
    anything its declaration put after it, in that row's before-world.

    Measured (scratch story 165, turn 4581, 2026-10-07): Hester declared three
    lines and then "crosses the taproom, lifts the door latch, and stands
    half-turned back toward the fire". The resolve prose dropped the lines and
    walked her out through the door; appended after that exit, all three were
    graded from the Main Walk through a shut plank door, and the player got
    "Hester Gale says something you cannot make out: ...somebody's...
    Nobody's... changes --". `beat_movement_cuts` could not save them: she
    went in at interpret and out at resolve, so the two snapshots show no move
    at all (its docstring's known residual).

    Only a declaration's own lines, and only where a later element of the same
    declaration was resolved: a line with nothing resolved after it keeps the
    end of the beat, and a human's lines are the onset rows themselves.
    """
    at_citation = {}
    for index, (_actor, events, _player) in enumerate(result):
        for event in events:
            cited = str(event.get("from_declaration") or "").strip()
            if cited:
                at_citation.setdefault(cited, index)
    before = {}
    for actor, sequence, is_player in sequences:
        if is_player:
            continue
        elements = [e for e in sequence or () if isinstance(e, dict)]
        ids = [str(e.get("event_id") or "").strip() for e in elements]
        for position, element in enumerate(elements):
            own = ids[position]
            if (element.get("type") != "speech" or not element.get("text")
                    or not own or own in at_citation):
                continue
            later = [at_citation[i] for i in ids[position + 1:]
                     if i in at_citation]
            if not later or not sequence_event_allowed(element, res):
                continue
            at = min(later)
            anchor = result[at][1][0]
            before.setdefault(at, []).append((actor, [dict(
                element, _causal_span=anchor.get("_causal_span"))], is_player))
    if not before:
        return result
    out = []
    for index, entry in enumerate(result):
        out.extend(before.get(index, ()))
        out.append(entry)
    return out


def _line_words(text):
    """A spoken line's identity: its words, in order, case folded.

    The author quotes a line with the punctuation its speech tag wants --
    `"Aye. Keep your eyes open down there," he said` -- and the dialogue log
    stores the line as spoken, ending "." Compared as text, the two were two
    lines: none of four bound on the playerless Aldermill run (round 7,
    2026-09-23, idx 9), so each was appended after the beat's own stream,
    past the listener's walk out of the square, and graded from the room she
    ended in. A line split around its tag and joined by the encoder differs
    in its middle punctuation the same way."""
    return " ".join(re.findall(r"\w+", _quote_body(str(text or "")).casefold()))


def _outcome_event_stream(ctx, scene, interp, res, player_name,
                          dialogue, background_beats):
    """One causally ordered speech/action stream for outcome perception.

    `dialogue_log` is the authority for which lines were actually delivered,
    but it is not a sufficient chronology: a Director can group or reorder
    its transcription, and it contains no physical actions at all.  The
    declarations carry the original interleaving.  Bind each declared speech
    element back to its exact dialogue row, keep each observable action beside
    it, then append only genuinely unbound dialogue/background events.

    Current causal output supplies the resolved spans instead of the original
    declarations, which may each contain several events. Their individual
    outward forms and before-span worlds survive that decomposition.

    This is deliberately still pre-perceiver.  Concealment, sight, hearing,
    containment and identity remain per-observer decisions in the loop that
    consumes the stream.
    """
    sequences = [(player_name, interp.get("sequence") or [], True)]

    # Additional human declarations happen in the same opening causal band as
    # the primary player's declaration. Their own sequence remains intact.
    other_players = interp.get("other_players") or {}
    for extra in ctx.extra_players:
        entry = other_players.get(str(extra.get("persona_id"))) or {}
        sequences.append((extra.get("name") or "Player",
                          entry.get("sequence") or [], True))

    cast_names = {}
    for row in ctx.cast:
        sheet = normalized_character_of_row(row)
        if sheet is None:
            continue
        try:
            cast_names[int(row["id"])] = character_name(sheet)
        except (KeyError, TypeError, ValueError):
            continue

    represented_ids = set()
    for stage_name in ("reaction_loop", "interaction_loop"):
        stage = ctx.get(stage_name) or {}
        for round_data in stage.get("rounds") or []:
            if not isinstance(round_data, dict):
                continue
            raw_id = (round_data.get("reactor_id")
                      if stage_name == "reaction_loop"
                      else round_data.get("speaker_id"))
            try:
                char_id = int(raw_id)
            except (TypeError, ValueError):
                char_id = None
            if char_id is not None:
                represented_ids.add(char_id)
            actor = (round_data.get("reactor") or round_data.get("speaker")
                     or cast_names.get(char_id))
            if actor and char_id is not None:
                cast_names.setdefault(char_id, str(actor))
            result = round_data.get("result") or {}
            if actor and isinstance(result, dict):
                sequences.append((str(actor), result.get("sequence") or [],
                                  False))

    # Resume and focused tests can hydrate the result maps without hydrating
    # round records. Preserve those declarations once, after any real rounds.
    for row in ctx.cast:
        try:
            char_id = int(row["id"])
        except (KeyError, TypeError, ValueError):
            continue
        if char_id in represented_ids:
            continue
        result = _settled_character_result(ctx, char_id)
        if result.get("sequence"):
            sequences.append((cast_names.get(char_id) or str(char_id),
                              result["sequence"], False))

    # An onscreen charter body's own declaration (`declare_charter_figures`),
    # resolved by the Director like a character's; its acts and lines carry
    # their own phase ids, so the dispositions and the cut machinery read
    # them exactly as they read a character's.
    for figure in ((res or {}).get("charter_declarations") or []):
        if isinstance(figure, dict) and figure.get("sequence"):
            sequences.append((str(figure.get("name") or ""),
                              figure["sequence"], False))

    declaration_sequences = sequences
    causal = any((output or {}).get("ledgers") or (output or {}).get("causal_ledger")
                 for output in (interp, res))
    if causal:
        sequences = _causal_outcome_sequences(
            ctx, interp, res, player_name, sequences, cast_names)

    def _same_speaker(actual, declared, is_player):
        if (is_player
                and str(declared or "").strip().casefold()
                == str(player_name or "").strip().casefold()
                and is_player_speaker(actual, ctx.chat)):
            return True
        return same_subject(scene, actual, declared) or (
            str(actual or "").strip().casefold()
            == str(declared or "").strip().casefold())

    used_dialogue = set()
    seen_events = set()
    stream = []
    deferred_stream = []
    for actor, sequence, is_player in sequences:
        for local_index, event in enumerate(sequence):
            if not isinstance(event, dict):
                continue
            event_key = str(event.get("event_id") or "").strip()
            if not event_key:
                event_key = json.dumps(
                    [actor, local_index, event], sort_keys=True,
                    ensure_ascii=False, default=str)
            if event_key in seen_events:
                continue
            seen_events.add(event_key)
            if not sequence_event_allowed(event, res):
                continue
            _deferred = bool(
                is_player and (event.get("depends_on") or
                               str(event.get("phase") or "").casefold() in (
                                   "continuation", "completion")))
            destination = deferred_stream if _deferred else stream
            # WHICH DECLARATION THIS ENTRY IS, kept on the entry itself.
            # The world's ledger cites declarations, so this is the join that
            # lets it order a stream assembled out of several of them. Only a
            # real phase id is carried -- `event_key` falls back to a JSON
            # blob for an element that has none, and a blob is a dedup key,
            # not an identity the world could ever name.
            declared_id = str(event.get("_ledger_citation", event.get("event_id")) or "").strip()
            if event.get("type") == "speech" and event.get("text"):
                wanted = _line_words(event.get("text"))
                match = next((
                    index for index, entry in enumerate(dialogue)
                    if index not in used_dialogue
                    and _same_speaker(entry.get("speaker"), actor, is_player)
                    and _line_words(entry.get("exact_quote")) == wanted
                ), None)
                if match is not None:
                    used_dialogue.add(match)
                    line = dialogue[match]
                    if causal:
                        line = dict(line)
                        _restrict_causal_concealment(line, event)
                    destination.append({"kind": "speech",
                                        "declared": declared_id,
                                        "causal_span": event.get("_causal_span"),
                                        "deferred": _deferred,
                                        "entry": line})
            elif (event.get("type") == "communication"
                  and communication_surface(event)):
                destination.append({
                    "kind": "communication", "actor": actor,
                    "declared": declared_id, "deferred": _deferred,
                    "causal_span": event.get("_causal_span"),
                    "entry": {**event, "speaker": actor},
                })
            elif (event.get("type") == "action"
                  and event.get("visibility") != "concealed"):
                surface = (adjudicated_player_action_text(event, res)
                           if is_player and not event.get("_causal_resolved")
                           else observable_action_text(event))
                if surface:
                    destination.append({
                        "kind": "action", "actor": actor,
                        "declared": declared_id, "deferred": _deferred,
                        "causal_span": event.get("_causal_span"),
                        "attempt": surface, "event": event})

    # A dependent player phase occurs only after present minds had the chance
    # to answer its prerequisite.  Character declarations were appended while
    # the main stream was built, so placing continuations here creates the
    # causal sandwich: onset -> response -> continuation/completion.
    stream.extend(deferred_stream)

    # A Director-originated/background line has no character declaration to
    # bind. Preserve it in dialogue-log order after the declared stream.
    for index, entry in enumerate(dialogue):
        if index not in used_dialogue:
            stream.append({"kind": "speech", "entry": entry})

    for beat in background_beats:
        if not beat.get("action") or not beat.get("room"):
            continue
        stream.append({
            "kind": "action", "actor": beat["name"],
            "attempt": beat["action"],
            "event": {"actor": beat["name"],
                      "observable": beat["action"],
                      "visibility": "overt",
                      "event_id": "background:%s" % beat["name"]},
        })
    stream.extend(_unanswered_addresses(scene, declaration_sequences, stream, res))
    # Causal spans already use the same chronology as the world's writer.
    # Reordering by a shared declaration id would collapse that chronology.
    return stream if causal else _world_ordered_stream(scene, ctx, stream)


def _world_ordered_stream(scene, ctx, stream):
    """The beat's stream, in the order the WORLD says the beat happened.

    "perception should only be reading the world." The stream above is
    assembled out of several separate declarations -- the player's, then each
    character's, then the lines that bound to none of them -- and concatenating
    them is a GUESS at chronology: it puts everything the player did before
    anything anyone else did, whatever actually happened. Live, that is a
    player who speaks, walks out and is answered, rendered as though the answer
    came before he left.

    The Director's author writes the beat as ONE ordered list ("one element
    for EVERYTHING that happened, in the order it happened"), the recompiler
    reassembles it, and `world/beat_ledger.py` keeps it. So the world can say
    what the concatenation could only guess, and this asks it.

    IT ONLY EVER REORDERS WHAT THE WORLD NAMES, AND NOTHING ELSE MOVES. The
    named entries are permuted among the slots they already occupy; an entry
    the ledger does not cite keeps its exact index. That matters in one
    direction in particular: an unbound dialogue row, a background presence's
    beat and a silence minted for an unanswered address are appended AFTER the
    whole declared stream deliberately, and the first rule tried here --
    anchoring an unnamed entry to the last named one before it -- dragged all
    three into the middle of the beat the moment that neighbour moved earlier.
    Holding every unnamed entry still cannot do that. A ledger that names
    nothing changes nothing; a ledger that names half the beat reorders that
    half and leaves the rest exactly where the declarations put it.
    """
    # `PipelineContext.__getattr__` raises KeyError rather than
    # AttributeError, so `getattr(ctx, "turn", None)` does NOT shield a
    # context without one -- a focused test's stub, or a resume that
    # hydrated no turn. Caught by the suite, not by reading it.
    try:
        turn_idx = ctx.turn.idx
    except (AttributeError, KeyError, TypeError):
        return stream
    order = beat_event_order(scene, turn_idx)
    if len(stream) < 2 or not order:
        return stream
    # THE DETERMINISTIC FLOOR OUTRANKS THE WORLD'S ORDER, and this is the one
    # place the two can disagree. A dependent player phase was DEFERRED above
    # so the beat reads onset -> response -> continuation, off the player's
    # own `depends_on`/`phase` -- a causal invariant the engine enforces,
    # where the ledger is a model's account of what happened. Measured: the
    # long-beat run's turn 1 listed all eleven of the player's acts before any
    # character's, which would pull a continuation back in front of the answer
    # it waits for. So a deferred entry keeps the index the floor gave it, and
    # everything else permutes among the slots around it: the world still
    # fixes the order of everything the floor has no opinion about, and can
    # never invert the one thing it does.
    slots = [index for index, entry in enumerate(stream)
             if isinstance(entry, dict)
             and str(entry.get("declared") or "") in order
             and not entry.get("deferred")]
    if len(slots) < 2:
        return stream
    ranked = sorted(slots, key=lambda index: (
        order[str(stream[index].get("declared") or "")], index))
    out = list(stream)
    for slot, source in zip(slots, ranked):
        out[slot] = stream[source]
    return out


def _unanswered_addresses(scene, sequences, stream, res):
    """The beat's addresses that got no answer, as stream entries (D6).

    A line spoken to somebody who says nothing back is an EVENT, and the
    engine had no channel for it at all: perception is built out of what
    arrived, and nothing arrives. So the page either let the beat pass as
    though nobody had been spoken to, or invented "no answer came" about a
    body that had in fact answered.

    Four conditions, and every one of them SUBTRACTS:

    * the addresser declared the line and named a target (`intended_target`
      -- their own declaration, so nothing here is inferred from the world);
    * the target WAS ASKED AND HAD THE BEAT TO ANSWER IN -- they declared a
      sequence of their own this beat. The dialogue log records what was
      SAID and never who was RUN, so it cannot tell "chose silence" from
      "was never asked to speak": `build_plan` plans character steps from
      `flow.reactors` alone, `addressed_to` only ORDERS the reactors it is
      given, and the interaction loop has a round budget. Without this
      condition a reactor the Director's pacing left out minted a refusal
      on the page every beat (measured: an empty context, where no
      character ran at all, yielded a silence for the target);
    * the line REACHED that target (`hear_level` above "none" over the
      beat's own relation), so an address nobody could hear is not read as
      a refusal to answer -- the honest reading of that beat is that the
      addresser does not know whether they were heard;
    * and NO VOICE OF THE TARGET'S IS ANYWHERE IN THIS BEAT'S STREAM. Every
      entry that carries a speaker counts, whatever channel carried it: an
      answer over a radio is an answer (measured -- an interaction_loop
      round whose sequence was a `communication` produced the stream
      `[('communication', 'Reya'), ('silence', 'Reya')]`, so the addresser's
      view carried Reya's answer and a sentence saying she gave none).

    The entry names the ADDRESSER as well as the target, because the fact
    belongs to the person who was listening for the answer: the per-observer
    loop mints a percept from it only into that observer's view. Anybody who
    speaks and names a target has that fact, player or character -- being
    ignored is a social event, and a character has a view for it to arrive
    in like anyone else. It states the fact and never the reason -- whether
    the target refused, was thinking, or answered somebody else is exactly
    the inference the beat is for.
    """
    # A VOICE THAT REACHED THE BEAT, however it travelled. Keyed off the
    # entry's own speaker rather than the entry's kind, so a channel added
    # later is counted the day it is added.
    spoke = [str((e.get("entry") or {}).get("speaker") or "").strip()
             for e in stream]
    spoke = [who for who in spoke if who]

    def answered(target):
        key = target.casefold()
        return any(who.casefold() == key or same_subject(scene, who, target)
                   for who in spoke)

    # WHO WAS RUN, under the spelling this beat's own declarations use. It
    # doubles as the canonicalisation the percept needs: an `intended_target`
    # spelled as an alias resolves to the body's own name here, which is what
    # `display_map` is keyed by, so the address does not pass every gate and
    # then silently mint nothing.
    declared = [str(actor) for actor, sequence, is_player in sequences
                if not is_player and actor and sequence]

    def body_asked(target):
        key = target.casefold()
        for who in declared:
            if who.casefold() == key or same_subject(scene, who, target):
                return who
        return None

    out, seen = [], set()
    for actor, sequence, _is_player in sequences:
        for event in sequence or ():
            if not isinstance(event, dict) or event.get("type") != "speech":
                continue
            if not str(event.get("text") or "").strip():
                continue
            if not sequence_event_allowed(event, res):
                continue                # the line was not spoken at all
            raw = event.get("intended_target")
            targets = raw if isinstance(raw, (list, tuple)) else [raw]
            for target in targets:
                target = str(target or "").strip()
                if not target or answered(target):
                    continue
                body = body_asked(target)
                if body is None:
                    # Nobody who ran this beat: an address to a body the
                    # Director never gave a turn to, or to a name nothing
                    # answers to. Neither is a refusal.
                    continue
                if room_of(scene, body) is None:
                    # No body the scene can place: a bodiless voice, a name
                    # nobody answers to. There is no relation to grade the
                    # delivery over, so there is no evidence they heard.
                    continue
                if same_subject(scene, body, actor):
                    continue
                key = (str(actor).casefold(), body.casefold())
                if key in seen:
                    continue
                rel = spatial_rel_between(scene, body, actor)
                # `addressed`: this body is the line's own target, so a line
                # breathed into its ear reaches it (`EAR_VOLUME`).
                if hear_level(rel, event.get("volume", "normal"),
                              addressed=True) == "none":
                    continue            # they never heard it: not an answer
                seen.add(key)
                out.append({"kind": "silence", "actor": body,
                            "addresser": str(actor)})
    return out


def _tell_acuity(sheet):
    """Numeric visual/auditory acuity for physical-tell delivery, ranked on
    the scale a tell's subtlety is graded on: an ordinary eye reaches
    "noticeable" (0.4), a keen one "subtle" (0.65), an exceptional one
    "hidden" (0.9) -- see `affect.TELL_ADVANTAGE`."""
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


#: THE SENSE A TELL ARRIVES BY -- the one question `manifest.tells[].channel`
#: answers. It is not the body part the cue shows in: that is the cue's own
#: text ("a hand that goes still on the glass"), and nothing in the engine has
#: ever read `channel` for anything but the reachability branch below.
#:
#: The sheet used to offer `face|eyes|voice|hands|posture|breath` -- six BODY
#: REGIONS against a two-way SENSE branch, four of them sight-only. The field's
#: own published vocabulary therefore made the concealing answer the likely
#: one: a swallow, a shifted weight, a hand drumming the table are all things
#: a mind in the dark catches, and each was lost, because the natural word for
#: the cue was a body part and every body part but two read as sight.
TELL_CHANNELS = ("seen", "heard")

#: The spellings that answer "heard". `voice` and `breath` are the two the
#: sheet published before `heard` existed and are what every stored manifest
#: carries, so they stay members rather than becoming unrecognised words on a
#: rerun-from-stage or a replayed variant.
_AUDIBLE_TELL_CHANNELS = frozenset({"heard", "voice", "breath"})


def tell_is_audible(channel) -> bool:
    """Does a tell on this channel reach an observer who cannot see.

    SIGHT-ONLY REMAINS THE ANSWER FOR A WORD THE ENGINE CANNOT VOUCH FOR, and
    that direction is not the defect above -- it is the firewall. Granting
    hearing to an unrecognised channel would hand "a glance at the door" to a
    blind observer, and nothing deciding who perceives what may depend on the
    character model choosing a good word. The fix for the losses is upstream,
    in what the sheet ASKS for: a field whose vocabulary is the sense has a
    correct answer available to write, one whose vocabulary is six body parts
    does not.
    """
    return str(channel or "").strip().casefold() in _AUDIBLE_TELL_CHANNELS


def _delivered_manifest(ctx, scene, observer, sources, known, cast_by_name,
                        observer_sheet=None):
    """Per SOURCE this observer can read: {surface_demeanor, cues:[cue,...]} --
    the interior-depth payoff (Phase 4). A character's `manifest` (surface
    demeanor + physical tells) is authored by that character; the ENGINE decides
    which cues reach THIS observer here, before the LLM call, exactly like the
    dialogue-injection backstop. A tell is delivered iff (a) the observer can
    receive its channel -- sight reaches any tell (same-visual-channel, not in
    the rear blind spot), and a tell `tell_is_audible` recognises also reaches
    a listener who cannot see it happen -- AND (b) affect.tell_gate: subtlety
    <= acuity + familiarity + attention, where knowing the source and watching
    it are each worth one grade (`affect.TELL_ADVANTAGE`) and worth nothing
    when absent. MEANING and the character's own labels never cross; only the
    observable cue text does -- with, beside it (`cue_at`), the event id of
    the source's own step the read-back said it shows at, which orders the
    cue and is never rendered (`_cue_slots`)."""
    out = {}
    focus = _focus_target(scene, observer)
    behind = set(_behind_sources(scene, observer, sources))
    o_room = room_of(scene, observer)
    # HOW WELL THIS OBSERVER SEES AND HEARS IS A FACT ABOUT THE OBSERVER: it
    # cannot differ between two sources, and reading it inside the loop
    # normalized the observer's own card once per source (review 2026-09-07
    # C20 -- 7 reads for one observer's 8 sources, and it is per observer per
    # beat, so it grew as N x M). Resolved on the first source that has a
    # tell to gate, so a beat where nobody declared one still reads nothing.
    acuity = None
    for s in sources:
        sname = s.get("name")
        cid = cast_by_name.get(sname) if sname else None
        if not sname or sname == observer or cid is None:
            continue
        # Both behaviour paths: a reaction-phase declarer's carriage and tells
        # were never delivered, while its lines and acts were (UNBUILT
        # CHARACTERS §6.18; reachable more often since the acted-upon widening
        # sends a contested act's target through the reaction phase).
        manifest = (_settled_character_result(ctx, cid) or {}).get("manifest") or {}
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
        visible = (visual_level_between(scene, observer, sname,
                                        _sense_card(observer_sheet)) != "none"
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
        familiarity = affect.TELL_ADVANTAGE if (
            observer in (known.get(sname) or [])
            or sname in (known.get(observer) or [])) else 0.0
        attention = affect.TELL_ADVANTAGE if focus == sname else 0.0
        cues, cue_at = [], []
        if tells and acuity is None:
            acuity = _tell_acuity(observer_sheet)
        for t in tells:
            reachable = visible or (audible
                                    and tell_is_audible(t.get("channel")))
            if reachable and affect.tell_gate(t, acuity, familiarity, attention):
                cues.append(t.get("cue"))
                cue_at.append(str(t.get("at_event") or ""))
        entry = {}
        if visible and demeanor:
            entry["surface_demeanor"] = demeanor
        if cues:
            entry["cues"] = cues
            if any(cue_at):
                entry["cue_at"] = cue_at
        if entry:
            out[sname] = entry
    return out


def _background_beats(ctx, scene):
    """Every background presence that spoke or ACTED this beat, each with the
    room it stands in. Cached per turn; empty when the stage did not fire.

    Two things were missing and they were the same thing. Only the presences
    carrying a `dialogue_log_entry` were collected, so an action-only reaction
    reached no observer at all -- it travelled to the narrator's `event_order`
    alone, which is the one delivery path that never asks whether the player
    could see it. And every presence collected was located with `cast_room`,
    which reaches a presence only through the entity table: it answers None
    for one the scene places nowhere, and for one whose name TWO entities
    answer to, where `room_of` refuses to pick (ambiguity resolves to
    nothing, and folding two beings into one is the worse error).

    A None room makes `spatial_rel_between` report "no known spatial channel",
    so this merge delivered nothing at all. Live in chat 78 t3, whose cell
    holds a guard at each of two corner stations under one name: the guard's
    line reached nobody while the narrator, on the same beat and from the same
    missing answer, rendered that guard's act as fact -- perception failing
    closed and the narrator's sight gate failing open.

    `presence_room` is the canonical resolver -- scene position, then entity
    id, then the sketch's station room -- and the background stage now records
    the room it actually voiced each presence at, which is preferred over
    re-deriving it here so the two cannot disagree.
    """
    cached = ctx.get("_background_beats_cache")
    if cached is not None:
        return cached
    br = ctx.get("background_react") or {}
    raw = br.get("reactions")
    if raw is None:                     # legacy single-entry shape
        raw = ([br] if br.get("fired")
               and (br.get("dialogue_log_entry") or br.get("action")) else [])
    # Local import: `persist.commit` reaches back into `agents.common` from
    # inside its own functions -- the same shape used for
    # `presence_has_an_identity` below.
    from persist.commit import presence_record_for, presence_room
    records = wget(ctx.chat["id"], "background_presences", {}) or {}
    beats = []
    for r in raw:
        if not isinstance(r, dict):
            continue
        entry = r.get("dialogue_log_entry")
        entry = entry if isinstance(entry, dict) else None
        name = str((entry or {}).get("speaker") or r.get("name") or "").strip()
        if not name:
            continue
        room = str(r.get("room") or "").strip() or presence_room(
            scene, name, presence_record_for(records, name, scene)[1] or {})
        beats.append({"name": name, "entry": entry, "room": room or None,
                      "action": str(r.get("action") or "").strip(),
                      # A CHORUS IS NOT A PERSON. `background._chorus_entry`
                      # answers an address to a crowd as one entry named by
                      # the crowd's composition ("cousins and mistress");
                      # carried so the outcome stage can deliver the act
                      # without treating the composition as an identity.
                      "chorus": bool(r.get("chorus"))})
    ctx["_background_beats_cache"] = beats
    return beats


def _manifest_percepts(sc, manifest, observer, display_map, recognized,
                       unknown, order, sense_card=None):
    """Tells and surface demeanor as percepts, from the manifest
    `_delivered_manifest` already gated for THIS observer (D1; review A36:
    computed per observer for 101 beats and read by nothing).

    What crosses is exactly what that gate let through -- the cue text and
    the demeanor -- named through the same display map every other percept
    uses, so a stranger's tell is a stranger's, and scrubbed through the
    same identity scrub an act surface gets. A body this observer was not
    shown (no display label, not recognised) names nothing and its tells
    are dropped: a tell is a thing SEEN OR HEARD on a body, and there is no
    body here to see it on. Returns (percepts, next order key).

    The outcome stage hands this only the cues `_cue_slots` could not place
    among the beat's events; the rest were minted where they showed."""
    out = []
    for sname, entry in (manifest or {}).items():
        if not isinstance(entry, dict) or same_subject(sc, sname, observer):
            continue
        label = _manifest_label(sname, display_map, recognized)
        if not label:
            continue
        can_see = visual_level_between(sc, observer, sname,
                                       sense_card) != "none"
        demeanor = _composer_scrub_surface(
            str(entry.get("surface_demeanor") or ""), observer, recognized,
            unknown, labels=display_map)
        percept = composer.demeanor_percept(sname, label, demeanor) \
            if demeanor and can_see else None
        if percept:
            out.append(percept)
        for cue in entry.get("cues") or []:
            percept = _cue_percept(sc, sname, cue, observer, display_map,
                                   recognized, unknown, order,
                                   sense_card=sense_card)
            if percept:
                out.append(percept)
                order += 1
    return out, order


def _manifest_label(sname, display_map, recognized):
    """This observer's label for a source's body, or None when it was not
    shown one (`_manifest_percepts`)."""
    label = display_map.get(sname)
    if label is None and _recognizes(sname, recognized):
        label = sname
    return label


def _cue_percept(sc, sname, cue, observer, display_map, recognized, unknown,
                 order, sense_card=None):
    """One delivered tell as THIS observer's percept, or None: named through
    the display map and scrubbed like an act surface, and nothing for a body
    this observer was not shown."""
    if same_subject(sc, sname, observer):
        return None
    label = _manifest_label(sname, display_map, recognized)
    if not label:
        return None
    can_see = visual_level_between(sc, observer, sname, sense_card) != "none"
    text = _composer_scrub_surface(str(cue or ""), observer, recognized,
                                   unknown, labels=display_map)
    return composer.cue_percept(sname, label, text, order_key=order,
                                can_see=can_see)


def _stream_actor(beat_event):
    """Whose own line or act one entry of the outcome stream is
    (`_outcome_event_stream`); "" for an entry that is nobody's conduct --
    a silence is news to the one who was waiting, not an act of the one
    who kept it."""
    kind = beat_event.get("kind") if isinstance(beat_event, dict) else None
    if kind == "speech":
        return str((beat_event.get("entry") or {}).get("speaker") or "")
    if kind in ("action", "communication"):
        return str(beat_event.get("actor") or "")
    return ""


def _cue_slots(sc, manifest, observer, beat_events):
    """WHERE IN THE BEAT EACH CUE THIS OBSERVER WAS DELIVERED GOES:
    `({stream index: [(source, cue)]}, the manifest less the cues placed)`.

    A cue goes just before the stream entry of the source's own step the
    read-back said it shows at (`cue_at`, that step's event id against the
    entry's `declared`; the first of them when the resolve cut the step into
    several spans). With no such entry -- no anchor, a sign that shows all
    through, a step this beat never resolved -- it goes just before the
    source's LAST line or act of the beat: inside its giver's conduct, and in
    the round the tells came from, since a mind's manifest is its latest
    round's (`_MERGE_LATEST_WINS_FIELDS`) while its lines and acts are every
    round's. Not after all of it -- except where the outcome stage finds
    the observer could not see the giver just before that step: a cue
    admitted on the end-of-beat relation goes after the beat then, where
    it was admitted (review of this placement, 2026-10-08).

    They used to be numbered after every event, so they were always the last
    records, and the narrator, told the order is absolute, ended the page on
    them -- 16 of 29 Brackwater pages (chat 166, 2026-10-07; 26 of 26 beats
    with a cue) -- even when the cue named an earlier moment ("at the coat
    question", "before the knock lands"). A source with no line or act in
    the stream keeps that place, as before: there is nothing of its own to
    stand beside."""
    slots, rest = {}, {}
    for sname, entry in (manifest or {}).items():
        if not isinstance(entry, dict):
            continue
        kept = {k: v for k, v in entry.items() if k not in ("cues", "cue_at")}
        cues = list(entry.get("cues") or [])
        at = list(entry.get("cue_at") or [])
        own = []
        if not same_subject(sc, sname, observer):
            folded = str(sname or "").strip().casefold()
            for index, beat_event in enumerate(beat_events or ()):
                actor = _stream_actor(beat_event)
                if actor and (actor.strip().casefold() == folded
                              or same_subject(sc, actor, sname)):
                    own.append(index)
        left = []
        for k, cue in enumerate(cues):
            anchor = str(at[k] if k < len(at) else "").strip()
            placed = [i for i in own if anchor and str(
                (beat_events[i] or {}).get("declared") or "").strip() == anchor]
            slot = placed[0] if placed else (own[-1] if own else None)
            if slot is None:
                left.append(cue)
            else:
                slots.setdefault(slot, []).append((sname, cue))
        if left:
            kept["cues"] = left
        if kept:
            rest[sname] = kept
    return slots, rest
