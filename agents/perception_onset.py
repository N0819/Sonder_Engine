"""The action-onset pass (pass 1): `perception_act`, its composer region
(`_composer_act`, `_composer_act_views`), and `beat_player_rooms`, runtime's
early reading of the same declaration.

Carved verbatim from `agents/perception.py` on 2026-11-01;
`agents/perception.py` is now a facade that re-exports every name defined
here (docs/design/DESIGN_MODULE_LAYOUT.md).
"""

from __future__ import annotations

import copy
from story.character_schema import (
    character_appearance,
    character_identity,
    character_name,
    character_name_from_text,
    normalized_character_from_text,
    persona_appearance,
    persona_name,
)
from core.db import wget
from core.pipeline_context import note_step_decision
from world.scene_memo import scene_read_pass
from story.scene import (
    NON_AWAKE_GATED,
    appearance_of,
    awareness_map,
    awareness_of,
    get_scene,
    persona_of,
    senses_of,
    sheet_state,
)
from world.spatial import (
    apply_contact_ops,
    room_display_name,
    _sense_channel,
    heard_events,
    measured_proximity_rel,
    normalize_sensory_event,
    room_of,
    spatial_rel_between,
)
from . import composer
from .common import (
    _act_surface_admission,
    preview_player_state_assertions,
    self_name_forms,
    _appearance_as_prose,
    player_room_in,
    _room_notes_for_view,
    crowds_for_room,
    artifacts_for_room,
    attending_this_room,
    chatter_for_room,
    chatter_inputs,
    couriers_for_room,
    observable_action_onset_text,
    player_speech_lines,
    resolve_action_referents,
    sequence_onset_elements,
    character_room,
    character_scene_keys,
    _present_cast_bodies,
)

from agents.perception_common import (
    _composer_prev_ledger,
    _composer_prev_seen,
    _composer_prev_state,
    _is_player_view,
    _is_the_observer,
    _ling,
    _stage_player_room,
)
from agents.perception_bodies import (
    _body_descriptions,
    _body_scents,
    _composer_extra_parts,
    _own_body_state,
    _subject_concealed_terms,
    _subject_disguise_context,
)
from agents.perception_senses import (
    _addressee_name,
    _behind_rooms,
    _felt_percepts_for,
    _focus_target,
    _in_plain_view,
    _line_is_to,
    _own_name_forms,
    _sense_card,
    _sight_detail,
    _sight_reaches,
    _sleep_hears,
    _sound_field_for,
    _speech_bearing,
    _visible_rooms_for,
    _voice_register_for,
    _voice_sound_for,
    _with_comm_channel,
)
from agents.perception_conduct import (
    _act_gait,
    _channel_to_every_leg,
    _declared_arrival_room,
    _declares_rapid_movement,
    _explicit_look_intent,
    _multi_room_legs,
    _previous_open_group_continuity,
    _speech_room_for,
)
from agents.perception_identity import (
    _ambient_location_for,
    _attributed_label,
    _character_known_places,
    _charter_titles_of,
    _co_present_company,
    _composer_identity_space,
    _composer_self_forms,
    _composer_unknown_sources,
    _far_regions,
    _identity_roster,
    _joint_stranger_labels,
    _presence_bodies,
    _unseen_voice_label,
)
from agents.perception_scrub import (
    _authored_prose_gate,
    _composer_company,
    _composer_finish_observer,
    _composer_scrub_surface,
    _disguise_leak_check,
    _scrub_episode_identities,
)
from agents.perception_standing import (
    _AMBIENT_BEAT_BAND,
    _composer_standing_percepts,
    _gated_ambient_percepts,
)


def perception_act(ctx, nonce):
    chat = ctx.chat
    interp = ctx.director_interpret
    sc = get_scene(chat["id"], chat)
    # Player-authored standing contact is true before reactors decide. Preview
    # it on a copy so pass 1 carries each participant's bodily endpoint while
    # leaving persistence solely to director_resolve/commit. No ageing here:
    # the durable merge will apply this beat exactly once.
    if interp.get("contact_assertions") and not (
            interp.get("state_assertions") or {}).get("causal_steps"):
        sc = apply_contact_ops(
            copy.deepcopy(sc), interp.get("contact_assertions"), _age=False)
    pers = persona_of(chat)
    known = wget(chat["id"], "known", {})
    action = interp.get("action")
    if not isinstance(action, dict):
        action = {}

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
    # WHERE THE BEAT FOUND THEM, before the declaration below is previewed
    # onto the scene: the room half of the walk this beat may contain (PA1).
    p_room_at_start = room_of(sc, p_name)
    origin_sc = sc          # the beat's opening scene: where every act began
    onset_worlds = []
    sc = preview_player_state_assertions(
        sc, (interp.get("onset_state_assertions")
             if interp.get("onset_state_assertions") is not None
             else interp.get("state_assertions")), ctx, p_name,
        causal_worlds=onset_worlds)
    # RESOLVED AGAINST THE SCENE THE VIEWS ARE BUILT FROM, which is this one:
    # the preview above is what puts a declared step into the next room into
    # `sc`, and a room resolved before it grades every observer's channel to
    # the player from the room she left. See `common.player_room_in`.
    p_room = player_room_in(sc, ctx, pers=pers, interp=interp,
                            player_name=p_name)
    # The declared walk's legs, on the same rule the outcome pass applies.
    onset_legs = _multi_room_legs(
        sc, [(p_name, p_room_at_start, p_room)]).get(p_name) or ()
    # A `failing` sound source that goes quiet this beat is TOLD TO THE
    # DIRECTOR, not delivered to an ear: the notice is filed ONCE,
    # at commit, beside the light field's -- `persist/commit_scene_state.py`'s
    # failed-source block writes the switch and the notice for both senses --
    # so a thing that both lights and hums is reported once, not twice, and
    # the Director answers it on the next beat. DESIGN_SOUND_FIELD.md § 5's
    # "silence where there was noise is heard" is the design's claim and not
    # yet the engine's (E16): no percept is minted for a sound that stops,
    # and the standing ledger has no verdict for a percept that simply stops
    # arriving, so the absence reaches the page only through what the Director
    # does with the notice. Perception only hears the beat.
    p_appearance = _appearance_as_prose(appearance_of(
        p_name, pers.get("appearance") or persona_appearance(pers), sc))
    # A physical disguise conceals the actor's real appearance from observers:
    # p_visible is what is actually SEEN (disguised form when active), fed to
    # both the LLM and the deterministic injection below so a concealed feature
    # is never rendered as perceived.
    (p_visible, _p_disguise, p_disguise_known,
     p_disguise_conceals) = _subject_disguise_context(
        ctx, p_name, p_appearance, known)
    p_disguise_terms = _subject_concealed_terms(ctx, p_name)

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
            ctx, b_name, b_true, known)
        co_present.append({
            "name": b_name, "room": b_room, "appearance": b_visible,
            "aliases": character_scene_keys(b_sh)[1:],
            "disguise_known_to": b_known_to,
            "disguise_conceals_identity": _ci,
        })

    # WHO PERCEIVED THE ACT IS NOT WHO MAY ANSWER IT, and one list was
    # answering both questions. `flow.reactors` is the Director's PACING
    # judgement -- who speaks this beat -- and gating this loop on it made a
    # present, awake, watching character perceive the onset never and then
    # answer the aftermath. Measured over the corpus: a witness was missing
    # from `reactors` in 757 of 975 multi-witness beats (77.6%), and 1,639 of
    # 4,292 character-presences (38.2%) got no act view at all.
    #
    # It is felt through `loops.py`: `local_views` starts from these views, so
    # a body drawn into the interaction loop later -- deferred, addressed,
    # answering next beat -- began from an EMPTY base and never held the act
    # it was reacting to, only the dialogue after it.
    #
    # THE WIDENING IS FREE. Perception makes no model call (there is no
    # `perception` role in `providers.ROLES`, and
    # `tests/test_perception_has_no_model.py` pins it), and `loops.py` reads
    # `flow.reactors` for itself -- so who SPEAKS, how many calls the beat
    # costs and the whole pacing question are byte-for-byte unchanged. What
    # changes is that being in the room is what decides whether you saw it.
    #
    # Presence is the scene's answer, not the Director's: a cast body with a
    # room. `co_present` above is built from exactly that test, for exactly
    # that reason.
    perceivers = []
    present_ids = {b["id"] for b in _present_cast_bodies(sc, ctx.cast)}
    # One registry read for the whole stage (see `chatter_inputs`).
    chatter = chatter_inputs(ctx.chat.id, sc, turn_idx=ctx.turn.idx)
    # And the room's other people. Before the perceiver loop, because
    # `_presence_bodies` places them on `sc` and every relation built below
    # asks the scene where a body is.
    co_present.extend(_presence_bodies(
        ctx, sc, [p_room, *(b["room"] for b in co_present)], chatter))

    for c in ctx.cast:
        if c["id"] not in present_ids:
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
                                  observer_room=r, target_room=p_room,
                                  sound=_sound_field_for(
                                      ctx, sc, character_name(sh), r))
        if _previous_open_group_continuity(
                ctx, sc, p_name, character_name(sh), c["id"], p_room, r):
            rel = {**rel, "open_group_continuity": True}
        rdata = (sc.get("rooms") or {}).get(r) if r else None
        prox_to_others, behind_others = _co_present_company(
            sc, character_name(sh), co_present, known)

        perceivers.append({
            "id": c["id"], "name": character_name(sh), "room": r,
            "pronouns": character_identity(sh)["pronouns"],
            "room_name": room_display_name(rdata, r) or "an unspecified area",
            "room_notes": _room_notes_for_view(rdata, r, ctx, sc),
            "ambient_location": _ambient_location_for(sc, r),
            "crowds": crowds_for_room(ctx.chat.id, sc, r, chatter),
            "chatter": chatter_for_room(
                ctx.chat.id, sc, r, chatter,
                attending=attending_this_room(sc, character_name(sh), r)),
            "couriers": couriers_for_room(ctx.chat.id, sc, r, chatter),
            "notices": artifacts_for_room(ctx.chat.id, sc, r, chatter),
            "visible_rooms": _visible_rooms_for(sc, character_name(sh), r),
            "known_places": _character_known_places(c),
            "senses": senses_of(sh), "sense_card": _sense_card(sh),
            "attention": act.get("goal") or "ambient",
            "spatial_to_actor": rel,
            "visual_channel_to_actor": _sight_reaches(
                sc, character_name(sh), act.get("actor") or "",
                _sense_card(sh), rel=rel),
            # ONE LINE, ONE FLOOR (PR5). This key feeds `speech_percept` and
            # `communication_percept` and nothing else, and
            # `composer.line_hear_level` states the contract in its own
            # docstring: pass only a MEASURED tier, because `proximity_rel`
            # returns "near" both as a reading and as its fallback when
            # nobody wrote stations (6.7% of live bodies carry one), and a
            # gate that reads the fallback as evidence of separation
            # silences a conversation. The OUTCOME pass already passes
            # `measured_proximity_rel`; this one passed the raw tier, so the
            # same beat's same line was graded by two different floors --
            # F61's class at the proximity gate.
            "proximity_to_actor": measured_proximity_rel(
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

    return _stage_player_room(_composer_act(
        ctx, sc, interp, perceivers, known, p_name, p_visible,
        p_disguise_known, p_disguise_conceals, p_disguise_terms, co_present,
        amap, speech_elems, action, onset_legs, p_room=p_room,
        origin_sc=origin_sc, origin_room=p_room_at_start,
        causal_worlds=onset_worlds), ctx)


def _composer_act(ctx, sc, *args, **kwargs):
    """Every observer's pass-1 view, built inside one scene read pass (C12
    -- see the note above `_composer_establish`)."""
    with scene_read_pass(sc):
        return _composer_act_views(ctx, sc, *args, **kwargs)


def _composer_act_views(ctx, sc, interp, perceivers, known, p_name, p_visible,
                        p_disguise_known, p_disguise_conceals,
                        p_disguise_terms, co_present, amap, speech_elems,
                        action, onset_legs=(), *, p_room, origin_sc=None,
                        origin_room=None, causal_worlds=()):
    regions = _far_regions(ctx)
    onset_sequence = sequence_onset_elements(interp.get("sequence") or [])
    actor_names = {f"character:{c['id']}": character_name_from_text(c["sheet"])
                   for c in ctx.cast}
    actor_names.update({f"persona:{p['persona_id']}": p.get("name") or "Player"
                        for p in ctx.extra_players})
    actor_names["persona:primary"] = p_name
    if ctx.chat.get("persona_id") is not None:
        actor_names[f"persona:{ctx.chat['persona_id']}"] = p_name
    from world.causal_program import event_worlds
    causal_moments = event_worlds(causal_worlds,
                                 [{"event": event} for event in onset_sequence])
    from world.causal_completion import event_execution_statuses
    execution_statuses = event_execution_statuses(
        causal_worlds, [{"event": event} for event in onset_sequence], action=True)
    # WHERE EACH ONSET EVENT HAPPENED. The stage resolves the player's room
    # ONCE against the previewed scene, so `p_room` is where the beat LEAVES
    # her; every event was graded there, and the lamp she took off the
    # kitchen table before walking out was refused "cannot see" by the man
    # sitting at that table (scratch play 2026-09-14, chat 5 turn 8). The
    # declaration carries its own order: the element that moved her is the
    # cut (`mover_cut_events`, the same rule the outcome pass and the
    # movement cuts read), everything before it happened where the beat
    # found her, everything from it on where it left her.
    _beat_origin = str(origin_room or "")
    _beat_dest = str(p_room or "")
    _moved = bool(_beat_origin and _beat_dest and _beat_origin != _beat_dest)
    _cut_index = None
    if _moved:
        try:
            from agents.director import mover_cut_events
            _told = str(mover_cut_events(interp).get(p_name) or "")
        except Exception:
            _told = ""
        for _i, _e in enumerate(onset_sequence):
            if not isinstance(_e, dict):
                continue
            if _told and str(_e.get("event_id") or "") == _told:
                _cut_index = _i
                break
        if _cut_index is None:
            for _i, _e in enumerate(onset_sequence):
                if isinstance(_e, dict) and isinstance(_e.get("movement"), dict):
                    _cut_index = _i
                    break

    def _event_room(idx):
        """The room an onset event happened in, or None when the beat
        cannot say (no move, or a move with no element to pin it to)."""
        if idx in causal_moments:
            return room_of(causal_moments[idx], p_name)
        if not _moved or _cut_index is None:
            return None
        return _beat_origin if idx < _cut_index else _beat_dest
    # THE SOUNDS THE PLAYER MADE THIS BEAT REACH THE CAST NOW, not a stage
    # later. A world-author declaration that opens a sluice ("the by-wash
    # took the run with a roar you could feel through your boots") is a
    # `sensory_events` row in the beat's onset assertions, and this pass
    # graded none of them: the cast declared into a silent world and the
    # bargee begged for the sluice she had just thrown (scratch play
    # 2026-09-14, chat 5 turn 3). Same rows, same normaliser and the same
    # field the outcome pass reads them through.
    _onset = (interp.get("onset_state_assertions")
              if interp.get("onset_state_assertions") is not None
              else interp.get("state_assertions"))
    _onset = _onset if isinstance(_onset, dict) else {}
    act_sounds = [dict(record, desc=record["detail"]) for record in (
        normalize_sensory_event(event, rooms=sc.get("rooms") or {})
        for event in (_onset.get("sensory_events") or [])
        if isinstance(event, dict)) if record and record.get("detail")]
    # WHICH ONSET ACTS FILED A SOUND OF ITS OWN -- a sound's `from_event` is
    # its act's `chrono_id`, one stage, so the number says it: an act behind
    # an observer is heard as that sound, not told again as movement
    # (`composer.act_percept`).
    _onset_sounding = set()
    for _event in (_onset.get("sensory_events") or []):
        if not isinstance(_event, dict) \
                or _event.get("from_event") in (None, ""):
            continue
        _record = normalize_sensory_event(_event, rooms=sc.get("rooms") or {})
        if _record and _record.get("detail") and _sense_channel(
                str(_record.get("kind") or "sound")) == "hearing":
            _onset_sounding.add(str(_event["from_event"]))
    if speech_elems and not any(
            isinstance(e, dict) and e.get("type") == "speech"
            for e in onset_sequence):
        onset_sequence.extend(speech_elems)

    self_forms_by_name = {}
    for c in ctx.cast:
        sh = normalized_character_from_text(c["sheet"])
        self_forms_by_name[character_name(sh)] = self_name_forms(
            character_name(sh), character_scene_keys(sh))

    onset_targets = {str(t).casefold()
                     for t in ((action or {}).get("targets") or [])}
    onset_loud = any(str(e.get("volume", "")).lower() in ("loud", "shout")
                     for e in speech_elems)
    spoken = player_speech_lines(interp)
    roster = _identity_roster(p_name, p_visible, ctx.cast, scene=sc,
                              bodies=co_present,
                              titles_of=_charter_titles_of(ctx, sc))
    identity_space = _composer_identity_space(ctx, p_name, p_visible)
    cast_parts = _composer_extra_parts(ctx, p_name)
    body_scents = _body_scents(ctx)
    body_descriptions = _body_descriptions(ctx, sc)
    prev_ledger = _composer_prev_ledger(ctx)
    actor_body = {
        # THE ROOM THIS STAGE ALREADY RESOLVED, handed down rather than
        # re-derived (review 2026-09-07 A83). `perception_act` is the one
        # stage entitled to read the declaration -- it composes the onset
        # from where the player says she is going -- and it resolves the
        # room once, against the previewed scene. This used to ask again
        # with `resolve=False`, which answered from the scene or from the
        # turn cache; once A83 stopped the declared destination being
        # cached, the positionless case would have left the onset pass
        # disagreeing with itself, because `actor_body["room"]` is the
        # speaker-origin room for `_declared_arrival_room` and the
        # `_spoken_from` fast path below. One resolution per stage, read by
        # everything in it.
        "name": p_name, "room": p_room,
        "appearance": p_visible, "aliases": [],
        "disguise_known_to": p_disguise_known,
        "disguise_conceals_identity": p_disguise_conceals,
    }
    all_bodies = [b for b in co_present if b.get("name") != p_name]
    all_bodies.append(actor_body)
    bodies_by_name = {b["name"]: b for b in all_bodies if b.get("name")}
    onset_appearances = {key: body.get("appearance") or ""
                         for key, body in bodies_by_name.items()}
    onset_aliases = {key: body.get("aliases") or []
                    for key, body in bodies_by_name.items()}
    joint_labels = _joint_stranger_labels(all_bodies)
    # Every body this beat could NAME, and every spelling prose reaches for
    # it by -- the input `_act_surface_admission` (PX5) reads to decide
    # whether an observable's clause is about somebody the observer has a
    # channel to. A presence with no sheet contributes its own name.
    forms_by_body = {nm: self_forms_by_name.get(nm) or [nm]
                     for nm in bodies_by_name}
    # WHERE THE BEAT SAYS THIS BODY ENDS UP (`_declared_arrival_room`), and
    # one relation per observer per room built from it (`_speech_room_for`):
    # a line said with a hand on somebody in the room walked INTO is heard
    # from there, not from the room left behind.
    arrival_room = _declared_arrival_room(sc, interp, actor_body.get("room"))
    arrival_rels = {}
    origin_rels = {}
    clean_views, observations, ledger, company = {}, {}, {}, {}
    witnessed = {}
    for p in perceivers:
        pid = str(p["id"])
        name = p["name"]
        # An unconscious observer sees nobody, and that is a RECORD rather
        # than a gap: it must reach the ledger as an empty set, so the beat
        # they wake on reads as a re-encounter with everyone in the room.
        # NOT `seen`: this function already binds that name to a visibility
        # BOOLEAN further down, and shadowing it made `sorted(seen)` fail
        # on five movement and resume tests at once.
        seen_bodies = set()
        display_map = {}
        prev_standing, prev_described = _composer_prev_state(prev_ledger, pid)
        if p.get("awareness") in NON_AWAKE_GATED:
            name_cf = name.casefold()
            cause = (amap.get(name_cf) or {}).get("cause", "").lower()
            pain = any(w in cause for w in _ling("_PAIN_CUES"))
            # THE PLAYER'S RAISED VOICE REACHES THIS SLEEPER ONLY WHERE IT
            # REACHES THEIR EAR (DESIGN_SOUND_FIELD § 13, `_sleep_hears`):
            # it was any loud or shouted line of theirs, wherever the
            # sleeper lay. Waking is decided once, at the outcome.
            loud_event = False
            if onset_loud:
                _loud_lines = [
                    {"speaker": p_name, "speaker_room": p_room,
                     "exact_quote": e.get("text") or "x",
                     "volume": e.get("volume")}
                    for e in speech_elems
                    if str(e.get("volume", "")).lower() in ("loud", "shout")]
                _woke, _heard = _sleep_hears(
                    ctx, sc, name, p.get("room"), _loud_lines,
                    senses=p.get("sense_card"))
                loud_event = bool(_woke) or _heard
            percepts = composer.residue_percepts(
                p["awareness"], targeted=(name_cf in onset_targets),
                loud_event=loud_event, pain=pain)
            company[pid] = []       # an unconscious observer sees nobody
        else:
            others = [b for b in co_present
                      if not _is_the_observer(sc, b["name"], name)]
            others.append(actor_body)
            # A deliberate look is a sweep: the player turns through the
            # whole room for this beat, so the cone does not subtract.
            p["sweep"] = pid == "player" and _explicit_look_intent(interp)
            display_map = composer.observer_display_map(
                sc, name, others, known, p.get("sense_card"))
            self_forms = _composer_self_forms(
                name, self_forms_by_name.get(name),
                bodies_by_name.get(name), joint_labels, display_map)
            percepts = _composer_standing_percepts(
                sc, p, name, others, display_map, known,
                entity_state=p.get("entity_state")
                or _own_body_state(sc, name),
                prev_seen=_composer_prev_seen(prev_ledger, pid),
                seen_out=seen_bodies,
                gate=_authored_prose_gate(
                    ctx, "perception_act", name, known, identity_space),
                extra_parts=cast_parts, body_scents=body_scents,
                body_descriptions=body_descriptions,
                self_forms=self_forms,
                self_pronouns=p.get("pronouns"),
                sound=_sound_field_for(ctx, sc, name, p.get("room"),
                                       events=act_sounds),
                prev_standing=prev_standing,
                regions=regions)
            if act_sounds:
                # THIS BEAT'S sounds are the beat's, not the air of the
                # place (`_AMBIENT_BEAT_BAND`; round 2, lane B).
                percepts.extend(_gated_ambient_percepts(
                    _authored_prose_gate(
                        ctx, "perception_act", name, known, identity_space),
                    act_sounds, p.get("room"), order_key=_AMBIENT_BEAT_BAND))
                _afar = heard_events(
                    sc, name, act_sounds, room=p.get("room"),
                    turn_idx=getattr(ctx.turn, "idx", None),
                    crowds=ctx.get("_sound_crowds"))
                if _afar:
                    _here = str(p.get("room") or "")
                    percepts.extend(_gated_ambient_percepts(
                        _authored_prose_gate(
                            ctx, "perception_act", name, known,
                            identity_space),
                        [{**event, "room": _here, "room_id": _here,
                          "source_room": _here} for event, _level in _afar],
                        p.get("room"), order_key=_AMBIENT_BEAT_BAND))
            # LOUD SOUND IS FELT (wave B2), whatever this body can hear.
            percepts.extend(_felt_percepts_for(ctx, sc, name, p.get("room"),
                                               act_sounds))
            rel = p.get("spatial_to_actor") or {}
            vis = p.get("visual_channel_to_actor", False)
            can_see = _in_plain_view(rel, vis)
            display = display_map.get(p_name, p_name)
            recognized, unknown = _composer_unknown_sources(
                name, known, roster, bodies_by_name)
            continuity = bool(rel.get("open_group_continuity"))

            def _spoken_from(room, idx=None, actor=p_name,
                             _p=p, _name=name, _rel=rel, _vis=vis):
                """(relation, can_see) for a line said in ``room``.

                One relation per observer per room, built the way the
                onset's own is (`perception_act`), so a line graded at the
                declared destination is graded by the same reader that
                grades one at the origin -- one beat, one field.

                SIGHT AT THE ORIGIN IS READ OFF THE OPENING SCENE. `_vis`
                is the beat-wide channel, computed on the preview with the
                actor already at the destination, so an act at the origin
                -- the lamp taken off the table before she walked out --
                was refused "cannot see" by the man sitting at that table
                (scratch play 2026-09-14, chat 5 turn 8). Where the beat
                moved the actor, the origin's sight is graded on the scene
                the beat opened with.
                """
                if idx in causal_moments or actor != p_name:
                    then = causal_moments.get(idx, sc)
                    observer_room = room_of(then, _name) or _p.get("room")
                    alt = spatial_rel_between(
                        then, _name, actor, observer_room=observer_room,
                        target_room=room_of(then, actor),
                        sound=_sound_field_for(ctx, then, _name, observer_room,
                                               events=act_sounds))
                    alt_vis = _sight_reaches(then, _name, actor,
                                             _p.get("sense_card"), rel=alt)
                    return alt, _in_plain_view(alt, alt_vis)
                if room == actor_body.get("room") or not room:
                    return _rel, _in_plain_view(_rel, _vis)
                if (_moved and room == _beat_origin
                        and origin_sc is not None):
                    cached = origin_rels.get(_name)
                    if cached is None:
                        alt = spatial_rel_between(
                            origin_sc, _name, p_name,
                            observer_room=_p.get("room"),
                            target_room=_beat_origin,
                            sound=_sound_field_for(
                                ctx, origin_sc, _name, _p.get("room"),
                                events=act_sounds))
                        alt_vis = _sight_reaches(
                            origin_sc, _name, p_name, _p.get("sense_card"),
                            rel=alt)
                        cached = (alt, _in_plain_view(alt, alt_vis))
                        origin_rels[_name] = cached
                    return cached
                cached = arrival_rels.get((_name, room))
                if cached is None:
                    alt = spatial_rel_between(
                        sc, _name, p_name, observer_room=_p.get("room"),
                        target_room=room,
                        sound=_sound_field_for(ctx, sc, _name,
                                               _p.get("room"),
                                               events=act_sounds))
                    alt_vis = _sight_reaches(sc, _name, p_name,
                                             _p.get("sense_card"), rel=alt)
                    cached = (alt, _in_plain_view(alt, alt_vis))
                    arrival_rels[(_name, room)] = cached
                return cached

            _act_fields = {}

            def _act_field(then, then_room, _name=name):
                """This observer's sound field over the scene an act was
                made in -- one per moment (a causal moment's scene is not
                the read pass's, so it is not memoised there)."""
                key = (id(then), then_room)
                if key not in _act_fields:
                    _act_fields[key] = _sound_field_for(
                        ctx, then, _name, then_room, events=act_sounds)
                return _act_fields[key]

            for idx, event in enumerate(onset_sequence):
                if not isinstance(event, dict):
                    continue
                if event.get("type") != "speech" and execution_statuses.get(idx) == "unresolved":
                    # Keep the event in the audit ledger, but never render a
                    # known unexecuted effect as an accomplished outward act.
                    # SAID OUT LOUD, because this was the one refusal in the
                    # stage that recorded nothing: a bare `continue` left the
                    # pipeline drawer showing a specialist's note and no
                    # trace of the act it had cost (chat 135 turn 1). What
                    # reaches here now is a verification failure only --
                    # a thin ledger stopped counting as one
                    # (`world/causal_completion.execution_receipt`).
                    note_step_decision(
                        "act_percept", "%s -> %s" % (
                            actor_names.get(str(event.get("actor") or ""), "?"), name),
                        "refused",
                        "the beat verified this act as unexecuted")
                    continue
                actor_ref = str(event.get("actor") or event.get("source_entity_id") or "")
                event_actor = actor_names.get(actor_ref) or actor_ref or p_name
                if _is_the_observer(sc, event_actor, name):
                    continue
                event_scene = causal_moments.get(idx, sc)
                event_observer_room = room_of(event_scene, name) or p.get("room")
                event_proximity = (measured_proximity_rel(event_scene, name, event_actor)
                                   if idx in causal_moments or event_actor != p_name
                                   else p.get("proximity_to_actor"))
                event_display = display if event_actor == p_name else _attributed_label(
                    event_actor, name, recognized=recognized, display_map=display_map,
                    bodies_by_name=bodies_by_name,
                    can_see=_spoken_from(None, idx, event_actor)[1], unseen=_unseen_voice_label(),
                    appearances=onset_appearances, cast_aliases=onset_aliases)
                if event.get("type") == "speech":
                    said_rel, said_seen = _spoken_from(
                        _event_room(idx) or _speech_room_for(
                            sc, event, arrival_room, actor_body.get("room")), idx, event_actor)
                    speech_rel = said_rel if continuity and event_actor == p_name else {
                        **said_rel, "open_group_continuity": False}
                    speech_rel = _with_comm_channel(
                        event_scene, speech_rel, speaker=event_actor, observer=name,
                        observer_room=event_observer_room)
                    # LOUD ENOUGH FOR THE ONE ADDRESSED, AT ONSET TOO. The
                    # addressee is on the interpret's own span (its
                    # `intended_target`/`targets`), so the level is solved
                    # here from where they stand, exactly as the outcome
                    # pass solves it; graded as a normal line, a keeper's
                    # order pitched down three storeys reached the man it
                    # was for as "...Then... hands... where..." (Skerry
                    # Light turn 5, 2026-09-15).
                    onset_volume = str(event.get("volume") or "normal")
                    onset_level = None
                    if onset_volume.strip().casefold() == "pitched":
                        from world.spatial import pitched_level_db, word_for_level
                        onset_level = pitched_level_db(
                            event_scene, event_actor, _addressee_name(
                                ctx, event.get("intended_target")
                                or (event.get("targets") or [None])[0]))
                        onset_volume = word_for_level(onset_level)
                    entry = {
                        "speaker": event_actor,
                        "text": event.get("text"),
                        "volume": onset_volume,
                        **({"level_db": onset_level} if onset_level is not None else {}),
                        "tone": event.get("tone", ""),
                        "visibility": event.get("visibility", "overt"),
                        "conceal_from": event.get("conceal_from") or [],
                        # Whom it is spoken to, for the ear rung's own
                        # reading of the line (`addressed` below decides).
                        "targets": list(event.get("targets") or []),
                        # WHOM IT WAS SPOKEN TO, as the outcome pass's lines
                        # carry it: in a din the one addressed follows the
                        # line and a bystander a few paces off does not
                        # (DESIGN_SOUND_FIELD § 12). Dropped here, every
                        # onset line read as addressed to nobody.
                        "intended_target": _addressee_name(
                            ctx, event.get("intended_target")
                            or (event.get("targets") or [None])[0]) or None,
                    }
                    percept = composer.speech_percept(
                        entry, speech_rel, name, display=event_display,
                        can_see=said_seen,
                        proximity=event_proximity,
                        order_key=idx, observer_id=pid,
                        senses=p.get("sense_card"),
                        voice=_voice_register_for(ctx, event_actor),
                        voice_sound=_voice_sound_for(ctx, event_actor),
                        prev_standing=prev_standing,
                        bearing=_speech_bearing(event_scene, name, event_actor,
                                                said_seen, speech_rel),
                        # WHOSE EAR (`EAR_VOLUME`), read against the scene
                        # and this beat's own handles for each body.
                        addressed=_line_is_to(ctx, event_scene, name, event,
                                              names=actor_names),
                        name_forms=_own_name_forms(ctx, name))
                    if percept:
                        percepts.append(percept)
                elif event.get("type") == "communication":
                    said_rel, said_seen = _spoken_from(_speech_room_for(
                        sc, event, arrival_room, actor_body.get("room")), idx, event_actor)
                    speech_rel = said_rel if continuity and event_actor == p_name else {
                        **said_rel, "open_group_continuity": False}
                    entry = {**event, "speaker": event_actor}
                    percept = composer.communication_percept(
                        entry, _with_comm_channel(
                            event_scene, speech_rel, speaker=event_actor, observer=name,
                            observer_room=event_observer_room),
                        name, display=event_display, can_see=said_seen,
                        proximity=event_proximity,
                        order_key=idx, observer_id=pid,
                        senses=p.get("sense_card"),
                        addressed=_line_is_to(ctx, event_scene, name, event,
                                              names=actor_names))
                    if percept:
                        percepts.append(percept)
                elif event.get("type") == "action":
                    if _declares_rapid_movement([event]):
                        # Speech before the run stays audible; speech after
                        # gets no continuity floor.
                        continuity = False
                    # A BODY THE OBSERVABLE NAMES IS A PERCEPT OF ITS OWN
                    # (PX5). Before the identity scrub, because the scrub
                    # rewrites the very names this reads.
                    surface, _cut = _act_surface_admission(
                        observable_action_onset_text(event),
                        actor=event_actor, observer=name,
                        forms_by_body=forms_by_body,
                        perceived=seen_bodies,
                        who="%s -> %s" % (event_actor, name))
                    if _cut and not surface:
                        continue        # refusal already recorded
                    # Own name off before the scrub, as at outcome.
                    surface = composer._peel_own_name(surface, event_actor)
                    surface = _composer_scrub_surface(
                        surface, name, recognized, unknown,
                        labels=display_map)
                    surface = resolve_action_referents(
                        surface, event, {
                            **{key: value for key, value in display_map.items()},
                            name: "you", event_actor: event_display,
                        })
                    # WHERE THE ACT WAS MADE (`_event_room`): before the
                    # cut, where the beat found her; from it on, where it
                    # left her.
                    act_room = _event_room(idx)
                    # The moving element itself is the crossing: it answers
                    # to every leg, as before. Anything the order places in
                    # one room is graded in that room.
                    anchored = (idx in causal_moments or event_actor != p_name
                                or (act_room is not None and idx != _cut_index))
                    if onset_legs and not anchored and not _channel_to_every_leg(
                            sc, None, name, p.get("room"), onset_legs,
                            p.get("sense_card")):
                        note_step_decision(
                            "act_percept", "%s -> %s" % (p_name, name),
                            "refused",
                            "the act crossed %d rooms and this observer's "
                            "channel did not stand in all of them"
                            % len(onset_legs))
                        continue
                    act_rel, act_seen = (_spoken_from(act_room, idx, event_actor) if anchored
                                         else (rel, can_see))
                    percept = composer.act_percept(
                        event_scene, event, name, event_actor, act_rel, display=event_display,
                        can_see=act_seen,
                        sight=_sight_detail(event_scene, name, event_actor, act_rel,
                                            senses=p.get("sense_card")),
                        self_forms=self_forms,
                        self_pronouns=p.get("pronouns"),
                        other_forms=tuple(
                            form
                            for other_name, other_names
                            in self_forms_by_name.items()
                            if other_name != name
                            for form in (other_names or ())),
                        order_key=idx, observer_id=pid, surface=surface,
                        # WHAT AN ACT BEHIND THIS OBSERVER SOUNDS LIKE, as
                        # at outcome: on the field of the act's own moment,
                        # at the gait it declares (a walk where it declares
                        # none: no travel record exists yet), unless it
                        # filed a sound of its own.
                        sound=_act_field(event_scene, event_observer_room),
                        gait=_act_gait(event) or None,
                        own_sound=str(event.get("chrono_id") or "")
                        in _onset_sounding)
                    if percept:
                        percepts.append(percept)
            company[pid] = _composer_company(others, display_map, percepts)
        rendered = composer.render_view(
            percepts, mode="character", prev_standing=prev_standing,
            prev_described=prev_described, language=ctx.language)
        _composer_finish_observer(
            ctx, "perception_act", pid, name, rendered, known, roster,
            clean_views, observations, ledger, spoken_lines=spoken,
            seen=seen_bodies, labels=display_map,
            percepts=percepts)
        # WHAT THIS MIND WITNESSED BEFORE IT ACTED (the owner, 2026-09-30:
        # a turn's memory in order -- witnessed, did, what happened as a
        # result -- "and doesn't have duplicates"). Minted from the same
        # percepts its view was, as the outcome's episode is; the keys of
        # every percept in it are what the outcome's episode leaves out, so
        # the two halves never say one thing twice.
        if not _is_player_view(pid):
            # FAR SIGHT IS NO PART OF WHAT A MIND WITNESSED BEFORE IT ACTED:
            # it is filed once, by the outcome's episode, after the beat --
            # in this half it opened the memory row and its gist overrode
            # the outcome's (review 2026-10-05: a town's lights at dusk took
            # the gist from the question put to her). Its keys stay out of
            # `keys`, so the outcome is free to file it.
            near = [p for p in percepts if not composer.far_sight(p)]
            w_content, w_gist, w_entities = composer.render_episode(
                near, prev_standing=prev_standing,
                prev_described=prev_described, language=ctx.language)
            w_content, w_gist = _scrub_episode_identities(
                ctx, "perception_act", name, w_content, w_gist, known, roster)
            witnessed[pid] = {
                "episode": w_content, "gist": w_gist, "entities": w_entities,
                "keys": sorted({p.dedupe_key for p in near if p.dedupe_key}),
                # what each percept says, one entry per percept: an act
                # re-minted at the outcome under a new event id keeps its
                # words, not its key
                "said": [s for s in (composer.episode_signature(p) for p in near) if s]}
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
        "witnessed": witnessed,
    }


def beat_player_rooms(ctx):
    """Every room this beat carries the player through: where it found them,
    where it leaves them, and the legs between -- the same reading
    `perception_act` makes of the interpreted beat (`preview_player_state_
    assertions`, `player_room_in`, `_multi_room_legs`), made early, with no
    model call and the player-room cache left as it was.

    For `runtime`'s bubble check before the plan is built: a beat that walks
    the player up to a bubble's cast must find them in its world, not after
    it (concept lab story, 2026-09-30: a knock at the clinic answered by a
    stranger while the doctor stood in a bubble)."""
    chat = ctx.chat
    interp = ctx.director_interpret if isinstance(ctx.director_interpret, dict) else {}
    sc = get_scene(chat["id"], chat)
    pers = persona_of(chat)
    p_name = pers.get("name") or persona_name(pers)
    start = room_of(sc, p_name)
    moved = preview_player_state_assertions(
        sc, (interp.get("onset_state_assertions")
             if interp.get("onset_state_assertions") is not None
             else interp.get("state_assertions")), ctx, p_name, causal_worlds=[])
    cached = ctx._extra.get("_player_room", None) if hasattr(ctx, "_extra") else None
    had = hasattr(ctx, "_extra") and "_player_room" in ctx._extra
    try:
        end = player_room_in(moved, ctx, pers=pers, interp=interp, player_name=p_name, resolve=False)
    finally:
        if hasattr(ctx, "_extra"):
            if had:
                ctx._extra["_player_room"] = cached
            else:
                ctx._extra.pop("_player_room", None)
    legs = _multi_room_legs(moved, [(p_name, start, end)]).get(p_name) or ()
    return {str(r) for r in (start, end, *legs) if r}
