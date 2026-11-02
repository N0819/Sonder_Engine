"""The opening pass: `perception_establish` and its composer region
(`_composer_establish`, `_composer_establish_views`, the opening's quoted
lines).

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
    persona_appearance,
    persona_name,
)
from core.db import wget
from world.scene_memo import scene_read_pass
from story.scene import (
    NON_AWAKE_GATED,
    appearance_of,
    apply_awareness_diff,
    awareness_map,
    awareness_of,
    get_scene,
    is_player_speaker,
    persona_of,
    sheet_state,
)
from world.spatial import (
    room_display_name,
    visual_level_between,
    heard_events,
    measured_proximity_rel,
    merge_scene_with_diff,
    room_of,
    spatial_rel_between,
)
from . import composer
from .common import (
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
    character_room,
    character_scene_keys,
)

from agents.perception_common import (
    _is_player_view,
    _is_the_observer,
    _stage_player_room,
)
from agents.perception_bodies import (
    _body_descriptions,
    _body_scents,
    _composer_extra_parts,
    _subject_disguise_context,
)
from agents.perception_senses import (
    _card_admitted,
    _felt_percepts_for,
    _in_plain_view,
    _own_name_forms,
    _sense_card,
    _sound_field_for,
    _source_channels,
    _speech_bearing,
    _voice_register_for,
    _voice_sound_for,
    _with_comm_channel,
)
from agents.perception_identity import (
    _attributed_label,
    _character_known_places,
    _charter_titles_of,
    _composer_identity_space,
    _composer_self_forms,
    _composer_unknown_sources,
    _far_regions,
    _identity_roster,
    _joint_stranger_labels,
    _player_known_places,
    _presence_bodies,
    _unseen_voice_label,
)
from agents.perception_scrub import (
    _authored_prose_gate,
    _composer_company,
    _composer_finish_observer,
)
from agents.perception_standing import (
    _AMBIENT_BEAT_BAND,
    _composer_standing_percepts,
    _gated_ambient_percepts,
)


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

    p_room = player_room_in(sc, ctx, pers=pers, player_name=p_name)
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

    # One registry read for the whole stage; each perceiver's room reuses it
    # through the memo inside (see `chatter_inputs`).
    chatter = chatter_inputs(ctx.chat.id, sc, turn_idx=ctx.turn.idx)
    # ONE READ PASS OVER THE PERCEIVER LOOP (audit agents_perception E1,
    # 2026-11-01): every relation and sight below is a pure read of the
    # scene, and `_presence_bodies`, which writes it, runs after. Nine
    # payload fields nothing read went with the pass (F9:
    # `ambient_location`, `visible_rooms`, the prose `senses`, `attention`,
    # `knows_identity`, `proximity_to_sources`, `behind_sources`,
    # `behind_rooms`, `focus_target`).
    with scene_read_pass(sc):
        perceivers = [{
            "id": "player", "name": p_name, "room": p_room,
            "pronouns": (pers.get("identity") or {}).get("pronouns") or {},
            "room_name": room_display_name(p_rdata, p_room) or "an unspecified area",
            "room_notes": _room_notes_for_view(p_rdata, p_room, ctx, sc),
            "crowds": crowds_for_room(ctx.chat.id, sc, p_room, chatter),
            "chatter": chatter_for_room(
                ctx.chat.id, sc, p_room, chatter,
                attending=attending_this_room(sc, p_name, p_room)),
            "couriers": couriers_for_room(ctx.chat.id, sc, p_room, chatter),
            "notices": artifacts_for_room(ctx.chat.id, sc, p_room, chatter),
            "known_places": _player_known_places(ctx),
            "sense_card": _sense_card(pers),
            "entity_state": p_state,
            **_source_channels(sc, p_name, p_room, sources,
                               senses=_sense_card(pers),
                               sound=_sound_field_for(ctx, sc, p_name, p_room)),
        }]

        for c in ctx.cast:
            sh, act, _ = sheet_state(c)
            r = character_room(sc, sh)
            rdata = (sc.get("rooms") or {}).get(r) if r else None
            c_sources = [s for s in sources if s["name"] != character_name(sh)]
            perceivers.append({
                "id": c["id"], "name": character_name(sh), "room": r,
                # Through the ONE identity reader, never the stored blob: a
                # card that parked its pronouns at top level is repaired only
                # for whoever normalizes, so the raw read handed this view --
                # the one the narrator falls back on -- nothing at all (review
                # 2026-09-07 B12). Same at the two sibling builders below.
                "pronouns": character_identity(sh)["pronouns"],
                "room_name": room_display_name(rdata, r) or "an unspecified area",
                "room_notes": _room_notes_for_view(rdata, r, ctx, sc),
                "crowds": crowds_for_room(ctx.chat.id, sc, r, chatter),
                "chatter": chatter_for_room(
                    ctx.chat.id, sc, r, chatter,
                    attending=attending_this_room(sc, character_name(sh), r)),
                "couriers": couriers_for_room(ctx.chat.id, sc, r, chatter),
                "notices": artifacts_for_room(ctx.chat.id, sc, r, chatter),
                "known_places": _character_known_places(c),
                "sense_card": _sense_card(sh),
                "entity_state": entity_states.get(character_name(sh)) or {},
                **_source_channels(sc, character_name(sh), r, c_sources,
                                   senses=_sense_card(sh),
                                   sound=_sound_field_for(
                                       ctx, sc, character_name(sh), r)),
            })

    # Consciousness gate (rare at opening, but a scenario may start someone
    # unconscious/asleep): overlay the establish diff onto committed conditions.
    amap = apply_awareness_diff(awareness_map(chat["id"]), diff)
    # The gate itself is INSIDE the composer orchestrators, per perceiver
    # (`if p.get("awareness") in NON_AWAKE_GATED`), so this loop stamps the
    # verdict and nothing here needs to partition on it.
    for p in perceivers:
        p["awareness"] = awareness_of(amap, p["name"])

    return _stage_player_room(_composer_establish(
        ctx, sc, perceivers, known, p_name, p_appearance,
        entity_states, sensory_events,
        # The room's other people, placed on `sc` before the composer reads
        # it (see `_presence_bodies`). A scene that opens in a staffed place
        # opens with the staff in it.
        _presence_bodies(ctx, sc, [p["room"] for p in perceivers], chatter)),
        ctx)


#: The three composer regions below each build EVERY observer's view off one
#: finished scene, and each was re-deriving the same objective spatial facts
#: for every builder that asked: sight 5-9x per (observer, body), stations
#: from fifteen callers, anchors from twenty-one, and a light or sound field
#: lookup that serialised the whole scene into its cache key on every hit
#: (review C12). One read pass per region is the "one sight map per observer
#: per stage" that finding asked for, generalised: inside it each objective
#: derivation runs once per distinct question and the answer is handed to
#: every builder. `world/scene_memo.py` holds the contract -- a pass is
#: opened only around a region that derives and does not write, and it
#: re-fingerprints the scene on close to say so if that was ever untrue.
#:
#: Opened INSIDE each region rather than around its call, because the
#: argument list is not part of the read-only region: `_presence_bodies`
#: places the room's other people on `sc`, and it is evaluated as an
#: argument at two of the three call sites.
#:
#: Measured 2026-09-07 on chat 117's 38-room, 22-body scene: composing every
#: observer's presence, pose and environment percepts took 0.514 s and takes
#: 0.087 s, with all 24 composed views byte-identical.
def _composer_establish(ctx, sc, *args, **kwargs):
    """Every observer's opening view, built inside one scene read pass."""
    with scene_read_pass(sc):
        return _composer_establish_views(ctx, sc, *args, **kwargs)


def _opening_line_percept(ctx, sc, p, pid, name, entry, order, *, field,
                          recognized, display_map, bodies_by_name,
                          appearances, aliases):
    """One line the opening's passage quotes, for one observer, or None.

    The outcome pass's speech branch on a beat with one moment: the relation
    from where each stands at the opening, the concealment and hearing gates
    `composer.speech_percept` applies, and a mind's OWN line left out -- it
    is filed as that mind's own conduct (`persist/commit_memory.py`), the
    firewall's usual split. The lines are the establish tail's transcription
    (`agents.director._opening_conduct`)."""
    speaker = str(entry.get("speaker") or "").strip()
    if not speaker or _is_the_observer(sc, speaker, name, aliases.get(name) or ()):
        return None
    if pid == "player" and is_player_speaker(speaker, ctx.chat):
        return None
    speaker_room = room_of(sc, speaker)
    rel = spatial_rel_between(sc, name, speaker, observer_room=p.get("room"),
                              target_room=speaker_room, sound=field)
    if rel is None:
        return None
    senses = p.get("sense_card")
    can_see = _in_plain_view(rel, composer._sense_graded(
        visual_level_between(sc, name, speaker, senses), "sight", senses) != "none")
    display = _attributed_label(
        speaker, name, recognized=recognized, display_map=display_map,
        bodies_by_name=bodies_by_name, can_see=can_see, unseen=_unseen_voice_label(),
        appearances=appearances, cast_aliases=aliases)
    return composer.speech_percept(
        entry, _with_comm_channel(sc, rel, speaker=speaker, observer=name,
                                  observer_room=p.get("room"),
                                  speaker_room=speaker_room),
        name, display=display, can_see=can_see,
        proximity=measured_proximity_rel(sc, name, speaker),
        order_key=order, observer_id=pid, senses=senses,
        voice=_voice_register_for(ctx, speaker),
        voice_sound=_voice_sound_for(ctx, speaker),
        bearing=_speech_bearing(sc, name, speaker, can_see, rel),
        name_forms=_own_name_forms(ctx, name))


def _composer_establish_views(ctx, sc, perceivers, known, p_name,
                              p_appearance, entity_states, sensory_events,
                              presence_bodies=()):
    regions = _far_regions(ctx)
    bodies = []
    p_visible, _, p_known_to, _ci = _subject_disguise_context(
        ctx, p_name, p_appearance, known)
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
            ctx, b_name, b_true, known)
        bodies.append({
            "name": b_name, "room": character_room(sc, sh),
            "appearance": b_visible,
            "aliases": character_scene_keys(sh)[1:],
            "disguise_known_to": b_known_to,
            "disguise_conceals_identity": _ci,
        })
    # LAST, so the registered cast keeps the label-assignment order it had:
    # a room's other people are additional bodies, never a reordering of the
    # ones already there.
    bodies.extend(presence_bodies or ())
    bodies_by_name = {b["name"]: b for b in bodies if b.get("name")}
    joint_labels = _joint_stranger_labels(bodies)
    roster = _identity_roster(p_name, p_appearance, ctx.cast, scene=sc,
                              bodies=bodies,
                              titles_of=_charter_titles_of(ctx, sc))
    identity_space = _composer_identity_space(ctx, p_name, p_appearance)
    cast_parts = _composer_extra_parts(ctx, p_name)
    body_scents = _body_scents(ctx)
    body_descriptions = _body_descriptions(ctx, sc)
    # What the passage shows people saying (the establish tail's transcribed
    # `dialogue_log`), heard below as any beat's lines are.
    opening_lines = [d for d in ((ctx.director_establish or {}).get("dialogue_log") or [])
                     if isinstance(d, dict)]
    appearances = {b["name"]: b.get("appearance") or "" for b in bodies if b.get("name")}
    body_aliases = {b["name"]: b.get("aliases") or [] for b in bodies if b.get("name")}
    clean_views, observations, ledger, company = {}, {}, {}, {}
    for p in perceivers:
        pid = str(p["id"])
        name = p["name"]
        # See the note in the act stage: empty is a record, not a gap.
        seen_bodies = set()
        display_map = {}
        if p.get("awareness") in NON_AWAKE_GATED:
            percepts = composer.residue_percepts(p["awareness"])
            company[pid] = []       # an unconscious observer sees nobody
        else:
            others = [b for b in bodies
                      if not _is_the_observer(sc, b["name"], name)]
            display_map = composer.observer_display_map(
                sc, name, others, known, p.get("sense_card"))
            own_body = bodies_by_name.get(name)
            own_aliases = (own_body or {}).get("aliases") or []
            self_forms = _composer_self_forms(
                name, self_name_forms(name, [name, *own_aliases]),
                own_body, joint_labels, display_map)
            gate = _authored_prose_gate(
                ctx, "perception_establish", name, known, identity_space)
            # `prev_seen=set()` is the LITERAL TRUTH of a scene opening --
            # this observer saw nobody before it -- and it is what finally
            # describes a body the observer KNOWS. A recognized body's
            # authored card was skipped unconditionally, so a companion the
            # player has travelled with for fifty beats opened every scene
            # undescribed, and the narrator had nothing but `past_narration`
            # to go on. Familiarity is a reason not to REPEAT a description,
            # never a reason never to give one.
            percepts = _composer_standing_percepts(
                sc, p, name, others, display_map, known,
                entity_state=p.get("entity_state")
                or (entity_states or {}).get(name),
                prev_seen=set(), seen_out=seen_bodies,
                gate=gate, extra_parts=cast_parts,
                body_scents=body_scents,
                body_descriptions=body_descriptions,
                self_forms=self_forms,
                self_pronouns=p.get("pronouns"),
                sound=_sound_field_for(ctx, sc, name, p.get("room")),
                regions=regions)
            # THIS BEAT'S sounds, so they reach the numbered deliveries
            # rather than the wallpaper. The establish stage's own call is
            # left keyless: its ambience is the air of a place and belongs
            # in standing state.
            percepts.extend(
                _gated_ambient_percepts(gate, sensory_events, p.get("room"),
                                        order_key=_AMBIENT_BEAT_BAND))
            # A SOUND EVENT IN ANOTHER ROOM IS A ONE-BEAT SOURCE on that
            # room's centre (DESIGN_SOUND_FIELD.md section 4b), spread through
            # the doorway it came by and admitted only where the field grades
            # it above `none`. Rewritten to the observer's room so
            # `ambient_percepts`' own-room admission takes it; the gate still
            # scrubs the text. Without a field the list is empty and the
            # opening composes exactly as before.
            afar = heard_events(
                sc, name, sensory_events, room=p.get("room"),
                turn_idx=getattr(ctx.turn, "idx", None),
                crowds=ctx.get("_sound_crowds"))
            if afar:
                here = str(p.get("room") or "")
                percepts.extend(_gated_ambient_percepts(
                    gate, [{**event, "room": here, "room_id": here,
                            "source_room": here} for event, _level in afar],
                    p.get("room"), order_key=_AMBIENT_BEAT_BAND))
            # LOUD SOUND IS FELT (wave B2): what shakes the floor under this
            # body, on the touch channel, whatever it can hear
            # (`felt_vibrations`).
            percepts.extend(_felt_percepts_for(ctx, sc, name, p.get("room"),
                                               sensory_events))
            # THE OPENING'S LINES, heard as any beat's are: nothing said at an
            # opening reached anyone before 2026-09-26 -- a greeting's words
            # included -- because the establish stage kept no log.
            if opening_lines:
                recognized, _unknown = _composer_unknown_sources(
                    name, known, roster, bodies_by_name)
                field = _sound_field_for(ctx, sc, name, p.get("room"))
                for n, entry in enumerate(opening_lines):
                    percept = _opening_line_percept(
                        ctx, sc, p, pid, name, entry, n, field=field,
                        recognized=recognized, display_map=display_map,
                        bodies_by_name=bodies_by_name,
                        appearances=appearances, aliases=body_aliases)
                    if percept:
                        percepts.append(percept)
            # THE CARD'S FLOOR, after every builder (`_card_admitted`).
            percepts = _card_admitted(percepts, p.get("sense_card"),
                                      observer=name)
            company[pid] = _composer_company(others, display_map, percepts)
        # A scene opening is the one beat where everything is legitimately
        # new: full render for every mind, and the ledger starts here.
        rendered = composer.render_view(percepts, mode="character",
                                        full_render=True,
                                        language=ctx.language)
        _composer_finish_observer(
            ctx, "perception_establish", pid, name, rendered, known, roster,
            clean_views, observations, ledger, seen=seen_bodies,
            labels=display_map,
            # The opening beat is where the standing record STARTS: a full
            # render for every mind, so every sentence in it is a delivery
            # this observer can be referred back to (D7).
            track_standing_meta=_is_player_view(pid),
            percepts=percepts)
    ctx["_composer_turn_ledger"] = ledger
    return {
        "views": clean_views,
        "observations": observations,
        "composer_ledger": ledger,
        "company": company,
    }
