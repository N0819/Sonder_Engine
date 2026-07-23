"""Deterministic micro-perception and multi-character reaction/dialogue loops."""

from __future__ import annotations

import json

from character_schema import character_appearance, character_name
from db import wget
from scene import (
    NON_AWAKE_GATED,
    awareness_map,
    awareness_of,
    dialogue_config,
    get_scene,
    reaction_config,
)
from spatial import has_visual, hear_level, room_of, spatial_rel

from .character import character_step
from .common import (
    _append_micro_view,
    _asks_player,
    _character_by_id,
    _character_display_name,
    _conceal_from_targets_observer,
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
                level = hear_level(relation, event.get("volume", "normal"))
                if level == "none":
                    continue
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
                if not has_visual(relation):
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
    id_to_name = {c["id"]: character_name(json.loads(c["sheet"])) for c in ctx.cast}
    return [rid for rid in reactor_ids
            if awareness_of(amap, id_to_name.get(rid, "")) not in NON_AWAKE_GATED]


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
    stop_reason = "budget exhausted"

    while queue_ids and len(rounds) < max_rounds:
        speaker_id = queue_ids.pop(0)

        if calls >= max_calls:
            stop_reason = (
                "character call budget exhausted"
            )
            break

        ctx._extra.setdefault(
            "interaction_views",
            {},
        )
        ctx._extra["interaction_views"][
            speaker_id
        ] = local_views.get(speaker_id, "")

        result = character_step(
            ctx,
            speaker_id,
            nonce + calls,
        )
        calls += 1
        already_spoke.add(speaker_id)
        # Merge rather than overwrite: a character can speak in more than one
        # micro-round, and commit/perception_outcome read
        # ctx.character_results[id] as that character's SINGLE result. A blind
        # reassignment dropped the earlier round's sequence/mind_model_updates
        # entirely at commit.
        ctx.character_results[speaker_id] = _merge_character_results(
            ctx.character_results.get(speaker_id), result
        )

        has_content = _sequence_has_content(result)
        if has_content:
            no_content_streak = 0
        else:
            no_content_streak += 1

        delivered, perceived_by = (
            deterministic_micro_perception(
                ctx,
                speaker_id,
                result,
                scene,
            )
        )

        for observer_id, additions in delivered.items():
            local_views[observer_id] = (
                _append_micro_view(
                    local_views.get(observer_id, ""),
                    additions,
                )
            )

        rounds.append({
            "round": len(rounds),
            "speaker_id": speaker_id,
            "speaker": _character_display_name(
                _character_by_id(
                    ctx,
                    speaker_id,
                )
            ),
            "result": result,
            "delivered_views": {
                str(key): value
                for key, value in delivered.items()
            },
        })

        if _requires_director_resolution(result):
            stop_reason = (
                "physical resolution required"
            )
            break

        if (
            config.get(
                "stop_on_question_to_player",
                True,
            )
            and _asks_player(result, ctx.chat, ctx.cast)
        ):
            stop_reason = (
                "awaiting player response"
            )
            break

        interaction = _dict(
            result.get("interaction")
        )

        if (
            interaction.get("expects_response")
            is False
            and interaction.get(
                "conversation_complete_for_me"
            )
        ):
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

        next_ids = _next_speaker_candidates(
            ctx,
            speaker_id,
            perceived_by,
            already_spoke,
        )

        if not next_ids:
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
