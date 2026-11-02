"""The outcome pass's composer region: `_composer_outcome` (sweep stamp, read
pass) and `_composer_outcome_views`, the 1,309-line per-observer assembler
moved whole.

Carved verbatim from `agents/perception.py` on 2026-11-01;
`agents/perception.py` is now a facade that re-exports every name defined
here (docs/design/DESIGN_MODULE_LAYOUT.md).
"""

from __future__ import annotations

from story.character_schema import (
    character_name,
    normalized_character_from_text,
)
from core.pipeline_context import note_step_decision
from world.scene_memo import scene_read_pass
from story.scene import NON_AWAKE_GATED, is_player_speaker, persona_of
from world.spatial import (
    tread_events,
    door_events,
    distant_sounds,
    visual_level_between,
    heard_events,
    measured_proximity_rel,
    normalize_sensory_event,
    room_of,
    same_subject,
    spatial_rel_between,
    beat_movement_cuts,
    scene_as_of,
    substance_event_clause,
)
from . import composer
from .common import (
    _act_surface_admission,
    self_name_forms,
    _recognizes,
    player_speech_lines,
    resolve_action_referents,
    cast_room,
    character_scene_keys,
)

from agents.perception_common import (
    _composer_prev_ledger,
    _composer_prev_meta,
    _composer_prev_seen,
    _composer_prev_state,
    _is_player_view,
    _is_the_observer,
    _ling,
)
from agents.perception_bodies import (
    _appearance_ledger_changed,
    _attire_changed_semantically,
    _attire_delta_text,
    _attire_diff_moves_clothing,
    _body_descriptions,
    _body_scents,
    _composer_extra_parts,
    _outward_form_transitions,
    _own_body_state,
    _subject_disguise_context,
)
from agents.perception_senses import (
    _card_admitted,
    _asleep_when_the_beat_began,
    _blast_exposure,
    _felt_percepts_for,
    _in_plain_view,
    _line_is_to,
    _own_name_forms,
    _reaches_this_ear,
    _sight_detail,
    _sleep_hears_where,
    _sound_field_for,
    _sound_filing_spans,
    _sounds_after_sight,
    _sourceless_event_rel,
    _speech_bearing,
    _ubiquitous_names,
    _voice_register_for,
    _voice_sound_for,
    _with_comm_channel,
)
from agents.perception_conduct import (
    _act_gait,
    _beat_movers,
    _channel_to_every_leg,
    _explicit_look_intent,
    _legs_of_actor,
    _looked_vistas,
    _multi_room_legs,
    _own_handled,
    _own_looks,
    _walk_underway,
    swept_this_beat,
)
from agents.perception_identity import (
    _attributed_label,
    _charter_place_before,
    _charter_titles_of,
    _composer_identity_space,
    _composer_self_forms,
    _composer_unknown_sources,
    _far_regions,
    _joint_stranger_labels,
    _mover_is_a_body,
    _source_is_a_body,
    _thing_label,
    _unseen_voice_label,
    _worn_identity,
    identity_bearing_sources,
)
from agents.perception_scrub import (
    _authored_prose_gate,
    _composer_company,
    _composer_finish_observer,
    _composer_scrub_surface,
    _disguise_leak_check,
    _disguise_leak_checks,
    _inverted_motion_check,
    _scrub_episode_identities,
)
from agents.perception_stream import (
    _background_beats,
    _cue_percept,
    _cue_slots,
    _manifest_percepts,
    _outcome_event_stream,
)
from agents.perception_standing import (
    _AMBIENT_BEAT_BAND,
    _composer_standing_percepts,
    _gated_ambient_percepts,
)


def _composer_outcome(ctx, sc, *args, **kwargs):
    """Every observer's pass-2 view, built inside one scene read pass (C12
    -- see the note above `_composer_establish`).

    WHO LOOKED AROUND THIS BEAT is stamped on the working copy BEFORE the
    pass opens. `_sweeping` is in the pass's read set (`scene_memo.
    SCENE_READS`: `effective_facing` reads it), and the views stamped it
    INSIDE the pass -- after the pass had fingerprinted the scene, so every
    derivation memoised before the write could be stale, which is exactly
    what the pass's exit warning reports (it fired on a probe story's
    opening, 2026-10-20: "the scene changed inside a read pass ... opened
    at _composer_outcome"). The stamp now precedes the pass; the views
    read it."""
    import inspect
    bound = inspect.signature(_composer_outcome_views).bind(
        ctx, sc, *args, **kwargs).arguments
    swept = swept_this_beat(bound["res"], bound["p_name"], ctx.cast,
                            bound["interp"])
    if swept:
        sc["_sweeping"] = sorted(swept)
    with scene_read_pass(sc):
        return _composer_outcome_views(ctx, sc, *args, **kwargs)


def _composer_outcome_views(ctx, sc, prev_scene, diff, interp, res, known,
                            p_name, p_appearance, _p_disguise,
                            p_disguise_known, p_disguise_conceals,
                            p_disguise_terms, perceivers, appearances,
                            sources, enriched_dlog, substance_events,
                            amap, presence_bodies=()):
    chat = ctx.chat
    pers = persona_of(chat)
    regions = _far_regions(ctx)

    cast_aliases = {}
    for c in ctx.cast:
        sh = normalized_character_from_text(c["sheet"])
        cast_aliases[character_name(sh)] = character_scene_keys(sh)[1:]
    self_forms_by_name = {
        nm: self_name_forms(nm, [nm, *(cast_aliases.get(nm) or [])])
        for nm in appearances
    }
    self_forms_by_name[p_name] = self_name_forms(
        p_name, [p_name, *((pers.get("identity") or {}).get("aliases") or [])])

    # Speech and action are one declared chronology.  Reducing them into a
    # dialogue list plus an actor-keyed terminal action first lost motion; a
    # plain action list restored the motion but still placed every line before
    # every act.  Bind both back to their original sequence slots once, before
    # applying each observer's channels below.
    beat_events = _outcome_event_stream(
        ctx, sc, interp, res, p_name, enriched_dlog,
        _background_beats(ctx, sc))
    # Where each source stands, as the perceiver maps were built with it
    # (`_source_channels`' `target_room`), for `_channel_as_of`'s restamp.
    _source_rooms = {str(src.get("name")): src.get("room")
                     for src in (sources or ()) if isinstance(src, dict)
                     and src.get("name")}
    from world.causal_program import event_worlds
    _composed = ctx.get("_composed_beat")
    causal_moments = event_worlds(
        getattr(_composed, "causal_worlds", None), beat_events)
    from world.causal_completion import event_execution_statuses
    execution_statuses = event_execution_statuses(
        getattr(_composed, "causal_worlds", None), beat_events, action=True)
    # WHEN EACH BODY CAME INTO A ROOM: the index of the causal step in which
    # it crossed into it, or None where the beat records no steps or no such
    # crossing. The crossing percepts below are ordered by it.
    _step_worlds = list(getattr(_composed, "causal_worlds", None) or ())
    _arrivals = {}

    def _arrival_step(body, room):
        key = (str(body), str(room))
        if key not in _arrivals:
            _arrivals[key] = next((
                index for index, world in enumerate(_step_worlds)
                if isinstance(world, dict)
                and room_of(world.get("after") or {}, body) == room
                and room_of(world.get("before") or {}, body) != room), None)
        return _arrivals[key]

    # WHERE EACH BODY WAS WHEN EACH EVENT HAPPENED. The stream above is
    # causally ordered and says so; until 2026-09-09 nothing downstream asked
    # it, and every percept was graded against `sc` -- the scene the commit
    # will write, i.e. where everybody ENDED. Right for a standing fact, wrong
    # for an event. Live: chat 122 turn 3, the Doctor spoke, turned and walked
    # off, and both lines were graded from the dune he reached; the surf's
    # noise floor refused them; his answers reached no view and the narrator
    # invented a player line to cover the hole. See `beat_movement_cuts`.
    # AND WHICH EVENT MOVED THEM, where the beat can say. `beat_movement_cuts`
    # otherwise infers it as the mover's LAST action -- the only choice two
    # snapshots allow, and its own docstring names the quantity it wanted:
    # "recording the trajectory is what fixes it". The causality recompiler
    # records it, so the cut falls on the move rather than after everything
    # the mover did next. A body it cannot speak for keeps the heuristic.
    from .director import mover_cut_events
    # BOTH HALVES. The player's cut comes from his own declaration, whose
    # elements carry the phase ids this stream is keyed on. A CHARACTER's comes
    # from the author's whole-beat list, whose elements cite the declaration
    # they describe -- the Director categorizes and cites, the character only
    # declares, and that is why nothing has to ask a mind about ledgers.
    # The player's own answer wins a collision: his sequence IS the
    # declaration, and the author is describing it second-hand.
    _moved_at = dict(mover_cut_events(res, (res or {}).get("state_diff")))
    _moved_at.update(mover_cut_events(interp))
    movement_cuts = beat_movement_cuts(
        prev_scene, sc, beat_events, moved_at=_moved_at)

    # A NOISE IS AN EVENT, AND AN EVENT IS OVER WHEN THE BEAT IS
    # (DESIGN_SOUND_DECIBELS.md § 4). Read from the beat's own diff rather
    # than from the scene, and it has to be: the record the scene will carry
    # is written by the commit, which runs AFTER the narrator, so
    # `beat_sensory_events` answers nothing at this point in the turn and
    # would go on answering nothing next turn, when the beat has moved. The
    # same normaliser the commit uses grades it, so what this stage delivers
    # and what the commit stores are the same records; `desc` is the key
    # `ambient_percepts` reads a signal's own room by, and `detail` is the
    # one the objects hand writes it in.
    _incoming = list(diff.get("sensory_events") or ())
    # WHAT THE OFF-SCREEN WORLD WAS HEARD DOING REACHES EARS HERE OR
    # NOWHERE. `charter_noises` turns each creature's own `state["heard"]`
    # -- what every body was doing and where, replaced every round -- into
    # this channel's shape, and `commit_scene_state` adds it to the record
    # it STORES. That store is unreachable by construction, and the comment
    # directly above says why for the Director's half: the commit runs after
    # the narrator, so a stored record is written for a beat whose
    # perception has already happened, and `beat_sensory_events` refuses it
    # on every later beat because the beat number is its whole lifetime.
    # The Director's own events escape that by riding the DIFF, which is
    # what this stage reads; the charter's had no diff to ride.
    #
    # So a creature's voice reached no reader at all -- not once, in any
    # story. Measured live, chat 117 turns 64-65: a carbonic stalker
    # followed the cast through a jammed pressure door, the round recorded
    # `moving` at `loud` in the room they were kneeling in, the commit wrote
    # it faithfully into the scene, and no observation of any kind was
    # composed from it. The whole authored apparatus -- four voices per
    # creature, rungs, bearings, "the sound is the channel a creature
    # reaches a room through before it reaches the room" -- was inert.
    #
    # A ONE-BEAT LAG IS THE HONEST ANSWER and not a defect of this fix: the
    # charter window advances inside the commit, so what it records is the
    # elapsed beat, and the first perception that can carry it is the next
    # one. Hearing it a beat late is what a listener gets when the thing
    # happened while the beat was resolving; hearing it never is what the
    # engine did before.
    try:
        from world.charter_runtime import charter_noises, registry_for
        _incoming.extend(charter_noises(
            registry_for(ctx.chat.id,
                         getattr(getattr(ctx, "turn", None), "frame_id", None))))
    except Exception:
        pass                       # a story with no charter adds nothing
    # THE BEAT'S FOOTFALLS ARE SOUND EVENTS (`spatial_sound_field.tread_events`):
    # a tread in the walker's room, and one in every room it lies over.
    _incoming = list(_incoming) + tread_events(sc, _beat_movers(
        ctx, prev_scene, sc, bodies=[*cast_aliases, p_name]))
    # ...AND SO ARE ITS DOORS: a doorway that went from shut to open, or open
    # to shut, this beat sounds at itself in both its rooms
    # (`spatial_sound_field.door_events`), whoever wrote the change.
    _incoming = _incoming + door_events(prev_scene, sc)
    # WHEN IT SOUNDED: the causal step a sound came from (`from_event`),
    # kept beside the normalised record so it is graded against the world
    # of that moment rather than the world the beat ended in. Chat 160 turn
    # 11: an elevator's brakes shrieked and its cables snapped in the shaft
    # the car was falling through; graded at the end of the beat the car had
    # landed, the shaft lay behind a wall, and its riders heard neither.
    _sensory = []
    for event in _incoming:
        if not isinstance(event, dict):
            continue
        record = normalize_sensory_event(event, rooms=sc.get("rooms") or {})
        if record:
            if event.get("from_event") not in (None, ""):
                record = dict(record, _at=str(event["from_event"]))
            _sensory.append(record)
    beat_sounds = [dict(record, desc=record["detail"])
                   for record in _sensory if record.get("detail")]
    # WHICH OF THE BEAT'S ACTS FILED A SOUND OF ITS OWN: an act behind an
    # observer is heard as that sound and not told again as movement
    # (`composer.act_percept`, `_sound_filing_spans`); any other act behind
    # one sounds as its actor's own tread, at the gait the beat walked them.
    _sounding_spans = _sound_filing_spans(diff, beat_sounds)
    _gaits = {str(name).strip().casefold(): pace for name, pace
              in (_beat_movers(ctx) or {}).items()}
    _sound_moments = {}
    for _world in getattr(ctx.get("_composed_beat"), "causal_worlds", None) or ():
        if str(_world.get("stage") or "") == "resolve" and isinstance(_world.get("after"), dict):
            _sound_moments[str(_world.get("chrono_id"))] = _world["after"]
    _now_sounds = [e for e in beat_sounds if e.get("_at") not in _sound_moments]
    _then_sounds = [e for e in beat_sounds if e.get("_at") in _sound_moments]

    def _beat_position(kind, record):
        """WHERE IN THE BEAT a line or a placed sound falls -- its index in
        `beat_events` -- or None (DESIGN_SOUND_FIELD § 17, the woken beat).
        A line is found by its dialogue row (the stream binds the row
        itself, or a copy of it with the same speaker and words); a sound
        tied to its moment (`_at`, the resolve step it came from) by the
        stream entry resolved in that step (`causal_span`). An unplaced
        sound -- a door, a tread, a charter noise, an event with no step --
        has no place, and a reader that needs one subtracts."""
        if kind == "line" and isinstance(record, dict):
            speaker = str(record.get("speaker") or "").strip()
            words = str(record.get("exact_quote") or "")
            for index, event in enumerate(beat_events):
                if event.get("kind") != "speech":
                    continue
                entry = event.get("entry") or {}
                if entry is record or (
                        str(entry.get("speaker") or "").strip() == speaker
                        and str(entry.get("exact_quote") or "") == words):
                    return index
            return None
        if kind == "event" and isinstance(record, dict):
            at = record.get("_at")
            if at is None or str(at) not in _sound_moments:
                return None
            for index, event in enumerate(beat_events):
                span = event.get("causal_span")
                if (isinstance(span, (list, tuple)) and len(span) == 2
                        and str(span[0]) == "resolve"
                        and str(span[1]) == str(at)):
                    return index
            return None
        return None

    def _step_index_of(at_index):
        """The index among the beat's causal worlds (`_step_worlds`) of the
        step `beat_events[at_index]` was resolved in, or None -- the clock
        the arrival steps (`_arrival_step`) are read on."""
        if at_index is None or not (0 <= at_index < len(beat_events)):
            return None
        span = (beat_events[at_index] or {}).get("causal_span")
        if not (isinstance(span, (list, tuple)) and len(span) == 2):
            return None
        for index, world in enumerate(_step_worlds):
            if (isinstance(world, dict)
                    and str(world.get("stage") or "") == str(span[0])
                    and str(world.get("chrono_id")) == str(span[1])):
                return index
        return None

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
                ctx, nm, app, known)
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
    # LAST, for the reason `_composer_establish` gives: the registered cast
    # keeps the stranger-label assignment order it had.
    bodies.extend(
        b for b in (presence_bodies or ()) if b["name"] not in appearances)
    bodies_by_name = {b["name"]: b for b in bodies if b.get("name")}
    joint_labels = _joint_stranger_labels(bodies)
    # The act stage's twin (see `_composer_act`): every body this beat could
    # NAME, and every spelling prose reaches for it by, for
    # `_act_surface_admission` (PX5).
    forms_by_body = {nm: self_forms_by_name.get(nm) or [nm]
                     for nm in bodies_by_name}

    # Visible-form structural changes this beat re-earn a full description.
    appearance_changed = set()
    for field in ("attire", "overlays", "scales"):
        for key in (diff.get(field) or {}):
            # ATTIRE IS ASKED WHETHER IT ACTUALLY MOVED. The other two
            # fields carry no comparable ledger here, so their key presence
            # still stands as the signal.
            # TWO GATES, and the cheap one first. An entry that adds,
            # removes and replaces nothing moved no clothing whatever its
            # `state` note says; and an entry that does move something may
            # still be putting on what is already worn, which the ledger
            # comparison catches.
            if field == "attire":
                entry = (diff.get(field) or {}).get(key)
                if not _attire_diff_moves_clothing(entry):
                    continue
                if not _attire_changed_semantically(prev_scene, sc, str(key)):
                    continue
            elif not _appearance_ledger_changed(
                    prev_scene, sc, field, str(key)):
                continue
            appearance_changed.add(str(key))
    # What each change LOOKS like, computed here because this is the stage
    # that holds the previous scene. Empty for a body whose clothing did not
    # move (a scale, an overlay, a rewritten description), which falls the
    # renderer back to the full authored appearance.
    appearance_deltas = {}
    for key in appearance_changed:
        text = _attire_delta_text(prev_scene, sc, key, ctx.language)
        if text:
            appearance_deltas[key] = text
    for key, entity in (diff.get("entities") or {}).items():
        # Schema-normalized entity rows routinely carry ``description: ''``
        # even when the specialist changed no visible prose. Key presence was
        # therefore enough to re-earn a registered body's complete card every
        # beat. Only a non-empty, genuinely changed description may signal a
        # visible rewrite here.
        previous = ((prev_scene or {}).get("entities") or {}).get(key) or {}
        rewrote_visible = isinstance(entity, dict) and any(
            str(entity.get(field) or "").strip()
            and entity.get(field) != (previous.get(field)
                                      if isinstance(previous, dict) else None)
            for field in ("description", "appearance")
        )
        if rewrote_visible:
            appearance_changed.add(str(key))
            if entity.get("name"):
                appearance_changed.add(str(entity["name"]))
    # THE TRANSITION, NEVER THE STANDING STATE (A37): a mask going up or
    # coming down re-earns a description; a mask that stayed on all beat is
    # the same body the observer was already looking at. See
    # `_outward_form_transitions` for the episode this was minting.
    appearance_changed.update(_outward_form_transitions(diff))

    titles_of = _charter_titles_of(ctx, sc)
    ident_roster = [
        {"name": nm, "appearance": ap, "aliases": cast_aliases.get(nm) or [],
         **_worn_identity(nm, bodies, sc, titles_of)}
        for nm, ap in appearances.items()
    ]
    for s in identity_bearing_sources(sources, sc):
        if s.get("name") and all(r["name"] != s["name"] for r in ident_roster):
            ident_roster.append(
                {"name": s["name"], "appearance": None, "aliases": [],
                 **_worn_identity(s["name"], bodies, sc, titles_of)})
    # Every body the beat laid in view, acting or not (`_identity_roster`).
    for b in bodies:
        if b.get("name") and all(r["name"] != b["name"] for r in ident_roster):
            ident_roster.append(
                {"name": b["name"], "appearance": b.get("appearance"),
                 "aliases": [a for a in (b.get("aliases") or []) if a],
                 **_worn_identity(b["name"], bodies, sc, titles_of)})

    # The stage roster is who ACTED this beat; the identity space is who
    # this chat could name. Authored prose is gated against the second.
    cast_parts = _composer_extra_parts(ctx, p_name)
    body_scents = _body_scents(ctx)
    body_descriptions = _body_descriptions(ctx, sc)
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
        # A charter body the stored scene never stood was still somewhere:
        # where its charter placed it. Read as "nowhere", every body the
        # resolve stood this beat rendered as walking in on the people it had
        # been standing beside -- nine of nine stands on the playerless
        # Aldermill run, round 5 (2026-09-23), each filed to memory as an
        # arrival.
        prev_room = room_of(prev_scene, str(mover)) or _charter_place_before(
            ctx, sc, str(mover))
        if not new_room or prev_room == str(new_room):
            continue
        if not _mover_is_a_body(sc, str(mover)):
            continue
        moves.append((str(mover), prev_room, str(new_room)))

    # A body that crosses rooms performs one act per room it is in, and an
    # observer is entitled to the legs that happened where their channel
    # stood (PA1 -- `director_movement.crossing_legs` holds the rule and the
    # live case). Only a walk past ONE boundary is here: past it there are
    # rooms in the middle that neither end has a channel to, and the beat's
    # single observable surface covers all of them.
    crossed_legs = _multi_room_legs(sc, moves)

    # THE OUTCOME IS THE RESOLVED BEAT, ONCE. The interaction loop's
    # between-declaration deliveries (`delivered_views`) are what each mind
    # was shown BEFORE the resolve decided the beat -- the context its next
    # declaration was made from, which the loop keeps for exactly that. They
    # used to be appended here as well, pre-rendered, after every percept
    # this stage builds from the same lines and acts through its own gates:
    # every declared line reached a watching character twice, once as the
    # loop's draft and once as said, and their memory kept both (7 outcome
    # views; one walk read three times; playerless Aldermill round 9,
    # 2026-09-23). The drafts carried none of this stage's gates either
    # (`docs/UNBUILT_IDENTITY.md` 1.39) -- at idx 13 one delivered by sight
    # an act this stage refused -- so dropping them subtracts only what the
    # resolve did not stand behind.

    base_ledger = dict(_composer_prev_ledger(ctx))
    base_ledger.update(ctx.get("_composer_turn_ledger") or {})
    full_player_render = _explicit_look_intent(interp)
    # Who looked around this beat: the cone subtracts nothing for them
    # (`effective_facing` reads the marker on this working copy). Stamped
    # by `_composer_outcome` BEFORE the pass opened -- a write here, inside
    # the pass, is the staleness the pass exists to prevent.
    _swept_names = set(sc.get("_sweeping") or ())
    _ubiq = _ubiquitous_names(sc)

    # EVERY line this beat produced, until a view takes it.
    #
    # This watched background presences alone until 2026-09-09, because a
    # burner answering into silence is the case it was written for. The class
    # is not the speaker's: chat 122 turn 3 dropped two lines from a CAST
    # character and one from the player, all three to the same stale relation,
    # and `perception_outcome` raised nothing at all -- the only alarm in the
    # whole turn came from the narrator's fidelity check, after it had already
    # invented a replacement line to cover the hole. A produced line reaching
    # no view is either a firewall refusal worth saying out loud or a fault,
    # and one that says nothing is indistinguishable from the two.
    unheard = {(str(d.get("speaker") or "").strip(),
                str(d.get("exact_quote") or ""))
               for d in enriched_dlog
               if str(d.get("exact_quote") or "").strip()}
    # Which of them some placed listener other than the speaker was offered.
    offered = set()
    clean_views, observations, ledger, company = {}, {}, {}, {}
    episodes, episode_meta = {}, {}
    # Sleepers this beat's sounds woke (`_sleep_hears`), for the commit to
    # end their sleep -- the stage that renders the beat does not write it --
    # and every ear a blast reached past `BLAST_DB` (`_blast_exposure`), for
    # the commit to dull.
    woken, exposures = {}, {}
    from world.spatial import blast_possible
    _blast_possible = blast_possible(sc, beat_sounds)
    for p in perceivers:
        pid = str(p["id"])
        name = p["name"]
        is_player_view = _is_player_view(pid)
        # See the note in the act stage: empty is a record, not a gap.
        seen_bodies = set()
        display_map = {}
        prev_standing, prev_described = _composer_prev_state(base_ledger, pid)
        # THE WOKEN BEAT (DESIGN_SOUND_FIELD § 17). `wake_at` is None for an
        # awake mind (the whole beat is theirs) and, for a sleeper a sound
        # woke this beat, the `beat_events` index of what woke them: they
        # perceive what came AFTER it as an awake mind would -- the room
        # they wake in, who is there, what is said -- and nothing from
        # before, which happened while they slept. A waking the beat cannot
        # place (`_beat_position` None) is read as the end of the beat: the
        # standing state alone, since no event can be said to have followed
        # it. The ledger is empty for them: a mind that just woke has no
        # record, and the world arrives as background, never as a claim
        # that any of it just moved (`standing_verdicts`).
        wake_at, wake_step, woke_percept = None, None, None
        if p.get("awareness") in NON_AWAKE_GATED:
            name_cf = name.casefold()
            targeted = any(
                str(d.get("intended_target") or "").casefold() == name_cf
                for d in enriched_dlog)
            cause = (amap.get(name_cf) or {}).get("cause", "").lower()
            pain = any(w in cause for w in _ling("_PAIN_CUES"))
            # WHAT REACHED THIS MIND'S EAR, AND WHETHER IT WOKE THEM
            # (DESIGN_SOUND_FIELD § 13, `_sleep_hears`). A sleeper the sound
            # wakes is told what woke them, then the rest of the beat from
            # that moment on (§ 17, below); the commit ends their sleep
            # (`woken`), and from the next beat they perceive as anyone
            # awake does. A sedated or unconscious mind is not woken by a
            # sound, and keeps the residue's intrusion where a loud one
            # reached it.
            woke, loud_event, woke_at = _sleep_hears_where(
                ctx, sc, name, p.get("room"), enriched_dlog,
                events=beat_sounds, prev_scene=prev_scene,
                senses=p.get("sense_card"),
                name_forms=_own_name_forms(ctx, name),
                order=_beat_position)
            if woke and not (p["awareness"] == "asleep"
                             and _asleep_when_the_beat_began(chat["id"], name)):
                woke = ""
            if _blast_possible:
                _exposed = _blast_exposure(
                    ctx, sc, name, p.get("room"),
                    _sound_field_for(ctx, sc, name, p.get("room"),
                                     events=beat_sounds), beat_sounds)
                if _exposed is not None:
                    exposures[name] = _exposed
            if woke:
                woken[name] = {"by": woke}
                note_step_decision(
                    "sleep", name, "woken",
                    "a sound reached a sleeper's ear and woke them (%s)" % woke)
            percepts = composer.residue_percepts(
                p["awareness"], targeted=targeted, loud_event=loud_event,
                pain=pain, woke=woke)
            company[pid] = []       # an unconscious observer sees nobody
            if woke:
                woke_percept = percepts[0]
                wake_at = woke_at if woke_at is not None else len(beat_events)
                wake_step = _step_index_of(wake_at)
                prev_standing = frozenset()
                note_step_decision(
                    "sleep", name, "remainder",
                    "the woken mind perceives the beat from %s on"
                    % ("event %d" % wake_at if woke_at is not None
                       else "its end (the waking is unplaced)"))
        if woke_percept is not None or p.get("awareness") not in NON_AWAKE_GATED:
            # What of the beat's one-beat sounds is this mind's: all of them
            # for an awake mind; for a woken one, only those the beat places
            # after the waking (an unplaced sound has no moment to be after).
            if wake_at is None:
                _my_now, _my_then = _now_sounds, _then_sounds
            else:
                _my_now = []
                _my_then = [
                    e for e in _then_sounds
                    if (lambda at: at is not None and at > wake_at)(
                        _beat_position("event", e))]
            _my_sounds = beat_sounds if wake_at is None else list(_my_then)
            others = [b for b in bodies
                      if not _is_the_observer(sc, b["name"], name)]
            # A SWEEP IS A SWEEP FOR WHOEVER MADE IT: the player's full
            # re-render, or any body whose act this beat looked around.
            p["sweep"] = (is_player_view and full_player_render) \
                or name in _swept_names
            # A WALK THE BEAT DID NOT FINISH IS THE WALKER'S TO KNOW: where
            # it got to and where it is still going (`walk_underway`). The
            # event text can say "climbs all the way to the top floor" while
            # the paces left the body a flight short; without this the page
            # followed the text (Larch Hill turn 3, 2026-10-04).
            p["walk_underway"] = _walk_underway(sc, res, name)
            # WHAT THIS BODY'S OWN ACT LOOKED AT on the horizon this beat
            # (`world.vistas.looked_vistas`): delivered as an event.
            p["looked_vistas"] = _looked_vistas(sc, res, interp, name, p_name, ctx,
                                                senses=p.get("sense_card"))
            # ...and every look of its own, for what it found FAR OFF
            # (`world.landscape.looked_far`, matched where the view is
            # composed, against the same far walk the view reads).
            p["own_looks"] = _own_looks(res, interp, name, p_name, ctx)
            # ...and what this beat put in its hands, read as a look is
            # (`_things_read_by`'s HANDLED admission).
            p["own_handled"] = _own_handled(sc, res, name)
            display_map = composer.observer_display_map(
                sc, name, others, known, p.get("sense_card"))
            self_forms = _composer_self_forms(
                name, self_forms_by_name.get(name),
                bodies_by_name.get(name), joint_labels, display_map)
            gate = _authored_prose_gate(
                ctx, "perception_outcome", name, known, identity_space)
            field = _sound_field_for(ctx, sc, name, p.get("room"),
                                     events=beat_sounds)
            # A BLAST AT THIS EAR (DESIGN_SOUND_FIELD § 13): measured where
            # anything this beat could reach `BLAST_DB` at all, for the
            # ringing this view tells and the shift the commit writes.
            p["blast_exposure"] = _blast_exposure(
                ctx, sc, name, p.get("room"), field, beat_sounds) \
                if _blast_possible else None
            if p["blast_exposure"] is not None:
                exposures[name] = p["blast_exposure"]
            percepts = _composer_standing_percepts(
                sc, p, name, others, display_map, known,
                entity_state=p.get("entity_state")
                or _own_body_state(sc, name),
                appearance_changed=appearance_changed,
                appearance_deltas=(appearance_deltas
                                   if is_player_view else None),
                prev_seen=_composer_prev_seen(base_ledger, pid),
                seen_out=seen_bodies,
                gate=gate,
                extra_parts=cast_parts, body_scents=body_scents,
                body_descriptions=body_descriptions,
                # Compression belongs only to player-facing prose. NPC
                # cognition keeps every other visible body's complete
                # appearance/attire surface. The observer's own body is not
                # in `others`; its current card + self.attire own that data.
                prune_appearance=(is_player_view
                                  and not full_player_render),
                self_forms=self_forms,
                self_pronouns=p.get("pronouns"),
                sound=field, prev_standing=prev_standing,
                prev_scene=prev_scene,
                regions=regions)
            if woke_percept is not None:
                # The waking leads the woken mind's view and episode
                # (`composer.render_view`, `render_episode`: the residue's
                # `woke` sentence, then the remainder).
                percepts.insert(0, woke_percept)
            # SOUND ARRIVES AFTER WHAT MADE IT (wave B2): a sound whose
            # maker this observer SEES far enough off is held back here and
            # told after the act it was seen doing, below, once the beat's
            # events have their places (`_sounds_after_sight`).
            _after_sight = {id(event): (after, source) for event, after, source
                            in _sounds_after_sight(sc, name, _my_now)}
            _held_sounds = []
            if _my_sounds:
                # WHERE IT HAPPENED, and then everywhere else it reached.
                # A signal is received whole only in its own room, so that
                # room's observers get the authored detail through the same
                # admission gate the establish stage uses...
                _here_sounds = [
                    e for e in _my_now
                    # A walker's own footfalls are no news to the walker,
                    # and a walker in plain view is seen walking, not
                    # heard: the tread reaches whoever cannot see them.
                    if not (e.get("tread") and (
                        str(e.get("source") or "") == str(name)
                        or (str(e.get("room") or "") == str(p.get("room") or "")
                            and visual_level_between(
                                sc, name, str(e.get("source") or "")) == "full")))]
                _held_sounds.extend(
                    (e, *_after_sight[id(e)]) for e in _here_sounds
                    if id(e) in _after_sight
                    and str(e.get("room") or "") == str(p.get("room") or "")
                    and _reaches_this_ear(sc, name, p.get("room"), field,
                                          beat_sounds, e))
                # KEYED TO THE BEAT (`_AMBIENT_BEAT_BAND`; round 2, lane B,
                # UNBUILT_PERCEPTION § 2.36): a beat's own sound is not
                # standing state, and keyless it rendered lowercase in the
                # view's background half, after the furniture ("... You see
                # a person of unremarkable appearance. a flat crack of
                # musket fire."). Every sound the beat makes -- here, from
                # the next room, or held after its seen maker -- lands in
                # the beat half, after the acts that made it.
                percepts.extend(
                    _gated_ambient_percepts(
                        gate,
                        [e for e in _here_sounds if id(e) not in _after_sight
                         # Through the listener's own ear (wave B1): a
                         # covered or blast-dulled ear grades a sound in its
                         # own room on the field first.
                         and _reaches_this_ear(sc, name, p.get("room"), field,
                                               beat_sounds, e)],
                        p.get("room"), order_key=_AMBIENT_BEAT_BAND))
                # ...THEN THE NEAR FIELD: a sound in a room the listener's
                # own composite grid places is a one-beat source on that
                # room's centre, spread through the doorway it came by and
                # admitted where the field grades it above `none` -- the
                # establish stage's step (`heard_events`), which this pass
                # never took. Rewritten to the observer's room so
                # `ambient_percepts`' own-room admission takes it; the gate
                # still scrubs the text.
                afar = heard_events(
                    sc, name, _my_now, room=p.get("room"),
                    turn_idx=getattr(ctx.turn, "idx", None),
                    crowds=ctx.get("_sound_crowds"))
                # A sound tied to its moment is graded in that moment's world,
                # from where this listener stood then (see `_sound_moments`).
                for _sound in _my_then:
                    _then = _sound_moments[_sound["_at"]]
                    _there = room_of(_then, name) or p.get("room")
                    if str(_sound.get("room") or "") == str(_there or ""):
                        afar.append((_sound, "full"))
                        continue
                    afar.extend(heard_events(
                        _then, name, [_sound], room=_there,
                        turn_idx=getattr(ctx.turn, "idx", None),
                        crowds=ctx.get("_sound_crowds")))
                if afar:
                    here = str(p.get("room") or "")
                    _kept = []
                    for event, _level in afar:
                        moved = {**event, "room": here, "room_id": here,
                                 "source_room": here}
                        if id(event) in _after_sight:
                            _held_sounds.append((moved, *_after_sight[id(event)]))
                        else:
                            _kept.append(moved)
                    percepts.extend(_gated_ambient_percepts(
                        gate, _kept, p.get("room"),
                        order_key=_AMBIENT_BEAT_BAND))
                # ...and beyond the near field it is a BEARING AND A
                # CHARACTER, never a sentence and never a place. The rooms
                # this listener's own composite already places are the near
                # field's and are skipped, so nobody is answered twice about
                # one sound; the room the sound came from never leaves
                # `distant_sounds`, which turns it into a direction against
                # this observer's own facing (DESIGN_SOUND_DECIBELS.md § 3).
                percepts.extend(composer.distant_sound_percepts(
                    distant_sounds(
                        sc, name, room=p.get("room"),
                        turn_idx=getattr(ctx.turn, "idx", None),
                        near_rooms=(field.grid.offsets if field else ()),
                        crowds=ctx.get("_sound_crowds"),
                        events=_my_now)))
            # LOUD SOUND IS FELT (wave B2): the beat's blows -- a sound tied
            # to its moment included -- and the steady trembling of what
            # runs, on the touch channel, whatever this body can hear.
            percepts.extend(_felt_percepts_for(ctx, sc, name, p.get("room"),
                                               _my_sounds))
            spatial = p.get("spatial_to_sources") or {}
            visual = p.get("visual_channel_to_sources") or {}
            recognized, unknown = _composer_unknown_sources(
                name, known, ident_roster, bodies_by_name)
            order = 0
            _seen_acts = {}         # actor -> the order of their last seen act
            # WHERE EACH DELIVERED TELL SHOWED, among the beat's events
            # (`_cue_slots`); what no event of its giver can hold is minted
            # after the loop with the demeanor, as before.
            cue_slots, unplaced_manifest = _cue_slots(
                sc, p.get("source_manifest"), name, beat_events)
            # THE RELATION AS IT STOOD WHEN THE EVENT HAPPENED, rather than
            # as it stands once the beat is over. Identical to the precomputed
            # map whenever no mover's cut is still ahead of this event -- which
            # is every event of a beat nobody crossed, and every event from the
            # last cut onward in the rest -- so the ordinary beat still pays one
            # dict lookup.
            #
            # IT MAY ONLY CHANGE THE ANSWER, NEVER THE ROSTER. A counterparty
            # the composed map does not hold is one this observer has no source
            # for, and it stays refused: this is about WHEN a channel was
            # graded, not about who is gradable.
            _as_of_scenes = {}

            def _as_of(at_index, _observer=name, _p=p):
                """`(scene, observer_room, sound_field)` for this event.

                `sc` itself, by identity, whenever no mover's cut is still
                ahead -- so the ordinary beat allocates nothing and every
                downstream reader is handed exactly the object it was handed
                before."""
                if at_index in causal_moments:
                    key = ("causal", at_index)
                    cached = _as_of_scenes.get(key)
                    if cached is None:
                        then = causal_moments[at_index]
                        room = room_of(then, _observer) or _p.get("room")
                        cached = (then, room, _sound_field_for(
                            ctx, then, _observer, room, events=beat_sounds))
                        _as_of_scenes[key] = cached
                    return cached
                pending = frozenset(
                    b for b, cut in movement_cuts.items() if at_index < cut)
                if not pending:
                    return None
                cached = _as_of_scenes.get(pending)
                if cached is None:
                    then = scene_as_of(prev_scene, sc, movement_cuts, at_index)
                    room = room_of(then, _observer) or _p.get("room")
                    # ONE BEAT, ONE FIELD (PC3) still holds -- it is the same
                    # beat's field, built over the geometry the beat had at
                    # this point rather than the geometry it ended with.
                    cached = (then, room, _sound_field_for(
                        ctx, then, _observer, room, events=beat_sounds))
                    _as_of_scenes[pending] = cached
                return cached

            def _sight_as_of(counterparty, at_index, _observer=name,
                             _senses=p.get("sense_card")):
                """Sight to a counterparty AS IT STOOD WHEN THE EVENT
                HAPPENED. The beat-wide map (`_saw_across_beat`) answers
                yes if either end of the beat could see, which is right for
                a beat nobody crossed and wrong for an event after a move:
                measured (scratch play 2026-09-14, chat 4 turn 2) a nurse
                walked from the sickroom to the scullery, the patient then
                clenched his fingers in the quilt, and her view carried the
                gesture as SIGHT through a shut door and two rooms, because
                she had seen him when the beat began. Where either body
                moved this beat, the scene at the event's moment decides."""
                if at_index not in causal_moments and (not movement_cuts or not (
                        _observer in movement_cuts
                        or counterparty in movement_cuts)):
                    return visual.get(counterparty, False)
                moment = _as_of(at_index)
                then = sc if moment is None else moment[0]
                if room_of(then, _observer) is None:
                    return visual.get(counterparty, False)
                return composer._sense_graded(
                    visual_level_between(then, _observer, counterparty,
                                         _senses),
                    "sight", _senses) != "none"
            def _channel_as_of(counterparty, at_index, _observer=name,
                               _spatial=spatial, _field=field,
                               _room=p.get("room")):
                standing = _spatial.get(counterparty)
                moment = _as_of(at_index)
                if moment is None:
                    # ONE BEAT, ONE FIELD (PC3), for a line no moment cites
                    # too. The perceiver map was stamped on a field built
                    # before the beat's sounds were known, so a background
                    # presence's line, a Director row and every line of an
                    # archived beat were graded as if the falls were not
                    # roaring while the cast's lines beside them were lost
                    # to it (audit agents_perception F4, 2026-11-01:
                    # `line heard without the beat's events=full / with
                    # them=none`). Restamped on THIS observer's field for
                    # the beat -- the one its soundscape, ambient sounds
                    # and acts are graded on. A relation the rescue kept
                    # from the beat's start (`was_reachable_at_beat_start`)
                    # is a channel the beat itself closed, and stays as it
                    # was kept.
                    if (isinstance(standing, dict) and _field is not None
                            and not standing.get("was_reachable_at_beat_start")):
                        standing = spatial_rel_between(
                            sc, _observer, counterparty, observer_room=_room,
                            target_room=_source_rooms.get(counterparty)
                            or room_of(sc, counterparty),
                            sound=_field)
                    return standing, measured_proximity_rel(
                        sc, _observer, counterparty)
                then, observer_room, field_then = moment
                rel = spatial_rel_between(
                    then, _observer, counterparty,
                    observer_room=observer_room,
                    target_room=room_of(then, counterparty),
                    sound=field_then)
                return rel, measured_proximity_rel(
                    then, _observer, counterparty)

            for at_index, beat_event in enumerate(beat_events):
                if wake_at is not None and at_index <= wake_at:
                    # BEFORE THE WAKING, OR THE WAKING ITSELF (§ 17): what
                    # woke them is told by the residue, without its words;
                    # what came before it happened while they slept. The
                    # tells placed here go with it.
                    order += 1
                    continue
                for _giver, _cue in cue_slots.get(at_index, ()):
                    # A TELL IS PLACED WHERE IT SHOWED ONLY IF IT COULD BE SEEN
                    # THERE. It was admitted on the end-of-beat relation
                    # (`_delivered_manifest`), so an observer who could not see
                    # its giver just before the step -- a line said behind a
                    # shut door, then a walk in -- was shown a visual sign at a
                    # moment it had no sight of (review of 9a29099a). The
                    # moment between the previous entry and this one, the
                    # step's own move still pending; failing it, the cue goes
                    # after the beat, where it was admitted, as before.
                    if not _sight_as_of(_giver, at_index - 1):
                        unplaced_manifest.setdefault(_giver, {}).setdefault(
                            "cues", []).append(_cue)
                        continue
                    percept = _cue_percept(
                        sc, _giver, _cue, name, display_map, recognized,
                        unknown, order, sense_card=p.get("sense_card"))
                    if percept:
                        percepts.append(percept)
                        order += 1
                if beat_event.get("kind") != "speech" and execution_statuses.get(at_index) == "unresolved":
                    # SAID OUT LOUD, as the onset pass says it: a bare
                    # `continue` here left no trace of a withheld act, so an
                    # act the world never refused vanished from every view
                    # with nothing in the drawer to say where it went -- 54
                    # of them across chats 175-177 (2026-10-19).
                    note_step_decision(
                        "act_percept", "%s -> %s" % (
                            beat_event.get("actor") or "?", name),
                        "refused",
                        "the beat verified this act as unexecuted")
                    continue
                event_scene = causal_moments.get(at_index, sc)
                event_observer_room = room_of(event_scene, name) or p.get("room")
                if beat_event.get("kind") == "speech":
                    d = beat_event.get("entry") or {}
                    speaker = d.get("speaker", "?")
                    if _is_the_observer(
                            sc, speaker, name, cast_aliases.get(name)) or (
                            pid == "player"
                            and is_player_speaker(speaker, chat)):
                        order += 1
                        continue
                    # An AUDIENCE is a listener the scene stands somewhere.
                    # A line offered to none -- a woman thinking aloud alone
                    # in a playerless bubble -- had nobody to reach, which is
                    # neither a refusal nor a fault (see `offered` below).
                    if p.get("room"):
                        offered.add((str(speaker or "").strip(),
                                     str(d.get("exact_quote") or "")))
                    rel, _prox = _channel_as_of(speaker, at_index)
                    if rel is None:
                        if str(speaker).strip().casefold() in _ubiq:
                            rel = {"same_room": True, "barrier": "open",
                                   "distance": "near", "note": (
                                       "bodiless voice, present throughout")}
                        else:
                            _moment = _as_of(at_index)
                            _then = sc if _moment is None else _moment[0]
                            _obs_room = (p.get("room") if _moment is None
                                         else _moment[1])
                            _field = (_sound_field_for(
                                ctx, sc, name, p.get("room"),
                                events=beat_sounds) if _moment is None
                                else _moment[2])
                            # `speaker_room` is stamped off the composed
                            # scene, so for a body that MOVED this beat it is
                            # where they ended -- and only for such a body is
                            # the moment's own scene the better answer. The
                            # precedence is otherwise untouched: a presence
                            # two entities answer to is placed by the stamp
                            # and not by a name `room_of` cannot resolve
                            # (tests/test_background_presence_channels.py).
                            # A body the moment's scene does not hold -- a
                            # charter figure voiced this beat, standing only
                            # in the room its declaration gave it -- keeps the
                            # stamp: `None` here refused every such line to a
                            # listener beside it (playerless Aldermill round
                            # 4, 2026-09-23, t4).
                            sp_room = (
                                (room_of(_then, speaker)
                                 or d.get("speaker_room"))
                                if _moment is not None and (speaker in movement_cuts
                                                           or at_index in causal_moments)
                                else (d.get("speaker_room")
                                      or room_of(_then, speaker)))
                            # ONE BEAT, ONE FIELD. This fallback used to omit
                            # `sound`, so a listener the composite grid could
                            # not place fell through to the edge model while
                            # every graded source was answered by the field --
                            # and the two floors disagreed about one line in
                            # one beat (PC3, F61's shape with the roles
                            # reversed): the nearest listener across the most
                            # open edge in the house heard less than one
                            # behind a shut door.
                            rel = spatial_rel_between(
                                _then, name, speaker,
                                observer_room=_obs_room,
                                target_room=sp_room,
                                sound=_field)
                    can_see = _in_plain_view(
                        rel, _sight_as_of(speaker, at_index))
                    display = _attributed_label(
                        speaker, name, recognized=recognized,
                        display_map=display_map,
                        bodies_by_name=bodies_by_name, can_see=can_see,
                        unseen=_unseen_voice_label(), appearances=appearances,
                        cast_aliases=cast_aliases)
                    percept = composer.speech_percept(
                        d, _with_comm_channel(
                            event_scene, rel, speaker=speaker, observer=name,
                            observer_room=event_observer_room,
                            speaker_room=((room_of(event_scene, speaker)
                                           or d.get("speaker_room"))
                                          if at_index in causal_moments
                                          else d.get("speaker_room"))),
                        name, display=display, can_see=can_see,
                        proximity=_prox,
                        order_key=order, observer_id=pid,
                        senses=p.get("sense_card"),
                        voice=_voice_register_for(ctx, speaker),
                        voice_sound=_voice_sound_for(ctx, speaker),
                        prev_standing=prev_standing,
                        bearing=_speech_bearing(event_scene, name, speaker,
                                                can_see, rel),
                        addressed=_line_is_to(
                            ctx, event_scene, name, d,
                            aliases=cast_aliases.get(name) or ()),
                        name_forms=_own_name_forms(ctx, name))
                    if percept:
                        percepts.append(percept)
                        unheard.discard(
                            (str(speaker or "").strip(),
                             str(d.get("exact_quote") or "")))
                    order += 1
                    continue

                if beat_event.get("kind") == "silence":
                    # THE UNANSWERED ADDRESS (D6). Into the ADDRESSER'S view
                    # alone: it is a fact about what they were listening
                    # for, and to anybody else in the room a person who did
                    # not speak is simply a person who did not speak. The
                    # label goes through the same display map every other
                    # attribution does, so a stranger stays a stranger.
                    if not _is_the_observer(
                            sc, beat_event.get("addresser"), name,
                            cast_aliases.get(name)) and not (
                            pid == "player" and is_player_speaker(
                                beat_event.get("addresser"), chat)):
                        order += 1
                        continue
                    # ...and only about a body this observer can actually
                    # place. `display_map` is the admission: it holds the
                    # bodies this view has already composed a presence for,
                    # under this observer's own label for each. Without one
                    # the sentence would have to say "a voice says nothing",
                    # which is not a fact anybody has.
                    target = beat_event.get("actor")
                    percept = composer.silence_percept(
                        display_map.get(target), order_key=order)
                    if percept:
                        percepts.append(percept)
                    order += 1
                    continue

                if beat_event.get("kind") == "communication":
                    actor = beat_event.get("actor")
                    entry = beat_event.get("entry") or {}
                    if _is_the_observer(
                            sc, actor, name, cast_aliases.get(name)):
                        order += 1
                        continue
                    rel, _prox = _channel_as_of(actor, at_index)
                    if rel is None:
                        order += 1
                        continue
                    can_see = _in_plain_view(rel, _sight_as_of(actor, at_index))
                    display = _attributed_label(
                        actor, name, recognized=recognized,
                        display_map=display_map,
                        bodies_by_name=bodies_by_name, can_see=can_see,
                        unseen=_unseen_voice_label(), appearances=appearances,
                        cast_aliases=cast_aliases)
                    percept = composer.communication_percept(
                        entry, _with_comm_channel(
                            event_scene, rel, speaker=actor, observer=name,
                            observer_room=event_observer_room),
                        name, display=display, can_see=can_see,
                        proximity=_prox,
                        order_key=order, observer_id=pid,
                        senses=p.get("sense_card"),
                        addressed=_line_is_to(
                            ctx, event_scene, name, entry,
                            aliases=cast_aliases.get(name) or ()))
                    if percept:
                        percepts.append(percept)
                    order += 1
                    continue

                act = beat_event
                actor = act.get("actor")
                if _is_the_observer(
                        sc, actor, name, cast_aliases.get(name)):
                    order += 1
                    continue
                rel, _prox = _channel_as_of(actor, at_index)
                # AN EVENT WITH NO BODY BEHIND IT HAPPENED WHERE ITS TARGETS
                # ARE (`_sourceless_event_rel`): a scheduled event or a
                # world process is placed nowhere, so its relation to every
                # observer read "no known spatial channel" and the whole of
                # it was refused -- chat 160 turn 11, an elevator's power
                # failing, the free fall and the cables snapping, refused
                # for the two people riding it.
                _sourceless = False
                if not room_of(event_scene, actor):
                    _placed = _sourceless_event_rel(
                        event_scene, name, (act.get("event") or {}).get("targets"),
                        event_observer_room)
                    if _placed is not None:
                        rel, _sourceless = _placed, True
                if rel is None:
                    order += 1
                    continue
                # NO PRE-SKIP ON SIGHT. `composer.act_percept` decides the
                # arc: a body in the observer's rear arc is heard and not
                # seen (PM5), and everything else is refused at its sight
                # gate. The onset pass has always handed it `can_see` and
                # let it rule; this pass skipped unseen and rear-arc actors
                # before the call, so the hearing percept the composer mints
                # for the rear arc was dead on every outcome beat.
                can_see = _in_plain_view(rel, _sight_as_of(actor, at_index))
                legs = _legs_of_actor(sc, crossed_legs, actor)
                if at_index not in causal_moments and legs and not _channel_to_every_leg(
                        sc, prev_scene, name, p.get("room"), legs,
                        p.get("sense_card")):
                    note_step_decision(
                        "act_percept", "%s -> %s" % (actor, name), "refused",
                        "the act crossed %d rooms and this observer's channel "
                        "did not stand in all of them" % len(legs))
                    order += 1
                    continue
                display = _attributed_label(
                    actor, name, recognized=recognized,
                    display_map=display_map, bodies_by_name=bodies_by_name,
                    can_see=True, unseen="", appearances=appearances,
                    cast_aliases=cast_aliases)
                if _sourceless:
                    # Nobody did it: the surface is the whole sentence, never
                    # "The unfamiliar person fluorescent tube flickers".
                    display = ""
                elif not _source_is_a_body(event_scene, actor):
                    # A THING did it, and is called what it is.
                    display = _thing_label(event_scene, actor)
                # A BODY THE SURFACE NAMES IS A PERCEPT OF ITS OWN (PX5),
                # asked before the identity scrub rewrites the names.
                surface, _cut = _act_surface_admission(
                    act.get("attempt"), actor=actor, observer=name,
                    forms_by_body=forms_by_body, perceived=seen_bodies,
                    who="%s -> %s" % (actor, name))
                if _cut and not surface:
                    order += 1
                    continue            # refusal already recorded
                # The actor's own leading name comes off BEFORE the scrub:
                # scrubbed first, it became the observer's label and the
                # renderer put the label in front of it again ("The
                # grey-streaked journeyman the grey-streaked journeyman bears
                # down", round 4 replay, 2026-09-23).
                surface = composer._peel_own_name(surface, actor)
                surface = _composer_scrub_surface(
                    surface, name, recognized, unknown,
                    labels=display_map)
                surface = resolve_action_referents(
                    surface, act.get("event") or {}, {
                        **{key: value for key, value in display_map.items()},
                        name: "you", actor: display,
                    })
                percept = composer.act_percept(
                    event_scene, act.get("event") or {}, name, actor, rel,
                    display=display, can_see=can_see,
                    sight=_sight_detail(event_scene, name, actor, rel,
                                        senses=p.get("sense_card")),
                    self_forms=self_forms,
                    self_pronouns=p.get("pronouns"),
                    other_forms=tuple(
                        form
                        for other_name, other_names
                        in self_forms_by_name.items()
                        if other_name != name
                        for form in (other_names or ())),
                    order_key=order, observer_id=pid, surface=surface,
                    # WHAT AN ACT BEHIND THIS OBSERVER SOUNDS LIKE: graded on
                    # the field of the act's own moment, as `event_scene`
                    # is, at the gait the act declares or else the one the
                    # beat walked its actor at, unless it filed a sound of
                    # its own (`composer.act_percept`).
                    sound=(_as_of(at_index)[2] if at_index in causal_moments
                           else field),
                    gait=(_act_gait(act.get("event"))
                          or _gaits.get(str(actor or "").strip().casefold())),
                    own_sound=tuple(
                        str(part) for part in (act.get("causal_span") or ())
                    ) in _sounding_spans)
                if percept:
                    percepts.append(percept)
                    if percept.channel == "sight":
                        _seen_acts[str(actor or "").strip().casefold()] = order
                order += 1
            # ...AND THE SOUND OF A THING SEEN FAR OFF COMES AFTER THE SIGHT
            # OF IT (wave B2): held back above, it is told right after the
            # last act of its maker this observer saw this beat, saying it
            # came after; a maker seen doing nothing keeps it where it was.
            for _event, _after, _source in _held_sounds:
                _at = _seen_acts.get(_source.strip().casefold())
                percepts.extend(_gated_ambient_percepts(
                    gate, [_event], p.get("room"),
                    **({"order_key": _at + 0.5, "after": _after}
                       if _at is not None
                       else {"order_key": _AMBIENT_BEAT_BAND})))
            # A BODY THAT WAS THERE WHEN YOU CAME IN DID NOT COME IN. An
            # observer who came into the room this beat, in the same causal
            # step as the mover -- the two walked it side by side -- or after
            # them, from whichever room, found them already there; only a
            # mover who came in after the observer, or on one who was there
            # all along, came in on them. Read off the beat's causal worlds;
            # where the beat records no steps the order is unknown and the
            # line stands. Scratch story 166 turn 4607, replayed with the
            # follow carrying her (2026-10-09), told the player "Hester Gale
            # comes in." on the stair they climbed together; turn 4590 (idx
            # 5), where the player went up the rise at the onset and the
            # pilot followed at the resolve, rightly told her the pilot came
            # in (review F4); and a watcher coming in from the yard was told
            # a porter who had come in from the store a step before him "comes
            # in" (review N8).
            _own_from = room_of(prev_scene, name) if prev_scene else None
            for mover, from_room, to_room in moves:
                if same_subject(sc, mover, name):
                    continue
                if p.get("room") not in (from_room, to_room):
                    continue
                if wake_at is not None:
                    # A BODY THAT WAS THERE WHEN YOU WOKE DID NOT COME IN
                    # (§ 17): only a crossing the beat's steps place after
                    # the waking step is the woken mind's to have seen;
                    # with no step on either side, it is who is there
                    # (the presence percepts), not an arrival.
                    _theirs = _arrival_step(mover, to_room)
                    if wake_step is None or _theirs is None \
                            or _theirs <= wake_step:
                        continue
                if _own_from and _own_from != to_room \
                        and p.get("room") == to_room and from_room != to_room:
                    _mine = _arrival_step(name, to_room)
                    _theirs = _arrival_step(mover, to_room)
                    if _mine is not None and _theirs is not None \
                            and _theirs <= _mine:
                        continue
                _graded = (lambda scene: composer._sense_graded(
                    visual_level_between(scene, name, mover,
                                         p.get("sense_card")),
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
            # A substance event and an unplaced tell have no moment in the
            # beat; a woken mind, which has only the moments after its
            # waking, gets neither (§ 17) -- the demeanor, a standing look,
            # it still gets.
            for event in ([] if wake_at is not None
                          else (substance_events or [])):
                if not isinstance(event, dict) or event.get("op") != "add":
                    continue
                percept = composer.substance_percept(
                    event, substance_event_clause(event, you=name, scene=sc),
                    order_key=order)
                if percept:
                    percepts.append(percept)
                    order += 1
            minted, order = _manifest_percepts(
                sc, (unplaced_manifest if wake_at is None else {
                    _s: {_k: _v for _k, _v in _e.items() if _k != "cues"}
                    for _s, _e in (unplaced_manifest or {}).items()
                    if isinstance(_e, dict)}),
                name, display_map, recognized,
                unknown, order, sense_card=p.get("sense_card"))
            percepts.extend(minted)
            # THE CARD'S FLOOR, after every builder (`_card_admitted`).
            percepts = _card_admitted(percepts, p.get("sense_card"),
                                      observer=name)
            company[pid] = _composer_company(others, display_map, percepts)
        rendered = composer.render_view(
            percepts,
            mode="player" if is_player_view else "character",
            prev_standing=prev_standing, prev_described=prev_described,
            full_render=is_player_view and full_player_render,
            language=ctx.language)
        # "NOTHING NEW" AND "NOTHING REACHED THIS MIND" ARE DIFFERENT STATES,
        # and storing both as None collapses them. A player view is a DELTA:
        # `render_view` suppresses the standing state this observer was
        # already given, which is right while anything survives it. When
        # nothing does -- no event reached the mind and every standing
        # percept hashes to a key it already holds -- the compression has
        # produced no view at all, `_composer_finish_observer` stores None,
        # and `agents/narration.py` falls through to the compositor's
        # "nothing in particular reaches you" default. That string is a claim
        # about the WORLD, and a false one: the observer is standing in a
        # room, in the light, with company. Measured over chat 98's 38 played
        # beats, `views.player` was null on six (turns 13, 15, 16, 20, 21,
        # 36) and `observations.player` was `[]` on all six, so the narrator
        # was handed no slice and originated the room -- which is the one
        # thing the narrator may not do.
        #
        # Asking for the background is `full_render`'s existing meaning, and
        # it re-renders the SAME percept list, so nothing is admitted that
        # Layer A did not already admit. Nothing in it is marked as this
        # beat's news either: `leads_the_beat` answers "unchanged" for every
        # one of these percepts, so the recovered view lands whole in the
        # background half and reads as context rather than as an event --
        # and `observations_from_render` files it `standing`, which
        # `_render_observed_events` skips, so it reaches the model as the
        # frame it is and never as a numbered obligation.
        # Asked of the NEAR spans: a far line alone is added to a view and
        # is never the whole of one, so it does not stand in for the room
        # the narrator must be handed (`composer.near_text`).
        if (is_player_view and not full_player_render and percepts
                and not composer.near_text(rendered)):
            rendered = composer.render_view(
                percepts, mode="player", prev_standing=prev_standing,
                prev_described=prev_described, full_render=True,
                language=ctx.language)
        _composer_finish_observer(
            ctx, "perception_outcome", pid, name, rendered, known,
            ident_roster, clean_views, observations, ledger,
            spoken_lines=spoken_lines, seen=seen_bodies, labels=display_map,
            # Rolled forward from the PREVIOUS TURN's stored ledger rather
            # than from `base_ledger` (D7): this turn's `perception_act` entry
            # for the same observer is a character-mode render that computes
            # no metadata, and reading it here would reset the record every
            # beat.
            prev_meta=_composer_prev_meta(_composer_prev_ledger(ctx), pid),
            track_standing_meta=is_player_view,
            percepts=percepts)
        if not is_player_view:
            # WHAT HAPPENED, after what this mind witnessed before it acted:
            # every percept the act stage already put in its witnessed
            # episode is left out, by its key (content-hashed, so the same
            # line or act keys alike in both stages; observation ids are
            # positional and do not).
            _w = (((getattr(ctx, "perception_act", None) or {}).get("witnessed") or {})
                  .get(pid) or {})
            _before = set(_w.get("keys") or ())
            # Counted, so an act done twice -- once before this mind acted,
            # once after -- is said once in each half.
            _said = {}
            for _s in _w.get("said") or ():
                _said[_s] = _said.get(_s, 0) + 1
            _after = []
            for q in percepts:
                if q.dedupe_key and q.dedupe_key in _before:
                    continue
                _s = composer.episode_signature(q)
                if _s and _said.get(_s, 0) > 0:
                    _said[_s] -= 1
                    continue
                _after.append(q)
            content, gist, entities = composer.render_episode(
                _after,
                prev_standing=prev_standing,
                prev_described=prev_described, language=ctx.language)
            content, gist = _scrub_episode_identities(
                ctx, "perception_outcome", name, content, gist, known,
                ident_roster)
            episodes[pid] = content
            episode_meta[pid] = {"gist": gist, "entities": entities}
    # AN ANSWER THAT WAS PRODUCED AND NOBODY HEARD IS SAID OUT LOUD. A
    # background presence's line goes through the same grading a cast line
    # does, and grading may correctly leave it reaching nobody -- but a beat
    # in which the NPC answered and nothing carried it is indistinguishable,
    # from every record afterwards, from a beat in which the NPC said
    # nothing. Live on the road, 2026-09-05: a burner answered a direct
    # question, the words reached no view, and the run gave no warning.
    # The line still stands in the beat's own dialogue log (`commit_memory`
    # folds every fired reaction into the persisted event), so the record of
    # who spoke keeps it; what this adds is that the silence is legible.
    for (speaker, quote) in sorted(unheard):
        if (speaker, quote) not in offered:
            # Nobody stood anywhere to be reached: recorded, not alarmed.
            # Eleven of these on one playerless run (2026-09-23) were a
            # character's own lines with no one else in the frame.
            note_step_decision(
                "speech", speaker, "no_audience",
                "no placed listener besides the speaker (%r)" % quote[:80])
            continue
        ctx.add_warning(
            "perception_outcome: %s answered and the line reached no view; "
            "no channel in this beat carried it (%r)"
            % (speaker, quote[:120]))
    merged = dict(base_ledger)
    merged.update(ledger)
    ctx["_composer_turn_ledger"] = merged
    _disguise_leak_checks(ctx, "perception_outcome", clean_views, perceivers, known)
    _inverted_motion_check(ctx, "perception_outcome", clean_views,
                           res.get("resolved_event"))
    out = {
        "views": clean_views,
        "observations": observations,
        "episodes": episodes,
        "episode_meta": episode_meta,
        "composer_ledger": merged,
        "company": company,
    }
    # WHAT THIS BEAT DID TO EARS, for the commit to write (DESIGN_SOUND_FIELD
    # § 13): the sleepers a sound woke, and every ear a blast reached past
    # `BLAST_DB`. Present only where there is something to say, so every
    # other beat's stored outcome is shaped exactly as before.
    if woken:
        out["woken"] = woken
    if exposures:
        out["hearing_exposures"] = exposures
    return out
