"""One observer's standing state and its assembler: things read by hand,
station or look, visible features, things and openings (with beam-lit
rooms), scents, gated ambient events, the bare-region rows, and
`_composer_standing_percepts`, the single consumer of all of them.

Carved verbatim from `agents/perception.py` on 2026-11-01;
`agents/perception.py` is now a facade that re-exports every name defined
here (docs/design/DESIGN_MODULE_LAYOUT.md).
"""

from __future__ import annotations

from story.scene import disguise_breaks_recognition
from world.spatial import (
    hiding_holders_of,
    scene_names_body,
    contact_sensation,
    contact_action_clause,
    contact_actions_for_observer,
    effective_adjacent,
    entity_arc,
    feature_visibility,
    anchor_cells,
    beam_light_on,
    beam_lit_cells,
    beam_sent_into,
    effective_light,
    room_has_geometry,
    visual_level_between,
    light_shape,
    neighbour_cells_in_view,
    neighbour_feature_visibility,
    normalize_barrier,
    room_of,
    scent_level,
    same_subject,
    spatial_rel,
    spatial_rel_between,
    sound_shape,
    sound_fill,
    room_holds_a_standing_source,
    room_noise_word,
    room_still_sounding,
    NOISE_WORDS,
)
from . import composer
from .common import (
    room_prose,
    _recognizes,
    _strip_identity_tokens,
    observer_body_regions,
)

from agents.perception_bodies import _bare_body_details, _self_body_detail
from agents.perception_senses import _channels_the_card_cuts


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


def _station_anchor_of(scene, name):
    """The anchor `name` stands at, with `same_subject`'s key tolerance."""
    stations = (scene or {}).get("stations") or {}
    if not isinstance(stations, dict):
        return ""
    for key, row in stations.items():
        if isinstance(row, dict) and same_subject(scene, str(key), name):
            return str(row.get("at") or "")
    return ""


def _things_read_by(sc, name, room, *, bodies=(), looks=(), handled=(),
                    senses=None):
    """The things whose own record this observer is READING right now, as
    ``[(entity_id, entity, channel)]`` -- for `composer.thing_reading_percepts`.

    A BODY READS A THING BY HAVING ITS HANDS ON IT OR BY STANDING AT IT. Two
    admissions, both subtracting from ledgers the engine already keeps, so
    neither is a new judgment about what a body reaches:

      * TOUCH: a standing contact this observer is the ACTOR of, whose target
        is a thing in this room. The contact ledger is the record that a hand
        is on it; what the hand finds is the thing's `state`.
      * SIGHT: a thing stationed at the SAME anchor the observer stands at,
        when the room has light to see by. Arm's reach is what a shared
        station means (`stations.at`), and a display at arm's reach is read
        without touching it. Across the room it is not: no distance
        vocabulary is spent here, so nothing is read from afar.

      * LOOKED: a thing this observer's OWN act looked at this beat
        (`_own_looks`), seen in full -- in this room or wherever the eye
        reaches it. A close look is a read by sight: the encoder authors the
        detail for exactly that act (its `entities__examined` card: "the act
        of looking promised the reader the detail"), and the owner's
        2026-09-19 ruling is that a thing examined closely tells you what it
        is like. Measured on scratch story 166 (idx 16): the player leaned
        out of the boat to examine a coat caught on a stake, the encoder
        wrote its treenail, its slit pocket and the cut reed into the coat's
        record, and her view said only that she was studying it -- so the
        page invented the opposite. The look is the observer's own, so the
        station rule's "nothing is read from afar" still holds for a glance.

      * HANDLED: a thing this beat's transfers put into this observer's
        hands (`_own_handled`), read as a look is -- seen in full, by the
        same test, so light, sight and where it now is still decide. A thing
        held is a thing at arm's reach with a body's attention on it, which
        is what the station rule reads at one remove; it needs no `look`
        written for it. Measured, Saltmarsh Crossing (2026-10-11, scratch
        chat 170, idx 24): a clerk handed the player a loading slip, she held
        it to the window and read it line by line, and set it down -- two
        transfers, no standing contact, no look -- while the slip's own record
        held every line she read, and her view held none of them. A transfer
        the commit refused names a thing out of reach, and the seen-in-full
        test refuses it with the rest.

    A body is never a thing (rule 2 of `_visible_things`, the same
    `same_subject` test), and a thing the observer only WATCHES someone else
    handle contributes nothing: the bystander gets the act through
    `act_percept`, never the numbers. That asymmetry is the firewall doing
    its ordinary work -- the reading crosses to the one body with a channel
    to it.
    """
    entities = (sc or {}).get("entities") or {}
    if not room or not isinstance(entities, dict):
        return []
    known = [str(b) for b in bodies if str(b)]

    def _is_body(eid, entity):
        label = str(entity.get("name") or "")
        return any(same_subject(sc, str(eid), body)
                   or (label and same_subject(sc, label, body))
                   for body in known)

    def _here(eid):
        return room_of(sc, str(eid)) == room

    found = {}
    for contact in _standing_contacts_for(sc, name):
        if not same_subject(sc, str(contact.get("actor") or ""), name):
            continue
        target = str(contact.get("target") or "").strip()
        if not target or same_subject(sc, target, name):
            continue
        for eid, entity in entities.items():
            if not isinstance(entity, dict) or eid in found:
                continue
            if not same_subject(sc, str(eid), target):
                continue
            if _is_body(eid, entity) or not _here(eid):
                continue
            found[eid] = (entity, "touch")
    at = _station_anchor_of(sc, name)
    if at and not _is_dark(effective_light(sc, room)):
        stations = sc.get("stations") or {}
        for eid, entity in entities.items():
            if not isinstance(entity, dict) or eid in found:
                continue
            row = stations.get(str(eid)) if isinstance(stations, dict) else None
            if not isinstance(row, dict) or str(row.get("at") or "") != at:
                continue
            if _is_body(eid, entity) or not _here(eid):
                continue
            found[eid] = (entity, "sight")
    for eid in _things_asked_by(sc, looks=looks, handled=handled):
        entity = entities.get(eid)
        if not isinstance(entity, dict) or eid in found:
            continue
        if _is_body(eid, entity):
            continue
        if visual_level_between(sc, name, str(eid), senses) != "full":
            continue
        found[eid] = (entity, "sight")
    return [(eid, entity, channel) for eid, (entity, channel) in found.items()]


def _things_asked_by(sc, *, looks=(), handled=()):
    """The entity ids this observer's own act asked about this beat, in the
    order asked: what it looked at (`_own_looks`) and what it took into its
    hands (`_own_handled`), each matched by id, name or alias. Admission is
    `_things_read_by`'s; this only says which reads an act asked for, which
    `composer.asked_this_beat` answers even when nothing about them changed."""
    entities = (sc or {}).get("entities") or {}
    out = []
    for ask in list(looks or ()) + list(handled or ()):
        ask = str(ask or "").strip()
        if not ask or not isinstance(entities, dict):
            continue
        for eid, entity in entities.items():
            if not isinstance(entity, dict) or eid in out:
                continue
            if (same_subject(sc, str(eid), ask)
                    or same_subject(sc, str(entity.get("name") or ""), ask)):
                out.append(eid)
    return out


def _composer_bare_details(rows):
    """[(observer-safe body label, place, detail)] from an already-gated
    `observer_body_regions` projection, via the same `_bare_body_details`
    parser the model-path fidelity floor uses. Covered zones never match, so
    this cannot turn a covered chest into anatomy."""
    out = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        label = str(row.get("body") or composer._t("someone")).strip()
        for region, surface in (row.get("regions") or {}).items():
            for place, detail in _bare_body_details(region, surface):
                rendered = _self_body_detail(detail) if label == "you" else detail
                out.append((label, place, rendered))
    return out


#: Where a beat's own sound events sit among the beat's deliveries: after
#: the acts and speech the loops produced, which are numbered from zero, so
#: a noise reads as part of the beat without displacing what people did.
_AMBIENT_BEAT_BAND = 500_000


def _gated_ambient_percepts(gate, sensory_events, room, *, order_key=None,
                            after=None):
    """Authored ambient events, run through the observer's admission gate.

    Ambient prose is written for the scene, not for a mind: the establish
    stage's own authored events were measured narrating a perceiver's voice
    back at them, and naming characters to observers who had never met
    them. Gating the event text (not the rendered percept) keeps the
    dedupe key honest -- two observers who receive different gated text
    have genuinely received different things. `after` is
    `composer.ambient_percepts`' (a sound heard after its seen source)."""
    if gate is None:
        return composer.ambient_percepts(sensory_events, room,
                                         order_key=order_key, after=after)
    gated = []
    for event in sensory_events or []:
        if not isinstance(event, dict):
            continue
        desc = gate(str(event.get("detail") or event.get("desc")
                        or event.get("description") or event.get("text")
                        or ""))
        if not desc:
            continue
        # EVERY KEY THE READER READS, `detail` first: `ambient_percepts`
        # takes `detail` before `desc`, and every beat sound and charter
        # noise is normalised INTO `detail` -- so a gate that rewrote the
        # other three handed the reader the ungated text on every one of
        # them, and the authored-prose floor held only for events that had
        # no `detail` key to begin with.
        gated.append({**event, "detail": desc, "desc": desc,
                      "description": desc, "text": desc})
    return composer.ambient_percepts(gated, room, order_key=order_key,
                                     after=after)


#: Substance placements whose matter has open air around it. `interior` is
#: matter with a body between it and the room and `contained` is matter in a
#: vessel, so neither reaches a nose across the room. This is the one
#: subtraction the barrier table cannot make for scent -- there is no edge
#: between two rooms to consult -- and the ledger already records which case
#: it is, so it is read rather than guessed.
_SCENT_CARRYING_PLACEMENTS = frozenset({"surface", "room"})


def _scent_sources_for(sc, observer, observer_room, others, display_map,
                       senses, body_scents=None):
    """Every smell reaching one observer, graded and labelled.

    THREE LEDGERS, ONE SHAPE. A body's standing smell comes from its card, an
    object's from the scene entity, and deposited matter's from the substance
    record -- and each is graded by exactly the relation its own channel
    already uses, so nothing here restates the barrier table.

    ATTRIBUTION IS A SECOND CHANNEL'S WORK, and it is the whole of the
    firewall answer (see `composer.scent_percepts`). A smell is attached to a
    body only when this observer can also SEE that body, under the label the
    observer already earned -- so a disguise that conceals identity yields the
    stranger's descriptor here exactly as it does for presence and pose, and a
    body in the dark or beyond a door delivers its smell and not its name.

    An ENTITY's smell is never attributed at all, and that is deliberate
    rather than cautious: the composer admits no percept for the objects
    standing in a room, so naming the oven on the smell channel would be this
    channel delivering a fact about the room's contents that no channel
    gated. A SUBSTANCE is attributed to what it is ON, never to the body it
    came FROM -- the standing form of the cause-blindness
    `substance_event_clause` already keeps for the beat's own delta.

    An observer's OWN card scent is not minted: `others` excludes them, and a
    standing fact true of every beat of a life is noise in a context window
    rather than a percept.
    """
    body_scents = body_scents or {}
    sources = []

    def graded(rel):
        return composer._sense_graded(scent_level(rel), "scent", senses)

    def sees(subject):
        return (composer._sense_graded(
            visual_level_between(sc, observer, subject, senses),
            "sight", senses)
            == "full" and entity_arc(sc, observer, subject) != "rear")

    def rel_to(subject, room=None):
        return spatial_rel_between(sc, observer, subject,
                                   observer_room=observer_room,
                                   target_room=room)

    known_bodies = [str(observer)]
    for body in others or []:
        name = str(body.get("name") or "")
        if not name:
            continue
        known_bodies.append(name)
        scent = str(body_scents.get(name) or "").strip()
        if not scent:
            continue
        label = str(display_map.get(name) or "")
        sources.append({
            "key": composer.body_key(name), "scent": scent,
            "level": graded(rel_to(name, body.get("room"))),
            "label": label,
            "attributed": bool(label) and sees(name),
        })

    for entity_id, entity in ((sc or {}).get("entities") or {}).items():
        if not isinstance(entity, dict):
            continue
        scent = str(entity.get("scent") or "").strip()
        if not scent:
            continue
        if any(same_subject(sc, entity_id, body)
               or same_subject(sc, entity.get("name"), body)
               for body in known_bodies):
            continue        # a registered body's smell is its card's to state
        sources.append({
            "key": composer.body_key(entity_id), "scent": scent,
            "level": graded(rel_to(entity_id, room_of(sc, entity_id))),
            "label": "", "attributed": False,
        })

    rooms = (sc or {}).get("rooms") or {}
    for record in ((sc or {}).get("substances") or []):
        if not isinstance(record, dict):
            continue
        scent = str(record.get("scent") or "").strip()
        target = str(record.get("target") or "")
        placement = str(record.get("placement") or "")
        if not scent or not target \
                or placement not in _SCENT_CARRYING_PLACEMENTS:
            continue
        if same_subject(sc, target, observer):
            # Matter on your own body is in your own air, whatever the room
            # around you is doing.
            level = composer._sense_graded("full", "scent", senses)
            label = ""
        elif target in rooms:
            level = graded(spatial_rel(sc, observer_room, target))
            label = ""
        else:
            level = graded(rel_to(target, room_of(sc, target)))
            label = str(display_map.get(target) or "")
        sources.append({
            "key": str(record.get("substance_id") or "")
                   or composer.body_key(target + scent),
            "scent": scent, "level": level, "label": label,
            "attributed": bool(label) and sees(target),
        })
    # ONE SMELL IS SAID ONCE. The three ledgers are separate facts and are
    # right to be -- `_substance_id` hashes the source and the source part, so
    # arousal reaching a nose from two sites on one body is two records, and
    # collapsing them in the ledger would lose which site. But a nose does not
    # smell the ledger: it smells arousal, and saying so twice tells the
    # reader nothing the first sentence did not.
    #
    # Measured live (chat 95 t59): Mirelle's view carried "Hinami smells of
    # arousal. Hinami smells of arousal." verbatim, from two substance records
    # on one body with identical scent, placement and grade. Folded on what a
    # percept would RENDER -- the smell, its grade and whose it is -- so two
    # different smells, or one smell arriving at two grades, still both land.
    # The surviving key is the first, which keeps the standing-verdict ledger
    # stable across beats as long as that record stands.
    folded, seen = [], set()
    for source in sources:
        signature = (str(source.get("scent") or "").casefold(),
                     str(source.get("level") or ""),
                     str(source.get("label") or "").casefold(),
                     bool(source.get("attributed")))
        if signature in seen:
            continue
        seen.add(signature)
        folded.append(source)
    return folded


def _with_body_description(appearance, described):
    """One body's appearance with its standing body description on the end.

    Appended rather than merged into the summary: `appearance` has already
    been rendered as prose and carries this body's clothing and overlays,
    and the two halves are separate facts about the same body rather than
    one sentence to be rewritten.
    """
    appearance = str(appearance or "").strip()
    described = str(described or "").strip()
    if not described:
        return appearance or None
    if not appearance:
        return described
    return "%s; %s" % (appearance.rstrip(" ;"), described)


def _feature_rows(sc, name, sweep=False):
    """`feature_visibility` for (observer, sweep), derived once per read pass:
    the furniture, the things and the openings each asked it of the same
    observer, three times a stage (audit agents_perception E3, 2026-11-01).
    By reference inside a pass -- every reader here only reads the rows."""
    from world.scene_memo import scene_memo
    return scene_memo(sc, ("feature_visibility", str(name), bool(sweep)),
                      lambda: feature_visibility(sc, name, sweep=bool(sweep)))


def _visible_features(sc, name, room, *, sweep=False):
    """The room's furniture as THIS observer's eyes reach it, or None.

    None -- not an empty list -- for a room nobody authored geometry on
    (`spatial_fov.room_has_geometry`), so the environment percept of every
    story written before the layer existed is byte-identical to what it
    was. For a room that has opted in, `feature_visibility` has already
    subtracted the cone and the line; what is left is delivered near to
    far, and a deliberate look around (`sweep`) turns the observer through
    the whole room for that one beat. Door pseudo-anchors are left out: the
    exits digest already carries them.
    """
    if not room or not room_has_geometry(sc, room):
        return None
    rows = _feature_rows(sc, name, sweep)
    # ...save a door whose edge says what it is like (`desc`): the exits
    # digest names the way through, and this is the door itself, where it
    # stands from here -- once on an anchor minted on top of the edge, now
    # the edge's own words (`spatial_geometry.effective_anchors`).
    from world.spatial import effective_anchors
    described = {aid for aid, a in (effective_anchors(sc, room) or {}).items()
                 if isinstance(a, dict) and a.get("implicit") and a.get("described")}
    return [
        {"desc": r["desc"], "tier": r["tier"], "side": r["side"],
         "peripheral": r["peripheral"]}
        for r in rows if r.get("visible")
        and (not r.get("implicit") or r.get("anchor") in described)
    ]


def _visible_things(sc, name, room, *, sweep=False, bodies=()):
    """The THINGS standing in this room, as this observer's eyes have them.

    Rows of `{what, uid, state}` for `composer.room_content_percepts`, whose
    own docstring names a crowd, a courier and a posted notice and forgot the
    fourth: a thing somebody set down. Until this existed there was no sight
    path from `scene.entities` to any view -- `feature_visibility` answers for
    the room's ANCHORS, and the only walk over scene entities on the view path
    is the scent loop, gated on `entity.scent` -- so a thing reached a mind
    only through a channel that owned it for another reason (attire, a pose, a
    contact, a smell, authored furniture). Measured 2026-09-20: a coin laid on
    a counter appeared in 0 of its own owner's 24 views and she paid twice.

    EVERY RULE HERE SUBTRACTS, and the first one is why this is small: a
    stationed thing INHERITS THE VISIBILITY OF THE ANCHOR IT STANDS AT. The
    cone, the sight line, the occluder and the light have already been decided
    for that anchor by `feature_visibility`; a coin on a counter is seen
    exactly when the counter is. So this adds no new judgment about what an
    eye reaches, and it cannot become a second, disagreeing answer to one the
    engine already has.

      1. No room, or a thing the scene does not place in it -> nothing.
      2. A BODY is not a thing. Presence and pose own every body, and the
         subject-identity test is the engine's own (`same_subject`), because a
         registered person can also stand in `entities` under another key.
      3. CONCEALED IS CONCEALED. A thing any holder hides -- pocketed, shut
         inside something, worn -- is read through `hiding_holders_of`, never
         off `scene['contained']`, so containment keeps its one owner.
      4. A thing that is also authored FURNITURE of this room is the features
         sentence's, not this one's. Two representations of one object can
         only disagree, and the observer would be told twice.
      5. Placed at an anchor -> admitted only when that anchor is visible.
         Placed nowhere -> admitted with NO distance claimed, and only where
         there is light to see by: the anchor carve-outs in
         `feature_visibility` are for a thing a body has its hands on and for
         a doorway, and an unplaced object is neither.
      6. No name -> nothing, the same silence `_feature_items` keeps for a
         row with no description.

    `state` is the thing's own placement, so a thing that MOVES re-renders as
    news and a thing that sits is furniture a delta view omits -- the dedupe
    contract `room_content_percepts` already states, keyed on state and never
    on the sentence composed from it.
    """
    if not room:
        return []
    entities = (sc or {}).get("entities") or {}
    if not entities:
        return []
    stations = (sc or {}).get("stations") or {}
    known = [str(b) for b in bodies if str(b)]
    # RULE 2b: A PERSON IS NEVER A THING. An entity of an explicitly animate
    # kind (`schemas._ANIMATE_ENTITY_KINDS`, the allow-list the inert test
    # already trusts) is a body, said through the presence path and its
    # recognition gate -- not "There is Abel Gale here.", by name, to a
    # player who had never met him (scratch story 165, turn 4582). A device
    # stays a thing; a person the presence path did not admit is better
    # unsaid than said as furniture.
    try:
        from llm.schemas import _ANIMATE_ENTITY_KINDS
    except Exception:
        _ANIMATE_ENTITY_KINDS = frozenset()
    people = {str(eid) for eid, ent in entities.items()
              if isinstance(ent, dict) and str(ent.get("kind") or "")
              .strip().casefold() in _ANIMATE_ENTITY_KINDS}
    # Rule 5's evidence, read once: which anchors this observer's eyes reach,
    # and what each is called.
    seen_anchors = {}
    for row in (_feature_rows(sc, name, sweep) or ()):
        if row.get("visible"):
            seen_anchors[str(row.get("anchor") or "")] = str(row.get("desc") or "")
    # Rule 4: the room's own authored furniture, by anchor id and by name.
    furniture = {str(key).casefold() for key in
                 (((sc.get("rooms") or {}).get(room) or {}).get("anchors") or {})}
    furniture |= {str(desc).casefold() for desc in seen_anchors.values() if desc}
    lit = not _is_dark(effective_light(sc, room))
    rows = []
    for eid, entity in entities.items():
        if not isinstance(entity, dict):
            continue
        label = str(entity.get("name") or "").strip()
        if not label:
            continue                                        # rule 6
        if room_of(sc, str(eid)) != room:
            continue                                        # rule 1
        if any(same_subject(sc, str(eid), body)
               or same_subject(sc, label, body) for body in known):
            continue                                        # rule 2
        if str(eid) in people:
            continue                                        # rule 2b
        if hiding_holders_of(sc, str(eid)):
            continue                                        # rule 3
        # RULE 3b: A THING IN SOMEBODY'S HANDS IS NOT LYING HERE. Held or
        # carried in the open it is not concealed, so rule 3 let it through
        # and the view said "There is the tallow tub here" in seventeen of
        # Emory's views while the commit held it in his grip (playerless
        # Aldermill round 7, 2026-09-23). Its place is the body bearing it:
        # to that body it is theirs, and to anyone else it is part of how the
        # bearer looks, which the bearer's own sentence carries.
        holder, mode = _bearer_of(sc, (str(eid), label))
        if holder:
            if same_subject(sc, holder, name) and mode != "worn":
                what = composer.thing_in_hand_clause(label, mode)
                if what:
                    # `kept_in`: the room it is carried in, so a move re-tells
                    # it (`composer.room_content_percepts`; chat 177 t13-t21).
                    rows.append({"what": what, "uid": str(eid),
                                 "state": [mode, holder], "kept_in": room})
            continue                                        # rule 3b
        if str(eid).casefold() in furniture \
                or label.casefold() in furniture:
            continue                                        # rule 4
        # RULE 4b: A THING THE VIEW CAN NEITHER PLACE NOR DESCRIBE IS NOT A
        # THING LYING HERE. Structural, and deliberately not a list of kinds:
        # the scene keys a room's own character and the sky above it as
        # entities so they can carry a `sound_source` and a `light_source`
        # (`room_light`: "a lamp is a light SOURCE and lives on an entity").
        # Measured, the owner's chat 151: the beach held `The Moon`
        # (`kind: celestial`) and `The Surf` (`kind: ambient`), both with an
        # empty description and no station, and this pass said "There is the
        # Moon here." The moon is not lying on the sand.
        #
        # A thing the view has something to SAY about has one of the two: a
        # description of its own, or a place in the room. The coin had both,
        # the clay mug had a station and no description, the TARDIS a
        # description and no station -- and a source-bearing scenery record has
        # neither, which is exactly what makes it scenery. Its light and its
        # noise still reach the view through the channels that own them.
        described = bool(str(entity.get("description") or "").strip())
        stationed = isinstance(stations.get(str(eid)), dict) \
            and str((stations.get(str(eid)) or {}).get("at") or "")
        if not described and not stationed:
            continue
        at = str(((stations.get(str(eid)) or {}) if isinstance(
            stations.get(str(eid)), dict) else {}).get("at") or "")
        if at:
            if at not in seen_anchors:
                continue                                    # rule 5, placed
            place = seen_anchors[at]
        elif not lit and _is_dark(beam_light_on(sc, str(eid)) or "dark"):
            # A POINTED LIGHT LIGHTS WHAT IT POINTS AT (the owner's ruling,
            # 2026-10-09): a thing with no place, in a dark room, that a beam
            # is aimed at and reaches -- from this room or through a doorway
            # -- is seen by its light, by everyone in the room with it, the
            # way a thing at a lit anchor is. Any other unplaced thing in the
            # dark stays unseen.
            continue                                        # rule 5, unplaced
        else:
            place = ""
        what = composer.thing_clause(label, place)
        if not what:
            continue
        rows.append({"what": what, "uid": str(eid), "state": [at or room]})
    return rows


def _bearer_of(sc, forms):
    """`(body, mode)` when a BODY holds or carries this thing in the open --
    the containment ledger naming it under any of `forms` -- else ("", "").
    A thing on a cart or in an open crate is not a body's, and stays a thing
    lying where its carrier stands."""
    contained = (sc or {}).get("contained") or {}
    if not isinstance(contained, dict):
        return "", ""
    for subject, record in contained.items():
        if not isinstance(record, dict):
            continue
        if not any(same_subject(sc, str(subject), form) for form in forms if form):
            continue
        holder = str(record.get("in") or "").strip()
        if holder and scene_names_body(sc, holder):
            return holder, str(record.get("mode") or "carried").strip().casefold()
        return "", ""
    return "", ""


#: Barriers sight crosses. Kept as a local read of the one definition in
#: `world.spatial_barriers` rather than a second list -- a bearing-less
#: doorway must still admit sight, and only the barrier decides that.
def _sight_crosses(barrier):
    from world.spatial import _SIGHT_BARRIERS
    return normalize_barrier(barrier) in _SIGHT_BARRIERS


def _is_dark(level):
    return str(level or "").casefold() in (
        "dark", "none", "pitch_black", "black")


def _visible_openings(sc, name, room, *, sweep=False, gate=None,
                      named_out=None):
    """The boundaries of `room` this observer can see, and what sight reaches
    past each -- or [] when the room has none it can offer.

    Rows of {desc, room_name, room_notes, dark, features}. THE GRAIN IS
    EXACTLY WHAT STANDING IN THE FAR ROOM WOULD GIVE, MINUS WHAT THE DOORWAY
    TAKES: name, notes, light and cone-capped furniture -- the same four the
    environment percept delivers for the room a body is actually in, and not
    one field more. A glance through a door must never out-resolve walking
    through it.

    Three grades, each falling back on what the world can actually support:

      * sight does not cross (a shut door, a curtain) -> the boundary alone,
        NAMING NOTHING BEYOND IT. What room lies behind a closed door is not
        a fact the observer holds, and putting the name in the view would
        hand it over for free;
      * sight crosses to an unlit room -> the boundary and darkness, because
        you see what is lit and no light means no room;
      * sight crosses to a lit room -> its name and notes, plus its furniture
        when the geometry can place it (`neighbour_feature_visibility`). A
        window or a grille never places -- you cannot walk a grid through
        glass -- and an edge whose bearing the world does not hold cannot be
        laid out either, so both degrade to name and notes rather than
        failing. That is why this does not require a bearing to run: 107 of
        the 185 multi-edge rooms in the live corpus carry none at all, and a
        layer that needed one would have been dark for most of them.

    WHICH BOUNDARIES THE OBSERVER CAN SEE is not re-decided here. Every edge
    already has a door pseudo-anchor placed in the room's geometry, so
    `feature_visibility` has graded it against this observer's cone and line
    along with the furniture; a door it marks unseen is simply absent. Where
    the room has no authored geometry there is nothing to grade against and
    every boundary is offered, which is the same "answers only on evidence it
    has" rule the FOV layer applies to bodies.
    """
    rooms = (sc or {}).get("rooms") or {}
    if not room or room not in rooms:
        return []
    here_light = effective_light(sc, room)
    from world.spatial import _BARRIER_ANCHOR_DESC, door_anchor_id

    seen_doors = None
    if room_has_geometry(sc, room):
        seen_doors = {r["anchor"] for r in _feature_rows(sc, name, sweep)
                      if r.get("implicit") and r["visible"]}
    out = []
    for edge in effective_adjacent(sc, room) or ():
        if not isinstance(edge, dict) or not edge.get("to"):
            continue
        barrier = normalize_barrier(edge.get("barrier"))
        if barrier == "wall":
            continue
        # AN UNBUILT FRONTIER STUB'S JOIN IS NO DOORWAY OF THIS ROOM, AND A
        # FAR ONE IS STILL A WAY (`spatial.frontier_joins`; across a medium
        # the join reaches no reader here at all). The place lies that way,
        # so the view says the way goes on to it -- named, never seen
        # through: no notes, no furniture, nothing past the join -- in the
        # pack's own onward words (`composer._render_openings`). Seen
        # through, it read "Through the open doorway is The Landing" from the
        # mainland, thirteen kilometres of channel away (the lighthouse, chat
        # 3 turn 25); left out, the owner's stories would stop telling a
        # player where the Room's frontier goes on (2026-10-21). Offered
        # whatever the observer faces: the join has no door to grade against
        # the cone, so it answers as every boundary of an unmeasured room
        # does.
        if edge.get("frontier_join"):
            from world.spatial import normalize_vertical
            far_name = str((rooms.get(str(edge["to"])) or {}).get("name") or "").strip()
            if far_name:
                row = {"desc": " ".join(str(edge.get("name") or "").split())
                       or _BARRIER_ANCHOR_DESC.get(barrier) or "the way through",
                       "state": "onward", "room_name": far_name}
                if normalize_vertical(edge.get("vertical")):
                    row["vertical"] = normalize_vertical(edge.get("vertical"))
                out.append(row)
            continue
        to_room = str(edge["to"])
        if seen_doors is not None and door_anchor_id(to_room) not in seen_doors:
            continue
        # The edge's own authored name is the specific thing ("the open blue
        # police box doors"); the barrier's generic phrasing is the floor.
        desc = " ".join(str(edge.get("name") or "").split())
        # A way up or down says so, and an overlook is worded as one: the
        # composer puts the room above or below, over the rail
        # (`spatial_levels.edge_way`).
        from world.spatial import edge_way, normalize_vertical
        _vertical = normalize_vertical(edge.get("vertical"))
        _way = edge_way(edge)
        if not desc:
            desc = _BARRIER_ANCHOR_DESC.get(barrier) or "the way through"
        row = {"desc": desc}
        if _vertical:
            row["vertical"] = _vertical
        if _way:
            row["way"] = _way
        far = rooms.get(to_room)
        if not _sight_crosses(barrier):
            row["state"] = "blind"
            out.append(row)
            continue
        if not isinstance(far, dict):
            row["state"] = "bare"
            out.append(row)
            continue
        # WHAT A POINTED LIGHT LIGHTS IN A DARK ROOM IS SEEN THROUGH THE WAY
        # INTO IT (the owner's ruling, 2026-10-09, D3 of the Brackwater run: a
        # pointed carried light lights what it points at in the next room, and
        # minds see what it shows). The darkness test below reads the far
        # room's TYPICAL light, its median cell, so a lantern aimed through
        # the doorway left the whole room "only darkness" while its beam lit
        # the threshold. Where a BEAM pointed into the room lights some of it
        # (`_beam_lit_view`), the room is seen by that light alone: named, its
        # furniture admitted only where the beam falls, and never its notes --
        # the room as a whole stays dark. No other light admits a dark room:
        # the contrast rule below stands for a lit room's spill and for every
        # lamp that is not pointed in.
        far_dark = _is_dark(effective_light(sc, to_room))
        lit_cells = _beam_lit_view(sc, name, room, to_room) if far_dark else None
        if far_dark and lit_cells is None:
            # DARKNESS IS ONLY WORTH SAYING WHERE IT IS A CONTRAST. A lit room
            # with an unlit way out of it has a black doorway in it, and that
            # is a thing a body sees. Standing in the dark yourself, every
            # exit is dark and saying so about each of them is noise about
            # the night rather than news about the room -- so the boundary is
            # delivered as itself and the darkness goes unremarked.
            row["state"] = "dark" if not _is_dark(here_light) else "bare"
            out.append(row)
            continue
        far_name = str(far.get("name") or "").strip()
        if not far_name:
            row["state"] = "bare"
            out.append(row)
            continue
        row["state"] = "seen"
        if named_out is not None:
            # The rooms this view NAMES through a doorway: a far line leaving
            # through one may say "past" it by that name (`world.landscape`).
            named_out[to_room] = far_name
        # THE SAME PROSE THE ROOM UNDERFOOT DELIVERS (`room_prose`): notes,
        # else desc. Reading `notes` alone here handed a freshly minted room
        # through its doorway as a bare name -- chat 123 turn 9, the TARDIS
        # interior the spatial hand had just described at length.
        notes = "" if far_dark else room_prose(far)
        row["room_name"] = far_name
        row["room_notes"] = gate(notes) if gate is not None else notes
        rows = neighbour_feature_visibility(sc, name, to_room, sweep=bool(sweep))
        if rows and far_dark:
            # The anchors as the LIGHT field lays them out (`derive`), the
            # frame `beam_lit_cells` answers in.
            placed = anchor_cells(sc, to_room, derive=True)
            rows = [r for r in rows if any(
                tuple(c) in lit_cells
                for c in (placed.get(r["anchor"]) or {}).get("cells") or ())]
        if rows:
            row["features"] = rows
        out.append(row)
    return out


def _beam_lit_view(sc, name, room, to_room):
    """What a BEAM POINTED INTO the dark room `to_room` lets this observer,
    standing in `room`, see of it through the way between: the cells of
    `to_room` (its own frame) the beams light that the observer's straight
    line through the gap reaches; an empty set when the room is to be named
    and nothing in it can be placed; None when no beam shows anything, and
    the black doorway stands.

      * The far room has a light field (`spatial.beam_lit_cells`): what the
        beams pointed into it light -- an aim naming it or something in it,
        or a compass aim whose beam proper falls in it, on its way through
        or not -- line-tested from where the observer stands
        (`neighbour_cells_in_view`), so a bystander whose line does not
        reach the lit patch is shown nothing.
      * Sight cannot place the far room (a doorway with no bearing), so
        there is no line to test: only the beams sent through THIS opening
        count -- a lamp standing in the observer's own room -- as below.
      * The far room has no field: no cells and no line. A beam lights only
        the body it names, never the room, and the room is named to an
        observer looking through the opening the beam is sent through
        (`spatial.beam_sent_into`), and to nobody else."""
    lit = beam_lit_cells(sc, to_room)
    if lit is None:
        return set() if beam_sent_into(sc, to_room, room) else None
    if not lit:
        return None
    in_view = neighbour_cells_in_view(sc, name, to_room, lit)
    if in_view is not None:
        return in_view or None
    return beam_lit_cells(sc, to_room, from_room=room) or None


def _was_hearing_this_room(prev_standing, room):
    """Was this observer already being delivered THIS room's sound (D3).

    The soundscape key hashes the room as its subject and the shape as its
    content (`composer.standing_key`), so the subject is the whole question:
    a shape that moved, a shape that stayed, an upgraded chat's single-hash
    key that answers None -- all of them fall out of one comparison. Empty
    ledger, no record, no claim; the same degradation rule
    `standing_verdicts` states at length.
    """
    if not prev_standing or not room:
        return False
    want = composer.standing_key("soundscape", (room,), ("",)).rsplit(":", 1)[0]
    return any(composer._subject_prefix(key) == want for key in prev_standing)


def _heard_without_eyes(shape, senses):
    """A sound shape as a SIGHTLESS ear has it. The shape is graded by ear
    and placed by eye: its `groups` are the visible anchors the noise is
    graded at and its `openings` the doorways in view a sound comes through
    (`spatial_sound_field.sound_shape` rules b and c), so an authored-blind
    card was told "The noise from the generator is a din at the long oak
    counter" -- an anchor it cannot see, placed (audit agents_perception
    F1, 2026-11-01). What the ear has stays: how loud it is where the body
    stands, and the sources it hears. Unchanged for every card that sees."""
    if not isinstance(shape, dict) or "sight" not in _channels_the_card_cuts(
            senses):
        return shape
    return {**shape, "groups": [], "openings": []}


def _composer_standing_percepts(sc, p, name, others, display_map, known, *,
                                entity_state=None, appearance_changed=(),
                                appearance_deltas=None, prev_seen=None,
                                seen_out=None,
                                gate=None, extra_parts=None,
                                body_scents=None, body_descriptions=None,
                                prune_appearance=False,
                                self_forms=(), self_pronouns=None,
                                sound=None, prev_standing=frozenset(),
                                regions=None, prev_scene=None):
    """The standing-state half of one observer's IR: environment, presence,
    first-mention/changed appearances, own body state, standing contact
    sensations, bare body regions. Every admission is a subtraction --
    unseen bodies, rear-arc bodies and covered regions simply never become
    percepts.

    `gate` is this observer's authored-prose gate (`_authored_prose_gate`).
    Room notes and appearance/overlay descriptions pass through it because
    nobody wrote either of them for a particular mind -- see
    `_composer_authored_prose`.

    `sound` is this observer's sound field for the beat (`_sound_field_for`:
    crowds and the turn index included); it is what the soundscape sentence
    is read from, so the sentence and the hearing grades cannot disagree.

    `prev_standing` is this observer's OWN standing ledger from the last
    beat, and the one thing read from it here is whether they were already
    being delivered this room's sound (D3) -- empty on the opening beat and
    on any caller that has no ledger, which reads as "no record" and mints
    nothing, never as "the room was silent".

    `regions` is the frame's region registry (`_far_regions`): the far
    layer's outline look for a place with none of its own, and the region
    names its floor withholds.

    `prev_scene` is the world as it stood before the beat, where the caller
    holds it (the outcome pass): read for one thing only, what the weather
    sounded like then, so its stopping can name what fell
    (`composer.weather_sound_percepts`). Absent, the record's own name
    stands."""
    percepts = []
    room = p.get("room")
    via_names = {}
    room_notes = p.get("room_notes")
    if gate is not None:
        room_notes = gate(room_notes)
    sweep = bool(p.get("sweep"))
    # WHERE THE LIGHT FALLS AND WHERE THE SOUND IS (2026-09-04): the two
    # fields' shapes, each None unless its room is uneven, each built from
    # what this observer's eyes already reach (`feature_visibility`) and
    # what they already see or hear, so the composer can only say less than
    # the observer has. The composer reads no scene; perception hands it the
    # shape and the templates do the rest.
    env = composer.environment_percept(
        room, p.get("room_name"), room_notes,
        effective_light(sc, room) if room else "",
        features=_visible_features(sc, name, room, sweep=sweep),
        openings=_visible_openings(sc, name, room, sweep=sweep, gate=gate,
                                   named_out=via_names),
        light_shape=light_shape(sc, name, sweep=sweep) if room else None)
    if env:
        percepts.append(env)
    if room:
        soundscape = composer.soundscape_percept(_heard_without_eyes(
            sound_shape(sc, name, sound=sound, room=room, sweep=sweep)
            # AN EVEN ROOM'S STEADY SOUND (DESIGN_SOUND_FIELD § 17): the
            # shape speaks only for an uneven room, and a clock in a quiet
            # study or a generator in a small room had no percept at all --
            # it could not start, fade or stop for anyone. `sound_fill` is
            # the rest of the class, under the same `soundscape` subject,
            # so the ceased branch below and the habituation read one
            # ledger for both.
            or sound_fill(sc, name, sound=sound, room=room, sweep=sweep),
            p.get("sense_card")),
            room)
        if soundscape:
            percepts.append(soundscape)
        elif (_was_hearing_this_room(prev_standing, room)
              and room_noise_word(sc, room, sound=sound) == NOISE_WORDS[0]
              and room_holds_a_standing_source(sc, room)):
            # AND WHEN THE ROOM'S SOUND STOPS, SAY SO (review 2026-09-07 D3).
            # `sound_shape` answers None for THREE reasons and only one of
            # them is a silence: the room is even (rule (a)); it has no
            # cells; or there was nothing to grade -- no visible anchor and
            # no measured cell. So the trigger is not "no shape", it is the
            # room's own cells agreeing on the quietest word: a room goes
            # even two ways, its one source stopping or its noise filling
            # every cell, and only the word separates them.
            #
            # THE ROOM'S CELLS AND NOT THE OBSERVER'S, because the sound
            # stopping is a fact about the room. Asked of a body instead,
            # an unplaced one is graded at the room's centre
            # (`SoundField.locate`), which said "the noise has stopped" in a
            # huge dark hall with the generator still running at the wall --
            # the D3 rework's measured false positive.
            #
            # AND ONLY A SOUND WITH A SOURCE STANDING IN THE ROOM CAN BE
            # HEARD TO STOP (D3 rework, second skeptic). A generator switched
            # off is still a generator standing there, so its silence is
            # news; a one-beat crash leaves nothing behind, so there was
            # never a sound of this ROOM'S to stop -- and `sound_shape`
            # already refuses to name a beat's own sounds as the room's
            # shape, for the same reason. Measured on chat 117: every one of
            # the five stranded soundscape keys was an event, so the true
            # count of standing-sound strandings in that corpus is ZERO and
            # every `ceased` percept it would have minted was false.
            #
            # THE OTHER HALF IS WHOSE EAR IT IS, and it is a subtraction:
            # this observer's OWN previous ledger has to hold the sound of
            # THIS room, or there is no silence for them to notice and no
            # percept at all. That keeps an ordinary quiet beat free of a
            # percept nobody renders, and it is what makes "in the same
            # room" exact -- a body that walked somewhere else carries the
            # old room's key, which is not this room's subject.
            #
            # AND A ROOM THAT FELL QUIET HAS NOT NECESSARILY STOPPED. `quiet`
            # is what a sound does to a voice one pace off -- "you can talk
            # over it" -- so a source still running below that goes even at
            # `quiet` too: the din died down, and the thing is still sounding
            # (chat 157 turn 4482, a TARDIS rotor's din "gentling into a hum"
            # in flight, rendered as a total silence).
            percepts.append(composer.sound_ceased_percept(
                room, still_sounding=room_still_sounding(sc, room, sound=sound)))
    # Crowds, couriers and posted notices: three built subsystems whose whole
    # perception seam is these three keys, and until now nothing read them.
    # Already room-scoped and already reduced to what a bystander takes in by
    # the builders that produced them (`common.crowds_for_room` and its two
    # twins), so this adds no admission decision -- it adds the delivery the
    # decisions were being made for.
    # ...and the fourth member of that family, which the three above were
    # always beside: A THING SOMEBODY SET DOWN. Same story exactly -- the
    # admission is decided before the delivery (`_visible_things`, whose every
    # rule subtracts and whose sight judgment is the anchor's own) and this
    # adds only the delivery. Measured 2026-09-20: a coin laid on a counter
    # reached its own owner's eyes on 0 of 24 beats, so she paid for one ale
    # twice.
    # WHAT THE SKY IS DOING, to a body that can tell. `weather_for_room` had
    # already decided every question -- can this body see it, is it landing on
    # them, does the wind reach -- and no mind read any of it: a character in a
    # freezing thundersnow gale was told the room was dim and loud and never
    # that it was snowing. Asked per BODY, not per room, because a canopy in an
    # open square is between THIS body and the sky (`weather.exposure_at`).
    # HEARING, since round 2 (DESIGN_SOUND_FIELD § 17): the weather's sound
    # was folded into the field's FLOOR alone, which masks and is never
    # told, so no mind was ever told it was raining by ear, and none could
    # be told it stopped. `weather_sound_percepts` is the telling -- the
    # precipitation this room hears, at the audibility the sound bed reads
    # (`weather_for_room`), and the wind at the ear -- keyed like the
    # soundscape, so it starts, fades and stops as one; the floor's level
    # is untouched (the owner's rain ruling: rain never masks a line).
    if room:
        from world.weather import weather_for_room
        reach = weather_for_room(sc, room, name)
        percepts.extend(composer.weather_percepts(reach))
        percepts.extend(composer.weather_sound_percepts(
            reach, room, prev_standing=prev_standing,
            before=(weather_for_room(prev_scene, room, name)
                    if prev_scene else None)))
        # WHAT LIES FAR OFF (`world/landscape`, UNBUILT_WORLD §2.40): the
        # places past the next room a body sees from open air, a window or a
        # height, at the grain distance leaves them -- places, never people,
        # named only where this mind knows them, and never a room the near
        # field already answers. Near to far: the weather, these, the horizon.
        from world.landscape import far_places, looked_far
        # WHAT A LOOK FOUND FAR OFF is the beat's EVENT (`looked_far`): the
        # place, its top over what stands nearer, or what is in the way --
        # and a place a look answered is not said again as standing ground.
        found = looked_far(sc, name, p.get("own_looks") or (),
                           known=p.get("known_places"), senses=p.get("sense_card"),
                           via_names=via_names, gate=gate, regions=regions)
        percepts.extend(composer.landscape_look_percepts(found))
        answered = {f["room"] for f in found if f.get("place")}
        percepts.extend(composer.landscape_percepts([
            place for place in far_places(
                sc, name, known=p.get("known_places"), senses=p.get("sense_card"),
                via_names=via_names, gate=gate, regions=regions)
            if (place.get("key_room") or place.get("room")) not in answered]))
        # WHAT STANDS ON THE HORIZON (`world/vistas`): from open air or a
        # window facing its way, through the weather, by the light, over what
        # stands nearer -- decided now, for this body.
        from world.vistas import visible_vistas, what_a_look_finds
        percepts.extend(composer.vista_percepts(
            visible_vistas(sc, name, senses=p.get("sense_card")),
            looked=[(v, what_a_look_finds(sc, name, v, senses=p.get("sense_card")))
                    for v in (p.get("looked_vistas") or ())]))
    if p.get("walk_underway"):
        percepts.extend(composer.walk_underway_percepts(p["walk_underway"]))
    percepts.extend(composer.room_content_percepts(
        p.get("crowds"), p.get("couriers"), p.get("notices"),
        _visible_things(sc, name, room, sweep=sweep,
                        bodies=[name] + [str(b.get("name") or "")
                                         for b in others or []])))
    recognized = set(known.get(name) or [])
    # The room's talk, as ground plus at most one figure — same admission
    # story as the three seams above: `common.chatter_for_room` already
    # decided what a bystander hears, and this is only the delivery
    # (DESIGN_BACKGROUND_PRESENTATION Part A). Except attribution: WHO the
    # fragment names is this observer's question, not the room's. The
    # entry carries each participant's name beside the anonymous form, and
    # the name is read only by an observer who recognises it -- the same
    # gate every speaker and actor label in this view passes
    # (`charter_chatter.relabel_fragment`; Harrowmere replay t32, where the
    # room's chatter named a trader to a player who had never been told).
    from world.charter_chatter import relabel_fragment
    percepts.extend(composer.chatter_percepts([
        relabel_fragment(
            entry, recognizes=lambda n: _recognizes(n, recognized),
            display_for=display_map.get)
        if isinstance(entry, dict) and entry.get("kind") == "fragment"
        else entry
        for entry in (p.get("chatter") or [])]))
    senses = p.get("sense_card")
    percepts.extend(composer.presence_percepts(
        sc, name, others, display_map, senses))
    names = getattr(gate, "names", None)
    percepts.extend(composer.pose_percepts(
        sc, name, others, display_map, senses,
        self_forms=self_forms, self_pronouns=self_pronouns,
        scrub=(lambda text: names(text, labels=display_map)) if names else None))
    for body in others:
        b_name = body.get("name")
        if not b_name:
            continue
        if composer._sense_graded(
                visual_level_between(sc, name, b_name, senses),
                "sight", senses) != "full":
            continue
        if entity_arc(sc, name, b_name) == "rear":
            continue
        # SEEN THIS BEAT. Recorded before any of the reasons below to
        # skip building a percept, because the question the ledger answers
        # is "could this observer see them", not "did we say anything".
        if seen_out is not None:
            seen_out.add(b_name)
        recog = not disguise_breaks_recognition(
            body.get("disguise_known_to"), name,
            body.get("disguise_conceals_identity")
        ) and _recognizes(b_name, recognized)
        changed = any(same_subject(sc, b_name, item)
                      for item in appearance_changed or ())
        # A BODY YOU ARE MEETING AGAIN. `prev_seen` is None when the
        # previous beat left no record -- an older stored ledger, or the
        # opening beat -- and unknown must not mean "re-describe
        # everyone", so it reads as no re-encounter at all.
        reencountered = (prev_seen is not None
                         and b_name not in prev_seen)
        if prune_appearance and recog and not changed and not reencountered:
            # A familiar stable body's authored card is not a new percept.
            continue
        label = display_map.get(b_name) or (
            b_name if recog else "the unfamiliar person")
        # WHAT THE CARD SAYS THE BODY LOOKS LIKE rides the full description
        # and nothing else. It is delivered here, past the sight gate above
        # and the rear-arc gate above that, because this is the only place a
        # body's own appearance is handed over at all -- the short stranger
        # LABEL is cut from the summary alone and stays that way, so an
        # observer holding a silhouette cannot start reading a face off the
        # name they were given for it.
        described = _with_body_description(
            body.get("appearance"), (body_descriptions or {}).get(b_name))
        if recog:
            description = described
        else:
            description = _strip_identity_tokens(
                described, [b_name, *(body.get("aliases") or [])])
        # `_strip_identity_tokens` removes only the described body's OWN
        # name. A scene overlay describing one body routinely names another
        # ("her arms still around Hinami"), and that third name walked
        # through -- 957 admissions the output tripwire then caught and
        # scrubbed after the fact. The gate catches it before the percept.
        if gate is not None:
            description = gate(description)
        if description:
            # A CHANGE IS RENDERED AS THE CHANGE. Only a body whose clothing
            # actually moved has a readable delta; a scale, an overlay or a
            # wholesale description rewrite has none, and falls back to the
            # full description rather than going unmentioned.
            # Computed by the caller, which is the stage that holds the
            # PREVIOUS scene; a stage without one simply has no delta and
            # falls back to the full description.
            #
            # TRANSITION PHRASING DISCLOSES THE PAST STATE, not just the
            # present one. "No longer wearing the robe" hands a returning
            # observer robe-WAS-worn, which is a fact that reached them
            # through no channel if they were asleep, in another room, or
            # behind the body when it came off. The delta is computed from
            # the objective previous scene, so it may only ride a percept
            # where that scene is a PROVEN stand-in for this observer's own
            # last percept: they held this body at full sight last beat, and
            # attire on a fully seen body is fully seen. `prev_seen` is None
            # when the previous beat left no record, and unknown must not
            # pass for proof. Failing the proof costs nothing but wording --
            # the percept falls back to the current description, and what
            # they conclude from it stays theirs to conclude.
            saw_before = prev_seen is not None and b_name in prev_seen
            delta = ((appearance_deltas or {}).get(b_name, "")
                     if prune_appearance and changed and saw_before else "")
            percepts.append(composer.appearance_percept(
                b_name, label, description, force=changed, delta=delta,
                reearn=reencountered, held=saw_before))
    if entity_state:
        state_percept = composer.body_state_percept(entity_state)
        if state_percept:
            percepts.append(state_percept)
    # THE BODY'S OWN EARS (DESIGN_SOUND_FIELD § 13): ringing after a blast --
    # from the shift the scene holds, or a blast that reached them this beat
    # (`blast_exposure`, measured by the outcome pass before the commit has
    # written it) -- and its fading, said once to an ear that was ringing.
    # Interoception: this body's view and nobody else's.
    from world.spatial import dulled_shift_db
    percepts.extend(composer.ear_percepts(
        dulled_shift_db(sc, name), prev_standing,
        fresh=bool(p.get("blast_exposure"))))
    # The identity floor rides the sensation clause at its source: the OTHER
    # party is named through this observer's own display map -- a recognized
    # partner gets their name, a stranger the descriptor, and a spelling the
    # map cannot place never leaks the canonical name (the tripwire
    # downstream remains the backstop). Before this, the clause named the
    # partner canonically and the tripwire fired on every contact beat with
    # an unrecognized partner (chat 70).
    #
    # A CONTACT PARTY IS NOT NECESSARILY A BODY, and "someone" asserts one.
    # The map holds co-present BODIES and nothing else, so every miss took the
    # person-shaped default -- and a contact record may name a garment, a
    # fixture, a device or a bare noun as readily as a person. Measured live,
    # chat 98 turn 22: the player's own combadge resting on her uniform was
    # delivered as "your uniform registers someone against it", and the page
    # made it a body pressed continuously against her with three absent
    # people's scents attached. Five more object contacts in the same run read
    # "someone's surface", "someone's exterior", "someone's edge" -- for a bar,
    # a table twice, a glass and a padd.
    #
    # ONE LADDER, ASKED AT BOTH SITES. `composer._pose_referent` already ranks
    # this exact order of certainty -- observer, a body already given, any
    # other body (kept, because a body you are TOUCHING reaches you by
    # interoception whether or not you can see who), a scene entity by its own
    # name, an id-shaped token dropped -- and it was added for poses after this
    # identical class put a desk in a room as an unidentified person (chat 84).
    # A second ladder minted for contacts is what let the THIRD site
    # (`narration._partner_label`) keep the person-shaped floor while two were
    # fixed, so the reuse is the point rather than an economy. A referent it
    # drops is a thing this observer cannot name, which is what "something"
    # says. The world-side floors that keep clothing out of a contact
    # altogether (`_endpoint_is_worn_clothing`, `_part_is_clothing`) sit under
    # this and answer a different question: not what to CALL a party, but
    # whether the record should have had one.
    _sensation_label = (
        lambda other: composer._pose_referent(
            sc, name, display_map, others, other, is_self=True) or "something")
    observer_standing_contacts = _standing_contacts_for(sc, name)
    percepts.extend(composer.contact_percepts([
        (contact, contact_sensation(contact, you=name, scene=sc,
                                    label_for=_sensation_label))
        for contact in observer_standing_contacts
    ]))
    # Contact actions ride the same contacts: suction/humming/pulsing the
    # actor is performing, or that someone else is performing on a contact
    # the observer is a party to. Same channel (touch), same dedupe story,
    # carried as their own percepts so the actor and the receiver each get
    # their side on a single beat.
    percepts.extend(composer.contact_action_percepts([
        (record, contact_action_clause(record, observer=name, scene=sc,
                                       label_for=_sensation_label))
        for record in contact_actions_for_observer(sc, name)
    ]))
    # WHAT THE THING UNDER THOSE HANDS SAYS ABOUT ITSELF. The contact
    # percept above is the sensation of touching it; this is its record --
    # readings, harm, workings -- delivered to the one body reading it
    # (`_things_read_by`: hands on it, or at its station with light). The
    # objects hand has been required to write these facts since the detail
    # clause and no view path read them back (chat 152 t4337-4338: two beats
    # of "checking the console for damage" answered with nothing).
    # A read this body's own act asked for this beat is said this beat,
    # unchanged or not (`composer.asked_this_beat`).
    # A name WRITTEN on the thing reaches this mind as written, never as
    # whose body it is (`gate.written`).
    _asked = set(_things_asked_by(sc, looks=p.get("own_looks") or (),
                                  handled=p.get("own_handled") or ()))
    _written = getattr(gate, "written", None) or (lambda text: text)
    percepts.extend(composer.thing_reading_percepts([
        (str(entity.get("name") or ""), _written(composer.thing_reading_text(
            entity.get("state"))), str(eid), channel, eid in _asked)
        for eid, entity, channel in _things_read_by(
            sc, name, room,
            bodies=[name] + [str(b.get("name") or "") for b in others or []],
            looks=p.get("own_looks") or (), handled=p.get("own_handled") or (),
            senses=p.get("sense_card"))
    ]))
    region_labels = {name: "you"}
    for body in others:
        if body.get("name"):
            # The story's word for a body the map cannot name, never the
            # English literal (audit agents_composer F9, 2026-11-01).
            region_labels[body["name"]] = display_map.get(
                body["name"], composer._t("someone"))
    rows = observer_body_regions(sc, name, region_labels,
                                 extra_parts=extra_parts)
    percepts.extend(
        composer.body_region_percepts(_composer_bare_details(rows)))
    # Authored extra parts ride the same gated projection as bare regions,
    # in a sibling key. Reading only `regions` -- which is what this did
    # when the two features merged -- landed the whole extra-parts feature
    # silently dead on the live path: gated correctly, rendered nowhere.
    percepts.extend(composer.body_part_percepts([
        (str(row.get("body") or composer._t("someone")), part)
        for row in rows or [] if isinstance(row, dict)
        for part in (row.get("part_data") or [])
    ]))
    percepts.extend(composer.scent_percepts(_scent_sources_for(
        sc, name, room, others, display_map, senses,
        body_scents=body_scents)))
    return percepts
