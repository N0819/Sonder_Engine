"""Deterministic micro-perception and multi-character reaction/dialogue loops."""

from __future__ import annotations

import json

from character_schema import (character_appearance, character_name,
                              character_name_from_text)
from db import wget
from scene import (
    NON_AWAKE_GATED,
    awareness_map,
    awareness_of,
    dialogue_config,
    get_scene,
    reaction_config,
)
from spatial import hear_level, proximity_rel, room_of, spatial_rel

from .character import _unanswered_question_note, character_step
from .common import (
    _append_micro_view,
    _asks_player,
    _character_by_id,
    _character_display_name,
    _conceal_from_targets_observer,
    _delivery_ok,
    _unknown_actor_label,
    character_room,
    _dict,
    _dict_list,
    _list,
    _merge_character_results,
    _next_speaker_candidates,
    _observable_predicate,
    _requires_director_resolution,
    observable_action_text,
    _sequence_has_content,
    normalize_character_refs,
)

def deterministic_micro_perception(ctx, actor_id, actor_result, scene):
    actor_row = _character_by_id(ctx, actor_id)
    actor_sheet = json.loads(actor_row["sheet"])
    actor_name = character_name(actor_sheet)
    actor_appearance = character_appearance(actor_sheet)
    # uid/alias-tolerant: a position keyed by identity.uid rather than the
    # display name must still resolve, else spatial_rel returns "unknown" and
    # same-room characters silently perceive nothing of each other.
    actor_room = character_room(scene, actor_sheet)
    # Same recognition gate as perception.py's injection paths: this
    # deterministic delivery used to attribute every micro-round line and
    # action to the actor's CANONICAL name with no "known" check at all, so
    # NPC-to-NPC rounds leaked identities between strangers -- and these
    # additions flow verbatim into subsequent character steps and the
    # outcome views. Quotes stay verbatim; only the attribution is gated.
    known = wget(ctx.chat.id, "known", {})
    # One awareness map for the whole sweep: awareness_of accepts a chat_id and
    # re-queries when given one, which inside this per-observer/per-event loop
    # is a query per event per observer.
    amap = awareness_map(ctx.chat.id)
    views = {}
    perceived_by = set()
    for row in ctx.cast:
        observer_id = int(row["id"])
        if observer_id == actor_id:
            continue
        observer_sheet = json.loads(row["sheet"])
        observer_name = character_name(observer_sheet)
        if actor_name in (known.get(observer_name) or []):
            display = actor_name
        else:
            display = _unknown_actor_label(actor_name, actor_appearance)
        observer_room = character_room(scene, observer_sheet)
        relation = spatial_rel(scene, actor_room, observer_room)
        observer_awareness = awareness_of(amap, observer_name)
        # F4: the micro-loop used to read bare hear_level with no proximity, so
        # a muttered aside landed full-volume on an arbitrarily large room.
        proximity = proximity_rel(scene, observer_name, actor_name)
        additions = []
        for event in actor_result.get("sequence") or []:
            if event.get("type") == "speech":
                # A concealed line is an absolute exclusion, not a volume: it
                # must never be delivered to an observer named in its
                # conceal_from, regardless of physical earshot. The action
                # branch below already skips concealed events; the speech
                # branch used to check ONLY hear_level, so a concealed NPC
                # line leaked verbatim to conceal-from parties (and thence
                # into their next character step, outcome view, and durable
                # memory). Legitimate recipients (anyone not concealed from)
                # still hear it, subject to hear_level -- mirroring
                # perception_act and the norm_sequence backstop.
                if (
                    event.get("visibility") == "concealed"
                    and _conceal_from_targets_observer(
                        event.get("conceal_from"),
                        observer_id,
                        observer_sheet,
                    )
                ):
                    continue
                volume = event.get("volume", "normal")
                if not _delivery_ok(relation, scene, observer_name, actor_name,
                                    "hearing", volume=volume,
                                    proximity=proximity,
                                    awareness=observer_awareness):
                    continue
                level = hear_level(relation, volume, proximity=proximity)
                quote = str(event.get("text") or "")
                if level == "full":
                    additions.append(f'{display} says: "{quote}"')
                else:
                    words = quote.split()
                    fragment = " ".join(
                        words[max(0, len(words) // 2):max(0, len(words) // 2) + 3])
                    additions.append(
                        f'You hear a muffled fragment from {display}: "...{fragment}..."')
                perceived_by.add(observer_id)
            elif event.get("type") == "action":
                if event.get("visibility") == "concealed":
                    continue
                if not _delivery_ok(relation, scene, observer_name, actor_name,
                                    "action", awareness=observer_awareness):
                    continue
                # Intent-free `observable` surface only -- never the raw
                # attempt (which carries the actor's purpose/intent). A mental
                # beat (observable "") is imperceptible and skipped. Composed via
                # the shared predicate helper so an actor-led / independent-clause
                # surface never double-names ('Dr. Moon Dr. Moon tilts...').
                surface = observable_action_text(event)
                sentence = _observable_predicate(display, surface) if surface else None
                if sentence:
                    additions.append(sentence)
                    perceived_by.add(observer_id)
        if additions:
            views[observer_id] = additions
    return views, perceived_by

def _drop_non_awake(ctx, reactor_ids):
    """Remove unconscious/asleep/sedated cast from a reactor list -- a non-awake
    mind neither perceives nor reacts. build_plan does the same before planning;
    both loops read flow.reactors independently, so they must gate too (a rerun
    that re-enters a loop with a stale plan is covered by the character_step
    guard as a final backstop)."""
    if not reactor_ids:
        return reactor_ids
    amap = awareness_map(ctx.chat.id)
    id_to_name = {c["id"]: character_name_from_text(c["sheet"]) for c in ctx.cast}
    return [rid for rid in reactor_ids
            if awareness_of(amap, id_to_name.get(rid, "")) not in NON_AWAKE_GATED]


def _defer_to_focus(queue_ids, tom_focus, already_spoke,
                    focus_deferred, calls, max_calls):
    """Re-queue this beat's focus character ahead of an early exit, or None to
    let the exit stand.

    Both of the interaction loop's early exits -- a declared act needing
    director resolution, and a question turned to the player -- end the beat
    immediately. Observed live (v3 run, turns 5 and 8): the character the beat
    was about, flagged by the Director in flow.tom_triggers and explicitly
    invited to answer BY ANOTHER CHARACTER in the same beat, was never called.
    The narrator then rendered the resulting absence as a deliberate silence
    ("He says nothing for a long moment") that no agent had chosen.

    The cost is not only dramatic: appraisal -- and therefore the goal_impacts
    drive strain accrues from -- exists only for characters that actually ran,
    so a drive could never build toward rupture on the very beats aimed at it.

    Granted at most once per beat: a focus character who themselves trigger an
    exit must not be able to hold the loop open.
    """
    if focus_deferred or calls >= max_calls:
        return None
    pending = [cid for cid in queue_ids
               if cid in tom_focus and cid not in already_spoke]
    if not pending:
        return None
    first = pending[0]
    return [first] + [cid for cid in queue_ids if cid != first]


def interaction_loop(ctx, nonce):
    config = dialogue_config(ctx.chat.id)

    interp = _dict(ctx.director_interpret)
    flow = _dict(interp.get("flow"))
    initial_reactors = _drop_non_awake(ctx, normalize_character_refs(
        _list(flow.get("reactors")),
        ctx.cast,
    ))

    # Direct address gives priority, not exclusivity: a character the player
    # explicitly spoke to should be queued ahead of others who merely appear
    # earlier in cast-registration order (flow.reactors' own order reflects
    # that registration order, not who was addressed).
    addressed = normalize_character_refs(
        _list(flow.get("addressed_to")) + _list(flow.get("addressed_to_refs")),
        ctx.cast,
    )
    if addressed:
        initial_reactors = sorted(
            initial_reactors, key=lambda cid: 0 if cid in addressed else 1
        )

    # WHOEVER OWES AN ANSWER HAS THE FLOOR, ahead even of direct address.
    #
    # Order was cast-registration order once the player was silent, so the
    # same character opened every beat regardless of who the conversation was
    # waiting on. Live, chat 38 t144-t147: Tamamo asked the Doctor a direct
    # question on three consecutive beats and he was queued FIRST each time,
    # so his line could never be the answer -- he spoke before she asked, she
    # asked again, and the exchange never closed a single loop.
    #
    # Derived from the engine's own record of who addressed whom expecting a
    # response, rather than added as a Director field. The Director cannot see
    # it any better than this does -- `interaction.expects_response` and
    # `addresses` are already written by the character who asked -- and a
    # second spelling of one fact is a thing that drifts and then disagrees.
    #
    # A tie is left alone: if two characters both owe an answer, the sort is
    # stable and the prior ordering (address, then registration) still decides.
    _owes = []
    # And who is OWED by somebody here. The asker is not an independent
    # observer of this beat -- see the wave construction below.
    _owed_to = set()
    for char_id in initial_reactors:
        row = _character_by_id(ctx, char_id)
        if row is None:
            continue
        try:
            name = character_name(json.loads(row["sheet"]))
        except Exception:
            continue
        debt = (_unanswered_question_note(
            ctx.chat.id, name, ctx.turn.idx, ctx.turn.frame_id)
            or {}).get("awaiting_your_answer")
        if not debt:
            continue
        _owes.append(char_id)
        # `from` is a display name, or "the player" -- who is not in the queue
        # and resolves to nothing, which is correct.
        for asker_id in normalize_character_refs([debt.get("from")], ctx.cast):
            if asker_id != char_id:
                _owed_to.add(asker_id)
    if _owes:
        initial_reactors = sorted(
            initial_reactors, key=lambda cid: 0 if cid in _owes else 1
        )

    # flow.tom_triggers is the Director's statement of whose mind matters this
    # beat. It is used below as a last-chance guard: a beat must not end with
    # that character unsimulated (see the stop_on_question_to_player branch).
    tom_focus = set(normalize_character_refs(
        _list(flow.get("tom_triggers")),
        ctx.cast,
    ))

    max_rounds = int(
        config.get("max_micro_rounds", 1)
    )
    max_calls = int(
        config.get("max_character_calls", 1)
    )
    allow_npc_to_npc = bool(
        config.get(
            "allow_npc_to_npc_dialogue",
            True,
        )
    )

    if max_calls <= 0:
        return {
            "rounds": [],
            "character_results": {},
            "combined_declarations": [],
            "stop_reason": "character calls disabled",
            "calls": 0,
        }

    scene = get_scene(ctx.chat.id, ctx.chat)
    base_views = dict(
        (ctx.perception_act or {}).get("views")
        or {}
    )
    local_views = {
        int(key): value
        for key, value in base_views.items()
        if str(key).isdigit()
    }

    already_reacted = set(ctx.reaction_results)

    # A resumed pipeline hydrates reaction_loop itself, but not necessarily
    # reaction_results. Recover reactor IDs from saved reaction rounds.
    for round_data in _dict_list(
        _dict(ctx.reaction_loop).get("rounds")
    ):
        reactor_id = round_data.get("reactor_id")
        try:
            already_reacted.add(int(reactor_id))
        except (TypeError, ValueError):
            continue

    queue_ids = [
        char_id
        for char_id in dict.fromkeys(initial_reactors)
        if char_id not in already_reacted
    ]

    if not queue_ids:
        return {
            "rounds": [],
            "character_results": {
                str(key): value
                for key, value in ctx.character_results.items()
            },
            "combined_declarations": [],
            "stop_reason": (
                "all reactors already handled"
                if initial_reactors
                else "no reactors"
            ),
            "calls": 0,
        }

    rounds = []
    calls = 0
    already_spoke = set()
    no_content_streak = 0
    focus_deferred = False
    stop_reason = "budget exhausted"

    # THE FIRST WAVE IS SIMULTANEOUS.
    #
    # Everyone in the initial queue is responding to the SAME thing -- the
    # player's declaration, already fixed by the time this stage runs -- and
    # none of them has seen any other reactor's response, because none exists
    # yet. They are mutually blind by construction, so making them take turns
    # is not caution, it is a claim about the fiction that is false: they were
    # all in the room when it happened.
    #
    # It is also what stranded them. The loop's early exits end the BEAT, and
    # the most common one fires on any declared act with a target -- a hug
    # returned, a hand on a shoulder, a glance answered. So the addressed
    # character (queued first, above) would touch somebody, the loop would
    # break, and every other reactor went unsimulated. Measured across the
    # stored corpus: 153 of 196 beats with two or more reactors left at least
    # one never called at all, 106 of those on that one exit.
    #
    # That is not merely a missing line. A character who never ran has no
    # appraisal, so no goal_impacts, so no drive strain from a beat aimed at
    # them; no psychology commit; no memory of having chosen to stay quiet --
    # and the narrator, seeing nothing, is free to render the absence as a
    # deliberate silence nobody chose. `_defer_to_focus` already patched this
    # for `tom_triggers` characters; this is the general case it was a
    # special case of.
    #
    # `initial_parallel_reactors` has been in DEFAULT_INTERACTION_CONFIG since
    # before this and was read by nothing. Parallel in the FICTION, not in
    # execution: the wave runs sequentially, because `character_step` writes
    # through ctx and threading it would race. What is guaranteed is that no
    # member sees another's output while deciding -- micro-perception for the
    # whole wave is delivered only once every member has declared.
    #
    # After the wave, one speaker at a time, unchanged: a character replying
    # to another character IS responding to something they just heard, and
    # ordering is the whole content of that.
    wave_size = max(1, int(config.get("initial_parallel_reactors", 1) or 1))

    def _speak(speaker_id, call_index):
        """One character's declaration. Does not touch `local_views` -- the
        caller decides when what they did becomes perceptible to the others."""
        ctx._extra.setdefault("interaction_views", {})
        ctx._extra["interaction_views"][speaker_id] = local_views.get(
            speaker_id, "")
        result = character_step(ctx, speaker_id, nonce + call_index)
        # Merge rather than overwrite: a character can speak in more than one
        # micro-round, and commit/perception_outcome read
        # ctx.character_results[id] as that character's SINGLE result. A blind
        # reassignment dropped the earlier round's sequence/mind_model_updates
        # entirely at commit.
        ctx.character_results[speaker_id] = _merge_character_results(
            ctx.character_results.get(speaker_id), result
        )
        delivered, perceived_by = deterministic_micro_perception(
            ctx, speaker_id, result, scene)
        rounds.append({
            "round": len(rounds),
            "speaker_id": speaker_id,
            "speaker": _character_display_name(
                _character_by_id(ctx, speaker_id)),
            "result": result,
            "delivered_views": {
                str(key): value for key, value in delivered.items()
            },
        })
        return result, delivered, perceived_by

    first_wave = True

    while queue_ids and len(rounds) < max_rounds:
        if calls >= max_calls:
            stop_reason = "character call budget exhausted"
            break

        is_first = first_wave
        size = min(wave_size, len(queue_ids)) if is_first else 1
        size = min(size, max_calls - calls, max_rounds - len(rounds))
        first_wave = False

        # THE PERSON BEING ANSWERED IS NOT IN THE WAVE.
        #
        # The wave's whole justification is that its members are answering the
        # same thing and none has seen another's response, because none exists
        # yet. That is true when everyone is reacting to the PLAYER. It is
        # false when one member is answering another: the answer is FOR the
        # asker, who is the addressee rather than a bystander, and the question
        # they are owed an answer to already exists from last beat.
        #
        # Live, chat 59 t146. The Doctor owed Tamamo an answer, so he was
        # queued first -- but she was in the same blind instant, so her round
        # was written deaf. Her present evidence was "dim light... gravel...
        # Hinami stands perfectly still", with his answer nowhere in it, and
        # she selected "rephrase the dimensional question freshly to the
        # Doctor". Given a second round she then heard him and acknowledged by
        # restating his own terms back at him. On the page: an answer, then the
        # question it had just answered, then the answer read back to the
        # person who gave it.
        #
        # So the asker steps out of the wave and speaks in the NEXT round,
        # having actually heard it. They keep their place at the front of the
        # queue; nobody loses a turn, the order changes.
        wave, deferred = [], []
        while queue_ids and len(wave) < max(1, size):
            char_id = queue_ids.pop(0)
            if is_first and char_id in _owed_to:
                deferred.append(char_id)
                continue
            wave.append(char_id)
        # Mutual debt (each owes the other) would defer everyone and stall the
        # beat outright. Somebody has to go first; the queue order already
        # decided who.
        if not wave and deferred:
            wave.append(deferred.pop(0))
        queue_ids[:0] = deferred
        if not wave:
            break

        spoke = []
        for speaker_id in wave:
            result, delivered, perceived_by = _speak(speaker_id, calls)
            calls += 1
            already_spoke.add(speaker_id)
            spoke.append((speaker_id, result, delivered, perceived_by))

        # Silence is a property of the WAVE, not of whoever happened to be
        # asked last. One person saying nothing beside somebody who said
        # plenty is not a lull, and counting it as one ended beats that were
        # visibly still going.
        if any(_sequence_has_content(r) for _, r, _, _ in spoke):
            no_content_streak = 0
        else:
            no_content_streak += 1

        # Only now does the wave become visible to itself and to everyone else.
        for _, _, delivered, _ in spoke:
            for observer_id, additions in delivered.items():
                local_views[observer_id] = _append_micro_view(
                    local_views.get(observer_id, ""), additions)

        # The exits are evaluated for the wave as a whole, after all of it has
        # spoken. Evaluating them mid-wave would reinstate exactly the
        # stranding this exists to fix, one member later.
        perceived_by = set()
        for _, _, _, seen in spoke:
            perceived_by |= set(seen or ())

        # Both early exits below end the beat. Neither may end it with the
        # character the beat is ABOUT never simulated -- see _defer_to_focus.
        if any(_requires_director_resolution(r) for _, r, _, _ in spoke):
            deferred = _defer_to_focus(
                queue_ids, tom_focus, already_spoke,
                focus_deferred, calls, max_calls,
            )
            if deferred is not None:
                queue_ids, focus_deferred = deferred, True
                continue
            stop_reason = (
                "physical resolution required"
            )
            break

        if (
            config.get(
                "stop_on_question_to_player",
                True,
            )
            and any(_asks_player(r, ctx.chat, ctx.cast)
                    for _, r, _, _ in spoke)
        ):
            # A question to the player normally ends the beat. But when the
            # Director flagged a character as this beat's focus
            # (flow.tom_triggers) and they have not been called yet, they
            # answer FIRST. Ending here was observed to render that
            # character's silence as a deliberate refusal no agent ever
            # chose -- and, because appraisal exists only for characters that
            # actually ran, it also denied them the goal_impacts their drive
            # strain accrues from, so a drive could never build toward rupture
            # on precisely the beats aimed at it. Granted at most once per
            # beat, so a focus character who also turns to the player cannot
            # hold the loop open.
            deferred = _defer_to_focus(
                queue_ids, tom_focus, already_spoke,
                focus_deferred, calls, max_calls,
            )
            if deferred is not None:
                queue_ids, focus_deferred = deferred, True
                continue
            stop_reason = (
                "awaiting player response"
            )
            break

        # EVERY member of the wave has to be done, not just the last one to
        # be asked. One character closing their own exchange says nothing
        # about whether the person beside them was mid-sentence.
        def _closed(one):
            interaction = _dict(one.get("interaction"))
            return (interaction.get("expects_response") is False
                    and bool(interaction.get("conversation_complete_for_me")))

        if all(_closed(r) for _, r, _, _ in spoke):
            stop_reason = (
                "speaker completed exchange"
            )
            break

        if (
            config.get(
                "silence_ends_exchange",
                True,
            )
            and no_content_streak >= 1
        ):
            stop_reason = "natural silence"
            break

        if not allow_npc_to_npc:
            stop_reason = (
                "NPC-to-NPC dialogue disabled"
            )
            break

        next_ids = []
        for one_id, _, _, _ in spoke:
            for cid in _next_speaker_candidates(
                ctx, one_id, perceived_by, already_spoke,
            ):
                if cid not in next_ids:
                    next_ids.append(cid)

        # `_next_speaker_candidates` looks for somebody NEW to bring in. It
        # does not know the queue already holds someone still owed their turn
        # -- the asker deferred out of the first wave above -- and breaking
        # here would drop them, which is the same stranding the wave exists to
        # prevent, one round later.
        if not next_ids and not queue_ids:
            stop_reason = "no eligible respondent"
            break

        queue_ids.extend(
            char_id
            for char_id in next_ids
            if (
                char_id not in queue_ids
                and char_id not in already_reacted
            )
        )

    ctx._extra["interaction_views"] = local_views

    return {
        "rounds": rounds,
        "character_results": {
            str(key): value
            for key, value
            in ctx.character_results.items()
        },
        "combined_declarations": [
            {
                "char_id": round_data["speaker_id"],
                "name": round_data["speaker"],
                "sequence": (
                    round_data["result"].get(
                        "sequence"
                    )
                    or []
                ),
                "follow_op": round_data["result"].get("follow_op"),
            }
            for round_data in rounds
        ],
        "stop_reason": stop_reason,
        "calls": calls,
    }

def reaction_loop(ctx, nonce):
    """Dedicated physical reaction phase for contestable actions.

    Runs before the interaction loop when the director interpret
    flags resolution_flags.contested or resolution_flags.possible_reactors.
    Each eligible reactor receives only its filtered perception of the
    player's action onset and declares a reaction blind to other reactors.
    """
    interp = _dict(ctx.director_interpret)
    flow = _dict(interp.get("flow"))
    flags = _dict(flow.get("resolution_flags"))

    if not flags.get("contested") and not flags.get("possible_reactors"):
        return {"rounds": [], "reaction_results": {}, "calls": 0, "stop_reason": "no contest"}

    config = reaction_config(ctx.chat.id)
    if not config.get("enabled"):
        return {"rounds": [], "reaction_results": {}, "calls": 0, "stop_reason": "reactions disabled"}

    # max_reactors is the sole cap on how many eligible reactors get to
    # react below. A second cap used to break the loop early once `calls`
    # (one per reactor) hit a separate, smaller "max_reaction_rounds"
    # default -- despite the name, there's no actual multi-round
    # structure here (no reactor is ever revisited), so that setting just
    # silently dropped the tail of reactor_ids below whatever max_reactors
    # already allowed, contradicting the docstring's "each eligible
    # reactor" promise. Removed; max_reactors alone now governs this.
    max_reactors = int(config.get("max_reactors", 6))

    # Get perceivers from perception_act
    perception_views = (ctx.perception_act or {}).get("views") or {}
    reactor_ids = flow.get("reactors") or []
    valid_ids = {int(row["id"]) for row in ctx.cast}
    reactor_ids = [int(rid) for rid in reactor_ids if int(rid) in valid_ids]
    reactor_ids = _drop_non_awake(ctx, reactor_ids)[:max_reactors]

    if not reactor_ids:
        return {"rounds": [], "reaction_results": {}, "calls": 0, "stop_reason": "no reactors"}

    rounds = []
    calls = 0

    for rid in reactor_ids:
        view = perception_views.get(str(rid))
        if not view:
            continue

        ctx._extra.setdefault("reaction_views", {})
        ctx._extra["reaction_views"][rid] = view

        result = character_step(ctx, rid, nonce + calls)
        calls += 1
        ctx.reaction_results[rid] = result

        rounds.append({
            "round": len(rounds),
            "reactor_id": rid,
            "reactor": _character_display_name(_character_by_id(ctx, rid)),
            "result": result,
        })

        if _requires_director_resolution(result):
            break

    return {
        "rounds": rounds,
        "reaction_results": {str(k): v for k, v in ctx.reaction_results.items()},
        "calls": calls,
        "stop_reason": "completed" if calls > 0 else "no reactions",
    }
