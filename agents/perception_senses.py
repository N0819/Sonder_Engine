"""What reaches one observer's eyes and ears: the per-source sight and channel
maps, sight detail and plain view, rooms behind and in view, the per-stage
sound field, sleepers' hearing, ear cover and blast, felt sound, a line's
addressee, comm channels, unseen voices' bearing, register and sound.

Carved verbatim from `agents/perception.py` on 2026-11-01;
`agents/perception.py` is now a facade that re-exports every name defined
here (docs/design/DESIGN_MODULE_LAYOUT.md).
"""

from __future__ import annotations

from story.character_schema import (
    character_voice,
    character_identity,
    character_name,
    character_name_from_text,
    character_senses,
    normalized_character_from_text,
    persona_name,
    persona_senses,
)
from core.db import wget
from story.scene import is_player_speaker, persona_of, sheet_state
from world.spatial import (
    felt_through_ground,
    felt_vibrations,
    seen_source_metres,
    sound_after_sight,
    hiding_holders_of,
    distant_sounds,
    effective_adjacent,
    egocentric_frame,
    entity_arc,
    entity_side,
    _sense_channel,
    has_visual,
    sense_adjusted,
    sight_verdict,
    visual_level_between,
    hear_level,
    spoken_to,
    normalize_bearing,
    proximity_rel,
    relative_bearing,
    room_of,
    body_visibility,
    scent_level,
    sight_level,
    comms_link,
    same_subject,
    sense_acuity_offset,
    spatial_rel_between,
    sound_field,
    visible_adjacent_rooms,
)
from core.pipeline_context import note_step_decision
from . import composer
from .common import CROWDS_KEY

from agents.perception_common import _is_the_observer


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
                visual_level_between(scene, perceiver_name, source_name,
                                     senses),
                "sight", senses) != "none"
        return _sight_reaches(scene, perceiver_name, source_name, senses,
                              rel=rel)
    return _at(sc) or _at(prev_sc)


def _body_relocated(prev_sc, sc, name, fallback_room=None):
    """Did THIS body's own position change across the beat.

    The beat's movement record, read off the two scenes that record it: the
    room a body stands in, and the enclosures shut around it. Both are ways a
    body relocates, both are written by the same merge, and reading the scenes
    catches a body carried by a passage or a vehicle exactly as it catches one
    that walked -- a `state_diff.positions` read would see only the second.

    False whenever either end is unknown. An unplaced body has not been shown
    to have moved, and the only thing this answer ever does is WITHDRAW a
    channel, so silence must not withdraw one.
    """
    if not prev_sc or not sc or not name:
        return False
    then_room = room_of(prev_sc, name)
    now_room = room_of(sc, name) or fallback_room
    if then_room and now_room and then_room != now_room:
        return True
    return ({str(h).strip().casefold() for h in hiding_holders_of(prev_sc, name)}
            != {str(h).strip().casefold() for h in hiding_holders_of(sc, name)})


def _sight_reaches(scene, observer, target, card, rel=None):
    """Can THIS perceiver see that body at all, card and all (A87)?

    ONE composition, so the six gates that decide whether a demeanor, a tell,
    a visual channel or a sweep reaches an observer answer what the composed
    view answers. Each of them used to ask `has_visual(rel)` and grade a bare
    `"full"` with no perceiver, which is card-blind: an authored sight that
    does not need light was graded `none` by the gate and `full` by the view
    on the same beat. Answer-identical for every stored card (proved over
    1,024 relations x 118 stored sense lists, 0 differences).
    """
    if rel is None:
        return visual_level_between(scene, observer, target, card) != "none"
    level, block = sight_verdict(rel)
    return sense_adjusted(level, "sight", card, blocked_by=block) != "none"


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


#: The percept channels an authored card can take away, under the card's own
#: channel names (`spatial.sense_acuity_offset`). Touch and interoception are
#: no sense a card authors, and `mixed` is no sense in particular.
_CARD_CUTS = (("sight", "sight"), ("hearing", "hearing"), ("smell", "scent"))


def _channels_the_card_cuts(senses):
    """The percept channels this card says are ABSENT (blind, deaf,
    anosmic): `sense_acuity_offset` answers None, a full cut and not a
    shift. Empty for no card and for every ordinary or dulled one."""
    if not senses:
        return frozenset()
    return frozenset(channel for channel, card in _CARD_CUTS
                     if sense_acuity_offset(senses, card) is None)


def _where_without_eyes(percept):
    """The environment percept a sightless body keeps: WHERE it is -- the
    room's name and its own description, which the dark leaves a sighted
    body too -- and nothing an eye reports (what is in reach, the ways out
    and what lies past them, the light). On no sense in particular, since
    no sense delivered it."""
    import dataclasses
    d = percept.data or {}
    where = composer.environment_percept(
        d.get("room_id"), d.get("room_name"), d.get("room_notes") or "")
    return dataclasses.replace(where, channel="mixed") if where else None


def _card_admitted(percepts, senses, *, observer=""):
    """THE SENSE CARD'S FLOOR, asked once a stage, after every builder.

    `composer._sense_graded` was asked by the builders that grade a BODY or
    a LINE and by nothing else, so an authored-blind card standing in a lit
    kitchen was told "You can see the hearth ... Through the back door is
    The Yard. A muddy yard. There is a silver coin at the long oak counter."
    byte-identical to a sighted one, and an authored-deaf card heard the
    generator's din and the kettle's shriek (audit agents_perception F1,
    2026-11-01: the environment, things, openings, notices, chatter,
    soundscape, weather, the beat's own sounds, the near and far field --
    every `_gated_ambient_percepts` and `heard_events` site -- asked no
    card). Nine builders each asking is nine places to forget; a percept
    already says which channel it arrived on, so the rule is stated once,
    here, where the observer's percepts are whole: what arrived on a channel
    the card says is ABSENT does not reach the mind.

    Only the absent case. A dulled or keen card is graded by the builders
    that grade (`_sense_graded`), and an ordinary or empty card returns the
    list unchanged. Never more than the card says:

      * the observer's OWN body and keeping (`source_label` "you", a thing
        in its own hands -- `kept`) are proprioception and touch whatever
        channel their sentence is filed on;
      * a sightless body still knows WHERE it stands (`_where_without_eyes`);
      * touch, interoception and an unclassified `mixed` channel are no
        card's to take.
    """
    cut = _channels_the_card_cuts(senses)
    if not cut:
        return percepts
    kept, withheld = [], []
    for p in percepts or ():
        if p.channel not in cut or p.source_label == "you" \
                or (p.data or {}).get("kept"):
            kept.append(p)
            continue
        if p.kind == "environment":
            where = _where_without_eyes(p)
            if where is not None:
                kept.append(where)
        withheld.append(p.kind)
    if withheld:
        note_step_decision(
            "sense_card", observer or "?", "refused",
            "the card says %s is absent: %d percept(s) withheld (%s)" % (
                "/".join(sorted(cut)), len(withheld),
                ", ".join(sorted(set(withheld)))))
    return kept


def _own_name_forms(ctx, name):
    """THE NAMES OTHERS CALL `name` BY (`composer.own_name_forms`), for the
    own-name rescue of a line heard in pieces or as a voice alone
    (DESIGN_SOUND_FIELD § 13): a cast member's card name and aliases, the
    player's persona name and aliases, an extra player's. Read off the
    cards, never off the scene's handles (a uid is not said aloud), and
    built once a turn."""
    cache = ctx.get("_own_name_forms")
    if cache is None:
        cache = {}
        try:
            pers = persona_of(ctx.chat)
            p_name = pers.get("name") or persona_name(pers)
            if p_name:
                cache[str(p_name).casefold()] = composer.own_name_forms(
                    p_name, (pers.get("identity") or {}).get("aliases") or ())
        except Exception:
            pass
        for c in getattr(ctx, "cast", None) or ():
            try:
                ident = character_identity(
                    normalized_character_from_text(c["sheet"]))
            except Exception:
                continue
            nm = str(ident.get("name") or "").strip()
            if nm:
                cache[nm.casefold()] = composer.own_name_forms(
                    nm, ident.get("aliases") or ())
        for extra in getattr(ctx, "extra_players", None) or ():
            nm = str((extra or {}).get("name") or "").strip()
            if nm:
                cache.setdefault(nm.casefold(), composer.own_name_forms(nm))
        ctx["_own_name_forms"] = cache
    return cache.get(str(name or "").strip().casefold(), ())


#: The event rungs a sleeper's residue calls LOUD -- "a sound, huge and
#: wordless, reaches down and is gone" -- where it reached them and they
#: slept on: the impact ladder's `loud` and up (`spatial_sound_field.
#: EVENT_POWER`), and the voice words `loud` and `shout`.
_RESIDUE_LOUD_EVENT_LEVELS = ("loud", "deafening", "thunderous", "catastrophic")


def _sleep_hears(ctx, sc, name, room, lines, *, events=(), prev_scene=None,
                 senses=None, name_forms=()):
    """WHAT A SLEEPER'S EAR TOOK FROM THE BEAT (DESIGN_SOUND_FIELD § 13):
    `(woke, loud)`.

    `woke` is what woke them, one of `spatial_listener.WAKING_SOUNDS`, or "".
    A SLEEPER WAKES TO SOUND: to one that reaches their ear at `WAKING_DB` or
    more and stands `WAKING_EMERGENCE_DB` out of the room's steady noise --
    a line (its voice at their ear by the hearing rule's own path,
    `voice_at_ear_db`), a one-beat sound of the beat, a far sound the room
    graph brought in, a running thing that STARTED this beat (one already
    running when they went under is the room's own, and is slept through);
    or to their own NAME (`name_forms`), said in a line whose words would
    reach them awake. Through whatever covers their ears. Nothing quieter
    wakes them, and a body with no hearing (`sense_acuity_offset` None) is
    woken by none of it.

    `loud` is the residue's wordless intrusion for a sleeper who slept on:
    a loud sound that REACHED them and stood out of the room. It was any
    loud or shouted line anywhere in the beat, so a shout in another
    building reached a sleeper's residue."""
    woke, loud, _at = _sleep_hears_where(
        ctx, sc, name, room, lines, events=events, prev_scene=prev_scene,
        senses=senses, name_forms=name_forms)
    return woke, loud


def _sleep_hears_where(ctx, sc, name, room, lines, *, events=(),
                       prev_scene=None, senses=None, name_forms=(),
                       order=None):
    """`_sleep_hears`, and WHERE in the beat the waking fell:
    `(woke, loud, at)` (DESIGN_SOUND_FIELD § 17, round 2 lane C).

    `order(kind, record)` places a line (`"line"`, its dialogue row) or a
    one-beat sound (`"event"`, its record) in the beat -- the outcome pass's
    `beat_events` index -- or answers None; a running thing that started
    this beat has no place in it. With it, the sleeper wakes to the EARLIEST
    placed sound that wakes them (their own name before a louder sound at
    the same place), and `at` is that place: what they perceive from then
    on is theirs, what came before it is not (`_composer_outcome_views`).
    A beat that places none of what wakes them keeps § 13's choice -- the
    name, else the loudest -- with `at` None, which the outcome reads as
    "the remainder is the standing state alone": an unplaced waking cannot
    say which of the beat's events came after it, and the firewall
    subtracts. Without `order`, § 13's answer exactly."""
    from world.spatial import (AMBIENT_DB, WAKING_EMERGENCE_DB, db_of_power,
                               ear_cover_db, into_another_ear,
                               sense_acuity_offset, started_sources,
                               voice_at_ear_db, wakes_sleeper)
    if sense_acuity_offset(senses, "hearing") is None:
        return "", False, None
    field = _sound_field_for(ctx, sc, name, room, events=list(events) or None)
    placed = field is not None and field.locate(name, room) is not None
    steady = (db_of_power(field.noise_at(name, room=room)) if placed
              else AMBIENT_DB["enclosed"])
    cover = ear_cover_db(sc, name)
    # (level at the ear before the cover, kind, loud, the steady noise it
    # stands out of -- a thing that started this beat is not its own room,
    # what kind of record made it and the record, for `order`)
    heard = []
    for idx, event in enumerate(events or ()):
        if not isinstance(event, dict) or not placed:
            continue
        source = str(event.get("source") or "").strip()
        if source and same_subject(sc, source, name):
            continue                    # their own breath, their own turn
        power = field.signal_at(name, "event:%d" % idx, room=room)
        if power:
            heard.append((db_of_power(power), "noise",
                          str(event.get("level") or "").casefold()
                          in _RESIDUE_LOUD_EVENT_LEVELS, steady,
                          "event", event))
    if events:
        try:
            far = distant_sounds(
                sc, name, room=room, turn_idx=getattr(ctx.turn, "idx", None),
                near_rooms=(field.grid.offsets if field else ()),
                crowds=ctx.get("_sound_crowds"), events=list(events))
        except Exception:
            far = []
        for record in far:
            try:
                heard.append((float(record.get("db")), "noise", True, steady,
                              "", None))
            except (TypeError, ValueError):
                continue
    if prev_scene is not None and placed:
        for sid in sorted(started_sources(prev_scene, sc)):
            power = field.signal_at(name, sid, room=room)
            if power:
                heard.append((db_of_power(power), "noise", False,
                              db_of_power(field.noise_at(
                                  name, exclude=(sid,), room=room)),
                              "", None))
    named = []
    for entry in lines or ():
        if not isinstance(entry, dict):
            continue
        speaker = str(entry.get("speaker") or "").strip()
        body = str(entry.get("exact_quote") or entry.get("text") or "")
        if not speaker or not body.strip() \
                or _is_the_observer(sc, speaker, name):
            continue
        volume = str(entry.get("volume") or "normal")
        addressed = composer.line_addressed(entry, name)
        if into_another_ear(volume, addressed, entry.get("level_db")):
            continue
        sp_room = entry.get("speaker_room") or room_of(sc, speaker)
        if not sp_room:
            continue
        rel = spatial_rel_between(sc, name, speaker, observer_room=room,
                                  target_room=sp_room, sound=field)
        level = voice_at_ear_db(rel, volume, reach=rel.get("reach"),
                                level_db=entry.get("level_db"))
        word = volume.strip().casefold()
        if level is not None:
            heard.append((level, "shout" if word == "shout" else "voice",
                          word in ("loud", "shout"), steady, "line", entry))
        if name_forms and composer.own_name_said(body, name_forms) \
                and hear_level(rel, volume, level_db=entry.get("level_db"),
                               addressed=addressed) in ("fragment", "full"):
            named.append(entry)
    waking = [(level, kind, rk, rec) for level, kind, _loud, under, rk, rec
              in heard if wakes_sleeper(level - cover, under - cover)]
    if order is not None and (named or waking):
        # THE EARLIEST PLACED WAKING: by its place in the beat, a name
        # first at the same place, then the loudest.
        candidates = []
        for entry in named:
            at = order("line", entry)
            if at is not None:
                candidates.append((at, 0, 0.0, "name"))
        for level, kind, rk, rec in waking:
            at = order(rk, rec) if rk else None
            if at is not None:
                candidates.append((at, 1, -float(level), kind))
        if candidates:
            first = min(candidates)
            return first[3], False, first[0]
    if named:
        return "name", False, None
    if waking:
        return max((level, kind) for level, kind, _rk, _rec in waking)[1], \
            False, None
    loud = any(is_loud and level >= under + WAKING_EMERGENCE_DB
               for level, _kind, is_loud, under, _rk, _rec in heard)
    return "", loud, None


def _reaches_this_ear(sc, name, room, field, events, event) -> bool:
    """Does a one-beat sound in this listener's own room reach THEIR ear?
    Always, for an open ear -- a sound is received whole in its own room,
    as it always was. A covered or blast-dulled ear (`spatial_listener`)
    grades it on the field first: a faint creak does not get through hands
    pressed over the ears, a crash does."""
    from world.spatial import dulled_shift_db, ear_cover_db, heard_at_ear
    if ear_cover_db(sc, name) <= 0.0 and dulled_shift_db(sc, name) <= 0.0:
        return True
    if field is None or field.locate(name, room) is None:
        return True
    try:
        idx = next(i for i, e in enumerate(events or ()) if e is event)
    except StopIteration:
        return True
    return heard_at_ear(sc, name, field, "event:%d" % idx, room=room) != "none"


def _blast_exposure(ctx, sc, name, room, field, events):
    """The loudest thing at this listener's ear this beat, in dB, where it is
    past `BLAST_DB`, else None (`spatial_listener.loudest_at_ear`: the
    placed sources of their field and the far sounds the room graph brought
    in, through whatever covers their ears)."""
    from world.spatial import BLAST_DB, loudest_at_ear
    try:
        far = distant_sounds(
            sc, name, room=room, turn_idx=getattr(ctx.turn, "idx", None),
            near_rooms=(field.grid.offsets if field else ()),
            crowds=ctx.get("_sound_crowds"), events=list(events or ()))
    except Exception:
        far = []
    level = loudest_at_ear(field, name, room=room, distant=far, scene=sc)
    if level is None or level < BLAST_DB:
        return None
    return round(level, 1)


def _asleep_when_the_beat_began(chat_id, name) -> bool:
    """Was this body ASLEEP when the beat began -- every active awareness
    row on it `asleep` (`story.scene.awareness_conditions`)? A sleep the
    beat itself put them into is not woken by the beat's own sounds, and a
    body also sedated or unconscious is not woken by a sound at all."""
    from story.scene import awareness_conditions
    from world.spatial import SOUND_WAKES
    folded = str(name or "").strip().casefold()
    levels = [r["level"] for r in awareness_conditions(chat_id)
              if str(r.get("subject") or "").strip().casefold() == folded]
    return bool(levels) and all(level in SOUND_WAKES for level in levels)


def _sound_field_for(ctx, sc, name, room, events=None):
    """One perceiver's sound field for this stage
    (`world/spatial_sound_field.py`), or None where their room carries no
    geometry -- in which case every hearing reader runs today's edge rules
    unchanged. The turn index seeds the steadiness hash so a reroll hears
    what the beat it replaces heard; the crowd ledger is read once per stage
    and every perceiver's field shares it.

    `events` are the beat's one-off sounds. A field built WITHOUT them knows
    nothing of a hiss or a crash this beat made, so the noise floor it
    grades a voice against is the room's standing one and a sound in the
    next room is on no grid at all. The outcome pass passed none: own-room
    events went through `ambient_percepts` (which drops other rooms) and
    far events through `distant_sounds` (which skips the near field's
    rooms), so a one-beat sound in the NEXT room reached nobody once the
    listener's room had geometry -- exactly the rooms the field was widened
    to cover."""
    crowds = ctx.get("_sound_crowds")
    if crowds is None:
        crowds = wget(ctx.chat.id, CROWDS_KEY, []) or []
        ctx["_sound_crowds"] = crowds
    return sound_field(sc, name, room=room,
                       turn_idx=getattr(ctx.turn, "idx", None), crowds=crowds,
                       events=events or None)


def _felt_percepts_for(ctx, sc, name, room, events):
    """LOUD SOUND IS FELT (DESIGN_SOUND_FIELD.md § 14.4, wave B2): what
    shakes the floor under `name` this beat -- the beat's own blows
    (`events`) and the steady trembling of whatever runs at `deafening` and
    above -- as touch percepts (`composer.felt_percepts`). Not gated by any
    sense card: a body that cannot hear feels it all the same."""
    turn_idx = getattr(getattr(ctx, "turn", None), "idx", None)
    return composer.felt_percepts(
        felt_vibrations(sc, name, room=room, events=events or None,
                        turn_idx=turn_idx),
        ground=felt_through_ground(sc, room), beat=turn_idx)


def _sounds_after_sight(sc, observer, events):
    """SOUND ARRIVES AFTER WHAT MADE IT (DESIGN_SOUND_FIELD.md § 14.3, wave
    B2): `[(event, after, source)]` for each of the beat's sounds whose maker
    -- a body the scene places, named as the event's `source` -- this
    observer sees, standing far enough off that the sound comes a beat
    after the sight of it (`sound_after_sight` over `seen_source_metres`).
    A footfall is not one: a walker in view is seen walking, not heard."""
    out = []
    for event in events or ():
        if not isinstance(event, dict) or event.get("tread"):
            continue
        source = str(event.get("source") or "").strip()
        if not source or not room_of(sc, source) \
                or same_subject(sc, source, observer):
            continue
        if visual_level_between(sc, observer, source) == "none":
            continue
        after = sound_after_sight(seen_source_metres(sc, observer, source))
        if after:
            out.append((event, after, source))
    return out


def _sound_filing_spans(diff, sounds) -> set:
    """`{(stage, chrono)}` for every causal step of the beat that filed a
    sound event of its own which is among the beat's `sounds` (the records
    the stage delivers, each carrying its step as `_at`).

    The step is read off the typed program (`state_diff.causal_steps`: each
    step's own `patch`), never matched by words, and the chrono alone does
    not say it: the resolve's diff carries the interpret's sounds as well,
    and the two stages number their steps from 1 each -- on the tavern
    probe (2026-10-20, chat 2 idx 5) the player's call (interpret 2) and a
    turn of the heads at the bar (resolve 2) shared one number. A sound the
    beat no longer holds (a floor took it) files nothing. Empty for a diff
    with no program."""
    present = {str(record.get("_at")) for record in sounds or ()
               if isinstance(record, dict)
               and record.get("_at") not in (None, "")}
    out = set()
    for step in (diff or {}).get("causal_steps") or ():
        if not isinstance(step, dict):
            continue
        patch = step.get("patch") if isinstance(step.get("patch"), dict) else {}
        rows = patch.get("sensory_events")
        if not any(isinstance(row, dict) and _sense_channel(
                str(row.get("kind") or "sound")) == "hearing"
                for row in (rows if isinstance(rows, list) else ())):
            continue
        chrono = str(step.get("chrono_id"))
        if chrono in present:
            out.add((str(step.get("stage") or ""), chrono))
    return out


def _source_channels(sc, perceiver_name, perceiver_room, sources,
                     prev_sc=None, senses=None, sound=None):
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
    # WHOSE ACT CLOSED THE CHANNEL, decided once: it is a fact about the
    # perceiver, not about any one source. See the rescue below.
    perceiver_relocated = _body_relocated(prev_sc, sc, perceiver_name,
                                          perceiver_room)
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
        # `sound` is this perceiver's sound field for the beat (crowds and
        # the turn index included), built once by `_sound_field_for` and
        # stamped onto every source relation here; None where the room
        # carries no geometry, and the relation is then exactly as before.
        rel = spatial_rel_between(sc, perceiver_name, s["name"],
                                  observer_room=perceiver_room,
                                  target_room=s["room"], sound=sound)
        if prev_sc:
            prev_rel = spatial_rel_between(
                prev_sc, perceiver_name, s["name"],
                observer_room=room_of(prev_sc, perceiver_name) or perceiver_room,
                target_room=room_of(prev_sc, s["name"]) or s["room"],
                # One beat, one field (PC3): the rescue used to build its
                # relation without this beat's field, so a channel it kept
                # was graded by the edge model alone.
                sound=sound)
            # Only ever upgrades. `has_visual` is the room-level question and
            # is the one that goes false when an edge is severed mid-beat --
            # which is exactly the transition this exists to preserve.
            #
            # AND ONLY WHEN THE PERCEIVER STAYED PUT. The rescue keeps a
            # channel the beat's own transition closed; it may not keep one
            # the perceiver walked out of, because a body is graded from
            # where it IS, and a room it left is not a room it still
            # perceives from. Keying on the relation alone cannot tell the
            # two apart -- both read as "visual then, none now" -- so a
            # perceiver who changed room was handed her old room back for the
            # whole beat, `same_room` and all: `line_hear_level` then
            # returned "full" and `speech_percept` emitted no `via`, so lines
            # spoken after she was gone arrived as unchannelled co-present
            # voice and nothing downstream could tell they had crossed a
            # boundary. Measured live: four speeches so delivered, and the
            # narrator invented a display feed to explain them, two beats
            # before any comm link existed.
            #
            # This withdraws the perceiver-moved half and keeps the whole of
            # the half the rescue was written for (chat 58 t27), where the
            # SOURCE is the one whose act severed the channel it was seen
            # through -- a door slammed, a curtain drawn, a vehicle pulling
            # away. The asymmetry is the firewall's own direction: where the
            # perceiver moved, the unrescued relation is the truthful one.
            if (has_visual(prev_rel) and not has_visual(rel)
                    and not perceiver_relocated):
                rel = {**prev_rel, "was_reachable_at_beat_start": True}
        rels[s["name"]] = rel
    return {
        "spatial_to_sources": rels,
        "visual_channel_to_sources": {
            n: (_saw_across_beat(sc, prev_sc, perceiver_name, n, rels[n],
                                 senses))
            for n in rels
        },
        # DELIVERED NOWHERE, and kept deliberately. `composer.CHANNELS`
        # declares "smell" and `ambient_percepts` can mint one from an
        # authored sensory event, so the channel is reachable. THE SCENT IT
        # WOULD GRADE NOW EXISTS AND ARRIVES BY ANOTHER ROUTE (E15): a body's
        # standing smell is a card field (`story.scene.scent_of` ->
        # `_body_scents`), and `_scent_sources_for` grades every smell reaching
        # an observer -- body, entity and deposited substance -- each by the
        # relation its own ledger already uses, out through
        # `composer.scent_percepts`. So this per-source map is not a gate with
        # nothing behind it; it is a second grading of what that path grades,
        # and no percept builder reads it. `tests/test_masked_floor_leaks.py`
        # reads it as the visible proof that `spatial_rel_between` stamps both
        # enclosure directions.
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


def _sourceless_event_rel(scene, observer, targets, observer_room):
    """Where an event with no body behind it happened, for one observer: the
    relation to the nearest of its targets the scene places, or None when
    it names none. A target the observer stands INSIDE -- the car it rides,
    the ship it sails -- is the observer's own place: what happens to it
    happens around them. The authored event, the world process and the
    engine's own sources are placed nowhere; their targets are where they
    happen."""
    from world.spatial import _unique_entity_keyed
    rooms = (scene or {}).get("rooms") or {}
    holder = str((rooms.get(observer_room) or {}).get("parent_entity") or "")
    best = None
    for target in targets or ():
        target = str(target or "").strip()
        if not target:
            continue
        if holder:
            eid, _entity = _unique_entity_keyed(scene, target)
            if eid == holder or target == holder:
                return {"same_room": True, "barrier": "open", "distance": "near",
                        "note": "it happened to the place this observer is inside"}
        target_room = room_of(scene, target)
        if not target_room:
            continue
        rel = spatial_rel_between(scene, observer, target,
                                  observer_room=observer_room, target_room=target_room)
        if rel.get("same_room"):
            return rel
        best = best or rel
    return best


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


def _sight_detail(sc, observer_name, actor_name, rel, senses=None):
    """How much CONDUCT sight admits: "full", "shapes" or "none".

    SIGHT IS GRADED AND THE ACT CHANNEL WAS NOT. Every grader here answers
    in the SIGHT ladder's own words -- `sight_level` and
    `visual_level_between` both return none/shapes/conduct/full since the
    2026-09-05 light work added the middle rung -- and `_in_plain_view`
    spends the answer as a boolean, so a shape-in-a-doorway budget bought a
    readable description of conduct at the far side of a room.

    This function collapses that ladder to what the ACT channel can carry,
    which is three answers rather than four: `conduct` is the rung that says
    a body's doing is plain while its face and its detail are not, and an
    act's observable surface IS its doing -- so `conduct` delivers the
    surface exactly as `full` does, and only `shapes` reduces it to motion.
    That collapse is what makes "dim withholds detail, not conduct" reach
    this channel at all; the detail half is withheld by the appearance and
    identity readers, which gate on `== "full"` by construction.

    Live, "The Long Gallery" turns 11-12 (PC1). Ada and Mrs Penrose were
    behind a `closed_door`, locked, on both edges; `closed_door` is not a
    sight barrier, so `sight_level` was `none` -- and the crossing record
    written when they went through it floors sight at `shapes` for a beat,
    because a body that has just crossed an opaque boundary is not instantly
    gone. Lord Edmund, at the hearth, read "Ada Quill perches on the corner
    of the desk, setting the lamp between herself and Mrs Penrose. Ada Quill
    opens a black notebook on her knee." No speech crossed: the dialogue gate
    honoured the same wall in the same beat.

    Only an explicit `shapes` downgrades. This is deliberately not a second
    admission gate -- `_in_plain_view` still decides whether anything is seen
    at all -- so nothing this returns can refuse what today delivers in the
    observer's own room; it can only say that what is seen is a body moving
    rather than a body acting.

    ACROSS A DOORWAY A `none` STAYS `none`. There the admission is the
    room-to-room edge (`_sight_reaches` with a relation) and this is the only
    body-level reader, so the carve-out below -- written for a body in the
    observer's own room -- turned the doorway cone's refusal into the act's
    whole surface (probed 2026-10-04: a lit yard, a body at a post on the
    doorway's own wall, `visual_level_between` none, the act delivered in
    full while no presence line placed him). The observer's card is spent
    exactly as `visual_level_between` spends it, on whether this sight needs
    light, so a card that sees in the dark keeps the act it sees the body in
    and acuity never lifts this channel -- PC1 again, through a keener eye.
    The one thing acuity does here is the presence line's own subtraction:
    a body a dulled eye cannot make out at all shows that eye no act.
    """
    if "sight" in _channels_the_card_cuts(senses):
        # AN ABSENT SIGHT SEES NO CONDUCT, IN THE ROOM OR OUT OF IT. The
        # same-room arm below grades the world alone (`visual_level_between`
        # spends a card only on `needs_light`), so an authored-blind card
        # was handed "Hinami crosses the hall toward the window" by sight
        # (audit agents_perception F1/F2, 2026-11-01).
        return "none"
    level = ""
    measured = room_of(sc, observer_name) is not None
    if measured:
        level = visual_level_between(sc, observer_name, actor_name,
                                     senses) or ""
    if not level:
        level = sight_level(rel) or ""
    if measured and isinstance(rel, dict) and not rel.get("same_room") and (
            level == "none"
            or composer._sense_graded(level, "sight", senses) == "none"):
        return "none"
    if level == "none":
        # THE SAME QUESTION, ASKED INSIDE THE ROOM TOO (PE9, "Two Rooms and a
        # Kettle"): `_in_plain_view` short-circuits on `same_room`, so an
        # occluder never subtracted from an act -- a body behind the sofa was
        # graded as if nothing stood between. Only the LINE subtracts here.
        # `_in_plain_view` has already admitted this source and the two
        # answers disagree for other reasons as well (an unlit room admits a
        # co-present act today and goes on doing so); what is new is the one
        # thing a room-level boolean cannot see, which is something standing
        # in the way. `body_visibility` answers only on two measured stations
        # and an opaque anchor of a stated height between them, so a scene
        # without geometry is unchanged.
        return "none" if _line_of_sight_blocked(
            sc, observer_name, actor_name) else "full"
    return "shapes" if level == "shapes" else "full"


def _line_of_sight_blocked(sc, observer_name, actor_name):
    """Does something stand in the way, on the evidence of measured stations."""
    try:
        line = body_visibility(sc, observer_name, actor_name) or {}
    except Exception:                       # pragma: no cover - geometry floor
        return False
    return line.get("basis") == "line" and not line.get("visible")


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

    # Undirected, like `visible_adjacent_rooms` on the other side of the
    # subtraction. While this loop read `room["adjacent"]` alone and that one
    # read both sides, an observer with their back to a doorway their own room
    # never declared stayed OUTSIDE this list and went on receiving fresh
    # sight of the room behind them -- the two paths computing one fact and
    # only one of them taught the rule. Gaining edges here subtracts more.
    for edge in effective_adjacent(scene, room_of(scene, observer)):
        if not edge.get("to"):
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

def _addressee_name(ctx, ref):
    """A speech span's target as the name a body is placed under: a cast
    id (`character:N`) becomes that member's name; anything else is
    returned as written (a name, an entity id, a room)."""
    ref = str(ref or "").strip()
    if ref.startswith("character:") and ref[10:].isdigit():
        for row in (getattr(ctx, "cast", None) or []):
            try:
                if int(row["id"]) == int(ref[10:]):
                    return character_name_from_text(row["sheet"])
            except (KeyError, TypeError, ValueError):
                continue
    return ref


def _line_is_to(ctx, sc, observer, line, *, names=None, aliases=()):
    """Is `observer` the body a spoken line is aimed at -- its
    `intended_target`, or one of its `targets` -- each read as the speaker
    named it: a handle `names` knows (a cast or persona id) to the name its
    body stands under, a cast id through the roster, then every spelling of
    the observer (`_is_the_observer`).

    What the ear rung is decided by (`spatial_senses.EAR_VOLUME`): a line
    breathed into an ear reaches this body only if this answers yes, so it
    fails toward no -- a target nothing resolves gives the line to nobody,
    and the composer's own reading of the line (`composer.line_addressed`)
    is what a caller without a scene falls back to.

    None where the line names NOBODY (`spatial_senses.spoken_to`): unknown,
    which no bystander rule caps, never "spoken to somebody else"."""
    if not isinstance(line, dict):
        return None
    refs = composer._line_refs(line)
    for text in refs:
        named = ((names or {}).get(text) or (names or {}).get(text.casefold())
                 or _addressee_name(ctx, text))
        if _is_the_observer(sc, named, observer, aliases):
            return True
    return spoken_to(False, bool(refs))


def _speech_bearing(scene, observer, speaker, can_see, rel):
    """Where an unseen voice from ANOTHER room came from, as the listener's
    own egocentric phrase ("through the doorway to your right"), or "".

    The phrase is `spatial.sound_bearing`'s, the one an unseen act is placed
    by (`composer._sound_bearing_phrase`): it names no room and no body, so
    it discloses nothing an ear did not take in. A speaker in sight, or in
    the listener's own room, needs none. See `composer.speech_percept`."""
    if can_see or not isinstance(rel, dict) or rel.get("same_room"):
        return ""
    try:
        from world.spatial import sound_bearing
        rec = sound_bearing(scene, observer, speaker)
    except Exception:
        return ""
    if not isinstance(rec, dict):
        return ""
    return str(rec.get("phrase") or "").strip()


def _voice_register_for(ctx, speaker):
    """The speaker's own vocal register from their sheet, or "" -- the voice
    the composer establishes ONCE per observer (D2, `composer.speech_percept`).
    Read through the cast row, so a per-story card override wins exactly as
    it does for everything else the character is. A player persona carries
    no `social.voice`, and a background presence has no sheet: both answer
    "", and their lines carry only the tone they were declared with."""
    target = str(speaker or "").strip()
    if not target:
        return ""
    for row in (getattr(ctx, "cast", None) or []):
        try:
            sheet, _active, _stance = sheet_state(row)
        except Exception:
            continue
        if not same_subject(ctx.get("scene") or {}, character_name(sheet), target) \
                and str(character_name(sheet) or "").strip().casefold() != target.casefold():
            continue
        return str((character_voice(sheet) or {}).get("register") or "").strip()
    return ""


def _voice_sound_for(ctx, speaker):
    """What the speaker's voice carries to a stranger's ear -- the card's
    `embodiment.voice` (DESIGN_SOUND_FIELD § 18) -- or "". Read through the
    cast row as the register is, so a per-story card override wins; and,
    where the speaker is the PLAYER (`is_player_speaker`), through their
    persona, which since 2026-10-20 carries the field too -- the player is a
    body other minds hear. A background presence has no sheet and answers
    "". The persona is read once a turn (`_persona_voice_sound` on ctx)."""
    from story.character_schema import character_voice_sound, persona_voice_sound
    target = str(speaker or "").strip()
    if not target:
        return ""
    for row in (getattr(ctx, "cast", None) or []):
        try:
            sheet, _active, _stance = sheet_state(row)
        except Exception:
            continue
        if not same_subject(ctx.get("scene") or {}, character_name(sheet), target) \
                and str(character_name(sheet) or "").strip().casefold() != target.casefold():
            continue
        return character_voice_sound(sheet)
    try:
        if is_player_speaker(target, ctx.chat):
            cached = ctx.get("_persona_voice_sound")
            if cached is None:
                cached = persona_voice_sound(persona_of(ctx.chat))
                ctx["_persona_voice_sound"] = cached
            return cached
    except Exception:
        return ""
    return ""
