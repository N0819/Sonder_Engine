"""Deterministic micro-perception and multi-character reaction/dialogue loops."""

from __future__ import annotations

import json
import random

from story.character_schema import (character_appearance, character_name,
                              character_name_from_text, character_senses)
from core.db import wget
from language_runtime import compositor_text
from story.scene import (
    NON_AWAKE_GATED,
    awareness_map,
    awareness_of,
    dialogue_config,
    get_scene,
    reaction_config,
)
from world.spatial import (hear_level, proximity_rel, room_of, sense_adjusted,
                     sound_bearing, spatial_rel, spatial_rel_between,
                     visual_level_between)

from .character import _unanswered_question_note, character_step
from .common import (
    _append_micro_view,
    _asks_player,
    cut_short_speech,
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
    _muffle_middle,
    _next_speaker_candidates,
    _observable_predicate,
    _requires_director_resolution,
    observable_action_text,
    _sequence_has_content,
    normalize_character_refs,
)

def _cut_into_last_element(sequence):
    """Cut the ONE element an interruption landed during -- the victim's most
    recent -- and report whether anything was cut.

    `ctx.character_results[id]` is the MERGED result across every micro-round
    (`_merge_character_results` concatenates sequences), so a character who
    spoke in round 0 and again in round 2 carries both lines. This used to
    truncate BOTH, and mark every action element in either round
    `interrupted`. Only the line being cut into was interrupted; the earlier
    one completed and was answered -- and `deterministic_micro_perception`
    had already appended it IN FULL to every eligible observer's local view,
    so rewriting it afterwards left the stored record disagreeing with what
    the other minds in the room were told they heard.

    Design.md states the contract as one line: `interrupts: "<name>"` says the
    beat landed DURING that line. A line too short to get inside stays whole
    (`cut_short_speech` returns None) and nothing was cut into.
    """
    elements = [e for e in (sequence or []) if isinstance(e, dict)]
    if not elements:
        return False
    last = elements[-1]
    if last.get("type") == "speech":
        shortened = cut_short_speech(last.get("text"))
        if not shortened:
            return False
        last["text"] = shortened
        last["cut_short"] = True
        return True
    if last.get("type") == "action":
        # Marked, never rewritten: what happens to a reach that got grabbed
        # is causality, and causality belongs to the Director.
        last["interrupted"] = True
        return True
    return False


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
        # THE body-to-body relation builder: it carries concealment, the
        # crossing grace, and the enclosure directions the bare room-level
        # form cannot know (register L2). Argument order is (observer, actor):
        # spatial_rel stamps the light of the room being LOOKED AT, and this
        # loop used to pass (actor_room, observer_room) -- grading sight OF
        # the actor by the light where the OBSERVER stood, a full visual
        # channel to an actor standing in darkness (register L6).
        relation = spatial_rel_between(scene, observer_name, actor_name,
                                       observer_room=observer_room,
                                       target_room=actor_room)
        observer_awareness = awareness_of(amap, observer_name)
        # F4: the micro-loop used to read bare hear_level with no proximity, so
        # a muttered aside landed full-volume on an arbitrarily large room.
        proximity = proximity_rel(scene, observer_name, actor_name)
        # G4: the observer's card senses gate what the channels carry. An
        # ordinary card is byte-identical to before; only explicitly authored
        # acuity shifts anything.
        observer_senses = character_senses(observer_sheet)
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
                                    awareness=observer_awareness,
                                    senses=observer_senses):
                    continue
                level = sense_adjusted(
                    hear_level(relation, volume, proximity=proximity),
                    "hearing", observer_senses)
                quote = str(event.get("text") or "")
                if level == "full":
                    additions.append(compositor_text(
                        "loop_speech", label=display, body=quote))
                elif level == "trace":
                    # Contentless by contract (G4): detection and direction at
                    # best -- no words, no identity, not even the gated
                    # `display` label, which would still say "someone you
                    # know of is there".
                    hint = sound_bearing(scene, observer_name, actor_name)
                    # Two templates, not one padded slot. A bearing changes
                    # the SHAPE of the sentence, not just its content: English
                    # needed a word gap the caller was supplying with an
                    # f-string, and Japanese with no bearing read 「どこかから」.
                    additions.append(
                        compositor_text("loop_faint_sound_placed",
                                        where=str(hint["phrase"])) if hint
                        else compositor_text("loop_faint_sound"))
                else:
                    # The SHARED degrader, not a second copy of the rule.
                    # This built its fragment with `quote.split()`, which
                    # returns one token for a language that does not space its
                    # words -- so a listener at partial hearing received the
                    # entire secret, verbatim. `_muffle_tokens` was fixed for
                    # exactly this and this call site was missed; one muffling
                    # rule, in one place, is the only way that stays true.
                    fragment = _muffle_middle(quote)
                    additions.append(compositor_text(
                        "loop_muffled", label=display, fragment=fragment))
                perceived_by.add(observer_id)
            elif event.get("type") == "action":
                if event.get("visibility") == "concealed":
                    continue
                if not _delivery_ok(relation, scene, observer_name, actor_name,
                                    "action", awareness=observer_awareness,
                                    senses=observer_senses):
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


def _defer_to_unrun_reactor(queue_ids, initial_reactors, already_spoke,
                            calls, max_calls):
    """Re-queue an initial reactor who has not run yet, or None to let the
    early exit stand.

    THE GENERAL CASE `_defer_to_focus` WAS A SPECIAL CASE OF, and the reason
    the simultaneous opening wave existed. Both early exits end the BEAT, and
    with the wave gone the shape came straight back: chat 59 t161 and t162 --
    the Doctor answered, turned a question to the player, `stop_on_question_
    to_player` fired, and Tamamo, an initial reactor standing right there,
    was never called at all. Two beats in a row.

    A character who never ran has no appraisal, so no goal_impacts, so no
    drive strain from a beat aimed at them; no psychology commit; no memory of
    having chosen to stay quiet -- and the narrator, seeing nothing, is free to
    render the absence as a deliberate silence nobody chose.

    The exit is right about what comes AFTER: no new speaker should be drawn
    in, and the beat does end here. What it was wrong about is ending before
    the people the beat already summoned have had their one turn. So the exit
    is deferred, not cancelled -- each remaining initial reactor runs, in
    order, each seeing what the previous did, and the beat closes when the
    queue is drained. That keeps the causal chain the whole ordering change
    exists for; the wave got these characters simulated by making them blind,
    which was the wrong price.

    Bounded by the call budget and by `already_spoke`, so this drains rather
    than loops.
    """
    if calls >= max_calls:
        return None
    pending = [cid for cid in queue_ids
               if cid in initial_reactors and cid not in already_spoke]
    if not pending:
        return None
    first = pending[0]
    return [first] + [cid for cid in queue_ids if cid != first]


def _standing_pressure(ctx, char_id):
    """How much this character currently WANTS to act, in [0, 1].

    The top urgency across their standing wants. `active_state.wants` is the
    psychology commit's own record of what a mind is carrying into the beat,
    already bounded and already written every turn -- so this reads a live
    field rather than introducing a second opinion about motivation that would
    drift from the first.

    Missing state reads as 0, not as an error. A character who has never been
    committed yet has no standing wants, which is the true answer.
    """
    row = _character_by_id(ctx, char_id)
    if row is None:
        return 0.0
    # sqlite3.Row raises IndexError for a column it does not have, and cast
    # rows reach this from several queries with different projections. A row
    # carrying no committed state is not an error; it has no standing wants.
    try:
        raw = row["state"]
    except (IndexError, KeyError, TypeError):
        return 0.0
    try:
        state = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return 0.0
    wants = ((state.get("active_state") or {}).get("wants")) or []
    best = 0.0
    for want in wants:
        if not isinstance(want, dict):
            continue
        try:
            urgency = float(want.get("urgency") or 0.0)
        except (TypeError, ValueError):
            continue
        best = max(best, min(1.0, max(0.0, urgency)))
    return best


def _untargeted_order(ctx, char_ids, nonce):
    """Who speaks first when the beat named nobody.

    Cast-REGISTRATION order was deciding, which is not a fact about the
    fiction: the same character opened every untargeted beat for the life of a
    story, whatever anybody wanted. The engine already fixed one instance of
    this for answer-debt; this is the general case.

    Two inputs, deliberately mixed. Standing pressure, because a mind carrying
    an urgent want is the one who would speak into a lull -- and a seeded
    jitter, because it is a lull: nobody was addressed, so the order is not
    determined by the beat, and a pure ranking would be as fixed as
    registration order was, only differently. The jitter is bounded well below
    the pressure range, so a strongly-motivated character usually goes first
    and not always.

    Seeded on the turn AND the nonce, so it is stable across a rerun from a
    stage and free to land differently on a reroll -- the same rule the dice
    already follow.
    """
    def _key(char_id):
        rng = random.Random(
            f"{ctx.chat.id}:{ctx.turn.idx}:{nonce}:reactor-order:{char_id}")
        return -(_standing_pressure(ctx, char_id) + rng.random() * 0.25)

    return sorted(char_ids, key=_key)


def _perceptually_isolated(scene, name_a, name_b):
    """Can neither of these two perceive the other, at all, right now?

    True only when BOTH channels are shut in BOTH directions: no sight either
    way, and nothing short of a deliberate shout audible either way. Anything
    less and one of them could register that the other acted, which is the
    whole reason the loop runs them in order.

    THE LINE IS DRAWN AT `loud`, NOT AT `shout`, and that is the loose end this
    feature is shelved with. The engine's own model says a shout carries a
    FRAGMENT between far separated rooms, so testing at `shout` would make
    nothing anywhere isolated and the branch dead. Testing at `loud` means two
    people in sealed rooms are isolated for every ordinary purpose, and a
    character who actually shouts could reach somebody the wave had already
    treated as unreachable. Whoever turns this on owns that case -- the honest
    fix is re-running an isolated reactor when a shout was in fact declared,
    which needs the declaration first and so needs the loop restructured.

    Fail-closed on unresolvable geometry: an unknown room answers "not
    isolated", because the cost of a wrong yes is two characters declaring into
    the same instant while one could hear the other, and the cost of a wrong no
    is only a sequential call that was not strictly required.
    """
    if not scene or not name_a or not name_b:
        return False
    room_a, room_b = room_of(scene, name_a), room_of(scene, name_b)
    if not room_a or not room_b or room_a == room_b:
        return False
    for observer, target in ((name_a, name_b), (name_b, name_a)):
        if visual_level_between(scene, observer, target) != "none":
            return False
        rel = spatial_rel(scene, room_of(scene, target), room_of(scene, observer))
        if hear_level(rel, "loud") != "none":
            return False
    return True


def _isolated_wave(ctx, scene, queue_ids, enabled):
    """The opening wave: the first reactor, plus anyone who could not possibly
    perceive them (or each other) this beat.

    OFF BY DEFAULT AND DELIBERATELY SHELVED. The rule is right -- two people in
    separate rooms, out of sight and out of earshot, are not taking turns in
    any sense a reader could detect, and running them in one instant is what
    offscreen simulation will need. But offscreen simulation is not built, so
    today every reactor in a beat is somebody the player can hear, this branch
    would never fire on a real story, and shipping it live would mean the first
    time it ran was the first time it was exercised. It is written, tested and
    switched off until there is offscreen life to run through it. See
    docs/UNBUILT.md.

    Grows greedily and checks each candidate against every member already in
    the wave, not just the first: two characters together in a far room can
    hear EACH OTHER, so they belong in sequence with one another even though
    both are isolated from the opener.
    """
    if not queue_ids:
        return []
    wave = [queue_ids[0]]
    if not enabled:
        return wave
    names = {}
    for char_id in queue_ids:
        row = _character_by_id(ctx, char_id)
        if row is None:
            continue
        try:
            names[char_id] = character_name(json.loads(row["sheet"]))
        except Exception:
            continue
    for char_id in queue_ids[1:]:
        candidate = names.get(char_id)
        if not candidate:
            continue
        if all(_perceptually_isolated(scene, candidate, names.get(member))
               for member in wave):
            wave.append(char_id)
    return wave


def interaction_loop(ctx, nonce):
    config = dialogue_config(ctx.chat.id)

    interp = _dict(ctx.director_interpret)
    flow = _dict(interp.get("flow"))
    initial_reactors = _drop_non_awake(ctx, normalize_character_refs(
        _list(flow.get("reactors")),
        ctx.cast,
    ))

    # WHO THE BEAT LANDED ON GOES FIRST, and the beat says who that is in two
    # places: who was spoken to, and who was acted upon. Order is causality
    # here -- whoever runs first decides in a room where nothing else has
    # happened yet, and everyone after them is answering a room that has.
    #
    # Speech outranks action deliberately. A question names its addressee
    # exactly; an action's `targets` is a looser field that the deterministic
    # binder fills from whoever the act plausibly lands on, and a live beat had
    # "sits back down at the chabudai table" targeting BOTH people in the room.
    # Treating that as an address would make the ranking say nothing. So:
    # spoken to (0), acted upon (1), present (2) -- and a stable sort leaves
    # cast-registration order deciding inside each band.
    addressed = normalize_character_refs(
        _list(flow.get("addressed_to")) + _list(flow.get("addressed_to_refs")),
        ctx.cast,
    )
    acted_upon = set()
    for element in _dict_list(interp.get("sequence")):
        if element.get("type") not in ("action", "speech"):
            continue
        for target_id in normalize_character_refs(
                _list(element.get("targets")), ctx.cast):
            if target_id not in addressed:
                acted_upon.add(target_id)
    # Inside the untargeted band, standing motivation and a seeded jitter
    # decide -- see `_untargeted_order`. Applied FIRST so the target ranking
    # below, being a stable sort, keeps it as the within-band order.
    initial_reactors = _untargeted_order(ctx, initial_reactors, nonce)
    if addressed or acted_upon:
        def _address_rank(cid):
            if cid in addressed:
                return 0
            if cid in acted_upon:
                return 1
            return 2
        initial_reactors = sorted(initial_reactors, key=_address_rank)

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
            ctx.chat.id, name, char_id, ctx.turn.idx, ctx.turn.frame_id)
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

    # The people this beat summoned. An early exit may not close the beat
    # while one of them has never run -- see _defer_to_unrun_reactor.
    initial_set = set(queue_ids)
    # Why the beat is going to end, recorded when an early exit is DEFERRED so
    # the summoned cast can finish. Without it the loop reports whatever it
    # happened to run out of ("no eligible respondent"), and the real reason --
    # somebody turned a question to the player -- is lost to every consumer.
    pending_exit_reason = None

    rounds = []
    calls = 0
    already_spoke = set()
    # observer_id -> the speakers they have actually perceived this beat.
    # An interruption claim is checked against it: you cannot cut into a
    # line you never heard.
    heard_by = {}
    no_content_streak = 0
    focus_deferred = False
    stop_reason = "budget exhausted"

    # ONE AT A TIME, AND CAUSALITY BUILDS AS THEY GO.
    #
    # This used to open with a simultaneous wave of two, on the argument that
    # everyone in the initial queue is responding to the same fixed thing --
    # the player's declaration -- so none of them could have seen another's
    # response and making them take turns claimed something false about the
    # fiction.
    #
    # The argument is right about a beat aimed at the ROOM and wrong about
    # every other kind, which is most of them. When the player addresses one
    # person, the others are not co-respondents to the same event: they are
    # bystanders to an exchange that has not finished, and what they should be
    # reacting to is how it went. Deciding blind, they answer a question that
    # is already answered. Live, chat 59 t161: the player asked the Doctor
    # "Doctor is something the matter?"; he was correctly ranked first and
    # answered; Tamamo, in the same blind instant, said "He savors in silence,
    # daughter" and then "Doctor?" -- prompting a man who had just spoken. The
    # narrator's own fidelity check caught it as dialogue rendered out of
    # order, which is what a beat looks like when two people speak into the
    # same instant and only one of them could hear.
    #
    # The wave's OTHER justification does not need it any more. It was
    # introduced because the loop's early exits ended the beat before later
    # reactors ran -- 153 of 196 multi-reactor beats left somebody never
    # called -- and the worst of those exits fired on any declared act with a
    # target. That exit is now gated on the Director's own `commitment:
    # "contestable"` (alpha 6.9.1), and `_defer_to_focus` plus the
    # queue-not-empty guard (6.9.2) cover the rest. Stranding is fixed where
    # it was caused; it does not also need everyone to move at once.
    #
    # So the default is one, and `initial_parallel_reactors` is the knob for
    # anyone who wants the simultaneous open back -- a duel, a crowd turning
    # at a noise, any beat where nobody was addressed and the room reacts as a
    # room. Raising it re-enables exactly the old behaviour: parallel in the
    # FICTION, not in execution, since `character_step` writes through ctx and
    # threading it would race. What the wave guarantees is only that no member
    # sees another's output while deciding, because micro-perception for the
    # whole wave is withheld until every member has declared.
    wave_size = max(1, int(config.get("initial_parallel_reactors", 1) or 1))

    def _apply_interruptions(speaker_id, result):
        """Resolve a declared interruption against who has actually spoken.

        WHY THIS IS DECLARATIVE RATHER THAN A SCHEDULING TRICK. Opening the
        beat with one character (see ONE AT A TIME above) buys causality and
        costs interruption: every reaction becomes a response to a COMPLETED
        act, and nobody can cut anybody off. The scheduling answer -- let them
        overlap again -- is the blindness that ordering was changed to remove.

        The declarative answer costs nothing, because a character later in the
        chain has ALREADY HEARD the line they want to cut off, which is how
        interruption works in life: you cut in because you heard where the
        sentence was going. So the only thing missing was a way to say the
        beat landed DURING that line rather than after it.

        `interrupts` is a CLAIM. This resolves it deterministically:

          * the named party must have actually spoken earlier in this beat --
            you cannot cut off a line nobody has said;
          * the interrupter must have been able to hear them, or there was
            nothing to cut into;
          * a line too short to get inside stays whole (`cut_short_speech`
            returns None), and the interrupting beat simply follows it.

        Speech and conduct both interrupt. A blow, a hand over a mouth or a
        grabbed wrist ends a sentence exactly as a louder voice does, and the
        engine should not need to be told twice which channel did it.

        The interrupted ACTION is marked and not rewritten: what happens to a
        reach that got grabbed is causality, and causality belongs to the
        Director. What is decided here is only that it was cut into.
        """
        notes = []
        for element in (result.get("sequence") or []):
            claim = str(element.get("interrupts") or "").strip()
            if not claim:
                continue
            element["interrupts"] = ""
            victim_id = next(
                (cid for cid in normalize_character_refs([claim], ctx.cast)
                 if cid != speaker_id and cid in already_spoke), None)
            if victim_id is None:
                ctx.warnings.append(
                    f"interaction_loop: dropped an interruption of {claim!r} "
                    f"-- they have not spoken this beat")
                continue
            if victim_id not in (heard_by.get(speaker_id) or set()):
                ctx.warnings.append(
                    f"interaction_loop: dropped an interruption of {claim!r} "
                    f"-- the interrupter could not hear them")
                continue
            victim = ctx.character_results.get(victim_id) or {}
            cut_any = _cut_into_last_element(victim.get("sequence"))
            element["interrupted"] = _character_display_name(
                _character_by_id(ctx, victim_id))
            if cut_any:
                notes.append(victim_id)
        return notes

    def _speak(speaker_id, call_index):
        """One character's declaration. Does not touch `local_views` -- the
        caller decides when what they did becomes perceptible to the others."""
        ctx._extra.setdefault("interaction_views", {})
        ctx._extra["interaction_views"][speaker_id] = local_views.get(
            speaker_id, "")
        result = character_step(ctx, speaker_id, nonce + call_index)
        _apply_interruptions(speaker_id, result)
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
        for _observer in perceived_by:
            heard_by.setdefault(_observer, set()).add(speaker_id)
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
        if is_first:
            # Out-of-earshot reactors may share the opening instant -- see
            # `_isolated_wave`. Off until offscreen simulation exists, so this
            # resolves to the configured wave size (1) on every live story.
            isolated = _isolated_wave(
                ctx, scene, queue_ids,
                bool(config.get("parallel_isolated_reactors", False)))
            size = max(len(isolated), min(wave_size, len(queue_ids)))
        else:
            size = 1
        size = min(size, len(queue_ids), max_calls - calls,
                   max_rounds - len(rounds))
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
            drained = _defer_to_unrun_reactor(
                queue_ids, initial_set, already_spoke, calls, max_calls)
            if drained is not None:
                queue_ids = drained
                pending_exit_reason = "physical resolution required"
                continue
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
            drained = _defer_to_unrun_reactor(
                queue_ids, initial_set, already_spoke, calls, max_calls)
            if drained is not None:
                queue_ids = drained
                pending_exit_reason = "awaiting player response"
                continue
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
                "material_effects": (
                    round_data["result"].get("material_effects") or []),
            }
            for round_data in rounds
        ],
        # A deferred exit is still the reason this beat ended. Without this the
        # loop reports whatever it ran out of after draining the queue, and
        # "somebody asked the player something" -- which every consumer of
        # stop_reason cares about -- is replaced by a bookkeeping detail.
        "stop_reason": (pending_exit_reason
                        if pending_exit_reason and stop_reason in (
                            "budget exhausted", "no eligible respondent",
                            "natural silence")
                        else stop_reason),
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
